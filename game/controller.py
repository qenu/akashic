from __future__ import annotations

import json
import random
import sys
import threading
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import QObject, QSettings, Signal
from PySide6.QtWidgets import QApplication

from app_config import AppConfig
from app_logger import AppLogger
from responses import APIConfig, APIError, ResponseClient
from game.records import ChatRecord
from game.parsing import assistant_chat_payload, extract_json, format_changes_lines, NARRATIVE_KEYS, pick_first_text, SUMMARY_KEYS
from game.world_io import (
    resolve_latest_world_folder,
    is_world_initialized,
    export_init_world_files,
    append_novel,
    append_summary,
    count_summary_words,
    read_summary,
    write_summary,
    archive_and_remove_world,
    dump_logs,
    restore_records_from_logs,
    read_world_json,
)
from game.context import build_runtime_context
from game.changes import apply_changes

log = AppLogger.get_logger("state")

SUMMARY_COMPRESSION_THRESHOLD = 1200  # words


class GameStateController(QObject):
    """Main orchestrator: wires UI signals, manages chat flow, delegates
    world I/O and context building to dedicated modules."""

    assistant_reply_ready = Signal(str)
    compression_state_changed = Signal(bool)
    world_data_updated = Signal()
    api_error_occurred = Signal(str)

    def __init__(self, base_path: Path) -> None:
        super().__init__()
        self.records: list[ChatRecord] = []
        self.story_file_path: Path | None = None
        self._world_folder_path: Path | None = None
        self._awaiting_init_export = False
        self._awaiting_opening_options = False
        self._init_export_done = False
        self._compression_in_progress = False
        self._summary_lock = threading.Lock()
        self._skill_mode = "idle"  # "idle" | "use" | "forget"
        self._pending_new_skill: dict | None = None
        self._last_story_options: list[str] = []
        self._config = AppConfig.instance()
        self._base_path = base_path
        self._greetings_lines = self._read_prompt_lines("core/template/greetings.md", "Describe a world you want to live in.")
        self._core_prompt = self._read_prompt_file("core/system.md", "")
        self._init_prompt = self._read_prompt_file("core/init.md", "")
        self._compression_prompt = self._read_prompt_file("core/compression.md", "")

        self._restore_existing_world_state()
        self._api_client = self._build_api_client()

        app = QApplication.instance()
        self.app = app if app is not None else QApplication(sys.argv)

        from ui import MainWindow, SectionsPage, LibraryPage, ItemPage, QuestPage, EquipmentPage

        self.window = MainWindow(base_path)
        sections_page = self.window.findChild(SectionsPage, "sectionsPage")
        if sections_page is None:
            raise RuntimeError("Sections page was not found in MainWindow")
        self.sections_page: SectionsPage = sections_page

        item_page: ItemPage | None = self.window.findChild(ItemPage, "itemPage")
        self._item_page: ItemPage | None = item_page
        if item_page is not None:
            item_page.item_used.connect(self._on_item_used)
            self.world_data_updated.connect(item_page.refresh)

        quest_page: QuestPage | None = self.window.findChild(QuestPage, "questPage")
        if quest_page is not None:
            self.world_data_updated.connect(quest_page.refresh)

        equipment_page: EquipmentPage | None = self.window.findChild(EquipmentPage, "equipmentPage")
        if equipment_page is not None:
            self.world_data_updated.connect(equipment_page.refresh)

        self.library_page: LibraryPage | None = self.window.findChild(LibraryPage, "libraryPage")
        if self.library_page is not None:
            self.library_page.refresh_from_latest_world(self._base_path)

        restored_has_options = self._rebuild_chat_ui_from_records()
        world_init = self._is_world_initialized()
        should_enable_options = world_init or restored_has_options

        log.info(
            "Startup state: world_initialized={}, restored_has_options={}, enabling_options={}",
            world_init, restored_has_options, should_enable_options,
        )

        self.sections_page.set_options_available(should_enable_options)
        self.sections_page.user_message_sent.connect(self._on_user_message)
        self.sections_page.skill_button_clicked.connect(self._on_skill_button_clicked)
        self.sections_page.skill_candidate_selected.connect(self._on_skill_candidate_selected)
        self.window.reset_story_requested.connect(self.reset_story)
        self.assistant_reply_ready.connect(self._on_async_assistant_reply)
        self.compression_state_changed.connect(self.sections_page.set_compressing)
        self.api_error_occurred.connect(self._on_api_error)
        self._ensure_world_prompt()

    # ------------------------------------------------------------------
    # Prompt helpers
    # ------------------------------------------------------------------

    def _read_prompt_file(self, file_name: str, fallback: str) -> str:
        file_path = self._base_path / file_name
        if not file_path.exists():
            log.warning("Prompt file not found: {}", file_path)
            return fallback
        content = file_path.read_text(encoding="utf-8").strip()
        return content if content else fallback

    def _read_prompt_lines(self, file_name: str, fallback: str) -> list[str]:
        file_path = self._base_path / file_name
        if not file_path.exists():
            log.warning("Prompt file not found: {}", file_path)
            return [fallback]
        lines = [line.strip() for line in file_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        return lines if lines else [fallback]

    # ------------------------------------------------------------------
    # Novel log
    # ------------------------------------------------------------------

    def _append_novel_entry(self, text: str) -> None:
        if self._world_folder_path is not None:
            append_novel(self._world_folder_path, text)

    def _append_novel_narrative(self, assistant_text: str) -> None:
        if self._world_folder_path is None:
            return
        payload = extract_json(assistant_text)
        if not isinstance(payload, dict):
            return
        narrative = pick_first_text(payload, NARRATIVE_KEYS)
        if narrative:
            append_novel(self._world_folder_path, narrative)

    def _append_summary_entry(self, assistant_text: str) -> None:
        """Extract the summary field from an assistant reply and append it to summary.md.
        Skipped during the opening options turn (system-generated, not player-driven).
        Triggers background compression when the file exceeds the word-count threshold."""
        if self._world_folder_path is None:
            return
        if self._awaiting_opening_options:
            return
        payload = extract_json(assistant_text)
        if not isinstance(payload, dict):
            return
        summary = pick_first_text(payload, SUMMARY_KEYS)
        if not summary:
            return
        with self._summary_lock:
            append_summary(self._world_folder_path, summary)
            word_count = count_summary_words(self._world_folder_path)
        if word_count >= SUMMARY_COMPRESSION_THRESHOLD and not self._compression_in_progress:
            self._compression_in_progress = True
            log.info("Summary exceeded {} words; scheduling compression", SUMMARY_COMPRESSION_THRESHOLD)
            threading.Thread(target=self._compress_summary, daemon=True).start()

    def _compress_summary(self) -> None:
        """Compress summary.md in place via a dedicated API call. Runs in a background thread."""
        world_folder = self._world_folder_path
        client = self._api_client
        compression_prompt = self._compression_prompt
        try:
            self.compression_state_changed.emit(True)
            if client is None or not compression_prompt or world_folder is None:
                log.warning("Summary compression skipped: missing client, prompt, or world folder")
                return
            with self._summary_lock:
                snapshot = read_summary(world_folder)
            if not snapshot.strip():
                return
            snapshot_words = len(snapshot.split())
            messages = [
                {"role": "system", "content": compression_prompt},
                {"role": "user", "content": snapshot},
            ]
            log.info("Compressing summary ({} words)…", snapshot_words)
            compressed = client.send_messages(messages, reasoning=False)
            if not compressed.strip():
                log.warning("Summary compression returned empty result; skipping")
                return
            if len(compressed.split()) >= snapshot_words:
                log.warning("Compression result not shorter ({} >= {}); skipping",
                            len(compressed.split()), snapshot_words)
                return
            with self._summary_lock:
                # Re-read to catch any entries appended during the API call
                latest = read_summary(world_folder)
                tail = latest[len(snapshot):].strip()
                final = compressed.strip() + ("\n\n" + tail if tail else "")
                write_summary(world_folder, final)
            log.info("Summary compressed: {} -> {} words", snapshot_words, len(compressed.split()))
        except Exception as exc:
            log.warning("Summary compression failed: {}", exc)
        finally:
            self._compression_in_progress = False
            self.compression_state_changed.emit(False)

    # ------------------------------------------------------------------
    # World changes
    # ------------------------------------------------------------------

    def _apply_world_changes(self, assistant_text: str) -> None:
        if self._world_folder_path is None:
            return
        payload = extract_json(assistant_text)
        if not isinstance(payload, dict):
            return
        changes = payload.get("changes")
        if not isinstance(changes, list) or not changes:
            return

        apply_changes(self._world_folder_path, changes)
        self.world_data_updated.emit()

    # ------------------------------------------------------------------
    # API client
    # ------------------------------------------------------------------

    def _build_api_client(self) -> ResponseClient | None:
        api_key = str(QSettings("erikH", "interactive-chat").value("ai/api_key", "", type=str)).strip()
        if not api_key:
            return None
        base_url = str(self._config.get("ai", "base_url", "api.x.ai")).strip()
        model = str(self._config.get("ai", "model", "grok-3-latest")).strip()
        reasoning_model = str(self._config.get("ai", "reasoning_model", "grok-3-mini")).strip()
        config = APIConfig(
            base_url=base_url,
            api_key=api_key,
            model=model or "grok-3-latest",
            reasoning_model=reasoning_model or "grok-3-mini",
        )
        return ResponseClient(config)

    # ------------------------------------------------------------------
    # Restore / rebuild
    # ------------------------------------------------------------------

    def _restore_existing_world_state(self) -> None:
        world_folder = resolve_latest_world_folder(self._base_path)
        if world_folder is None:
            return
        self._world_folder_path = world_folder
        self._init_export_done = True

        restored = restore_records_from_logs(world_folder)
        if restored:
            self.records = restored

    def _rebuild_chat_ui_from_records(self) -> bool:
        if not self.records:
            return False

        self.sections_page.clear_story_ui()
        last_options: list[str] = []
        player_data, item_data, map_data = self._read_player_and_items()

        for record in self.records:
            if record.role == "user":
                self.sections_page.add_history_message(text=record.text, is_user=True)
                continue
            narrative, status_line, options = assistant_chat_payload(record.text, player_data, item_data, map_data)
            self.sections_page.add_history_message(text=narrative, status_line=status_line, options=options, is_user=False)
            if options:
                last_options = options

        self._last_story_options = last_options
        self.sections_page.set_option_candidates(last_options)
        log.info(
            "Restored chat UI with {} messages; last options available: {}",
            len(self.records), bool(last_options),
        )
        return bool(last_options)

    def _is_world_initialized(self) -> bool:
        folder = self._world_folder_path or resolve_latest_world_folder(self._base_path)
        if folder is None:
            return False

        initialized = is_world_initialized(self._base_path, folder)
        if initialized and self._world_folder_path is None:
            self._world_folder_path = folder
            self._init_export_done = True
        return initialized

    # ------------------------------------------------------------------
    # Chat flow
    # ------------------------------------------------------------------

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _on_user_message(self, text: str) -> None:
        log.info("Received user message")
        self.records.append(ChatRecord(role="user", text=text, timestamp_utc=self._now_iso()))
        self._dump_logs_memory()
        self._append_novel_entry(text)
        self._request_assistant_reply()

    def _on_api_error(self, message: str) -> None:
        self.sections_page.set_waiting(False)
        self.sections_page.show_error(message)

    def _on_item_used(self, item_name: str) -> None:
        if not self._init_export_done:
            return
        if self._item_page is not None:
            self._item_page.set_frozen(True)
        self.window.show_chat_badge()
        message = f"我使用了道具：{item_name}"
        self.sections_page.add_history_message(text=message, is_user=True)
        self._on_user_message(message)

    # ------------------------------------------------------------------
    # Skill flow
    # ------------------------------------------------------------------

    MAX_SKILLS = 4

    def _on_skill_button_clicked(self) -> None:
        if self._skill_mode != "idle":
            self._exit_skill_mode(notification="放棄使用技能")
            return
        if self._world_folder_path is None:
            return
        skills = read_world_json(self._world_folder_path, "skill.json", [])
        if not isinstance(skills, list) or not skills:
            self.sections_page.assistant_message_received.emit("你目前沒有任何技能。")
            return
        lines = ["你要使用哪個技能？"]
        for i, skill in enumerate(skills, 1):
            name = skill.get("名稱", "未知技能")
            effect = skill.get("效果", "")
            lines.append(f"{i}. {name}：{effect}")
        self.sections_page.show_skill_prompt("\n".join(lines))
        self._skill_mode = "use"
        self.sections_page.set_skill_button_mode("use")
        self.sections_page.set_skill_candidates(skills)

    def _on_skill_candidate_selected(self, skill_name: str) -> None:
        if self._skill_mode == "use":
            self._exit_skill_mode(notification=f"使用了{skill_name}")
            self._on_user_message(f"我使用了技能：{skill_name}")
        elif self._skill_mode == "forget":
            self._forget_skill_and_apply(skill_name)

    def _exit_skill_mode(self, notification: str = "放棄使用技能") -> None:
        self._skill_mode = "idle"
        self.sections_page.set_skill_button_mode("idle")
        self.sections_page.dismiss_skill_prompt(notification)
        self.sections_page.freeze_input(False)
        self.sections_page.set_option_candidates(self._last_story_options)

    def _check_and_prompt_forget_skill(self) -> None:
        """Called after each turn's stream finishes. Shows the in-chat forget
        bubble if the player's skill count exceeds MAX_SKILLS."""
        if self._world_folder_path is None:
            return
        current_skills = read_world_json(self._world_folder_path, "skill.json", [])
        if not isinstance(current_skills, list) or len(current_skills) <= self.MAX_SKILLS:
            return
        self._trigger_forget_skill_prompt(current_skills)

    def _trigger_forget_skill_prompt(self, current_skills: list) -> None:
        lines = [f"技能欄已滿（上限 {self.MAX_SKILLS} 個），請選擇要遺忘的技能："]
        for skill in current_skills:
            name = skill.get("名稱", "未知技能")
            effect = skill.get("效果", "")
            lines.append(f"{name}：{effect}" if effect else name)
        self.sections_page.show_skill_prompt("\n".join(lines))
        self._skill_mode = "forget"
        self.sections_page.set_skill_button_mode("forget")
        self.sections_page.set_skill_candidates(current_skills)
        self.sections_page.freeze_input(True)

    def _forget_skill_and_apply(self, skill_name: str) -> None:
        if self._world_folder_path is None:
            self._exit_skill_mode(notification="放棄遺忘技能")
            return
        skills = read_world_json(self._world_folder_path, "skill.json", [])
        skill_to_remove = next((s for s in skills if s.get("名稱") == skill_name), None)
        if skill_to_remove and skill_to_remove.get("id"):
            remove_change = {"action": "remove", "type": "技能", "id": skill_to_remove["id"]}
            apply_changes(self._world_folder_path, [remove_change])
        self.world_data_updated.emit()
        self._exit_skill_mode(notification=f"遺忘了《{skill_name}》")

    def _ensure_world_prompt(self) -> None:
        if self.records:
            return
        if self._init_export_done:
            return
        self.sections_page.assistant_message_received.emit(random.choice(self._greetings_lines))

    def _request_assistant_reply(self) -> None:
        self.sections_page.set_waiting(True)
        self._api_client = self._build_api_client()

        if self._api_client is None:
            log.warning("API client unavailable: missing API key")
            self.api_error_occurred.emit("API key is not set. Add it in Settings to continue.")
            return

        messages: list[dict[str, str]] = []
        is_world_init_turn = not self._init_export_done and not self._is_world_initialized()

        if is_world_init_turn and self._init_prompt:
            messages.append({"role": "system", "content": self._init_prompt})
            self._awaiting_init_export = True
        else:
            self._awaiting_init_export = False

        records_for_api = self.records
        if self._init_export_done:
            records_for_api = self._records_without_world_builder_turn(self.records)

        if self._world_folder_path is not None:
            context_payload = build_runtime_context(self._world_folder_path, records_for_api)
            messages.append({
                "role": "system",
                "content": "runtime_context.json\n" + json.dumps(context_payload, ensure_ascii=False),
            })

        # Inject only the latest user message so the model knows what to respond to.
        if records_for_api:
            latest = records_for_api[-1]
            if latest.role == "user":
                messages.append({"role": "user", "content": latest.text})

        # Place system.md at the very end so it's the last thing the
        # model sees, making it much harder to ignore.
        if self._core_prompt and not is_world_init_turn:
            messages.append({"role": "system", "content": self._core_prompt})

        threading.Thread(
            target=self._fetch_assistant_reply,
            args=(messages, is_world_init_turn),
            daemon=True,
        ).start()

    @staticmethod
    def _records_without_world_builder_turn(records: list[ChatRecord]) -> list[ChatRecord]:
        first_user_seen = False
        first_assistant_seen = False
        filtered: list[ChatRecord] = []

        for record in records:
            if not first_user_seen and record.role == "user":
                first_user_seen = True
                continue
            if first_user_seen and (not first_assistant_seen) and record.role == "assistant":
                first_assistant_seen = True
                continue
            filtered.append(record)

        return filtered

    def _fetch_assistant_reply(self, messages: list[dict[str, str]], use_reasoning: bool = False) -> None:
        if self._api_client is None:
            self.api_error_occurred.emit("API key is not set. Add it in Settings to continue.")
            return
        try:
            log.info("Requesting assistant reply with {} messages (reasoning={})", len(messages), use_reasoning)
            assistant_text = self._api_client.send_messages(messages, reasoning=use_reasoning)
        except APIError as exc:
            log.exception("Assistant request failed")
            self.api_error_occurred.emit(str(exc))
            return
        except Exception as exc:
            log.exception("Assistant request failed with unexpected exception")
            self.api_error_occurred.emit(str(exc))
            return
        self.assistant_reply_ready.emit(assistant_text)

    def _on_async_assistant_reply(self, assistant_text: str) -> None:
        world_builder_completed = False

        if self._awaiting_init_export and not self._init_export_done:
            new_folder = export_init_world_files(self._base_path, assistant_text)
            self._awaiting_init_export = False
            if new_folder is not None:
                self._world_folder_path = new_folder
                self._init_export_done = True
                world_builder_completed = True
                if self.library_page is not None:
                    self.library_page.refresh_from_latest_world(self._base_path)
            else:
                log.warning("World init export failed; keeping init state so user can retry")

        old_player_data, old_item_data, _ = self._read_player_and_items()

        self._apply_world_changes(assistant_text)

        self.records.append(
            ChatRecord(role="assistant", text=assistant_text, timestamp_utc=self._now_iso())
        )
        self._dump_logs_memory()

        self._append_novel_narrative(assistant_text)
        self._append_summary_entry(assistant_text)

        player_data, item_data, map_data = self._read_player_and_items()
        narrative, status_line, options = assistant_chat_payload(assistant_text, player_data, item_data, map_data)

        payload = extract_json(assistant_text)
        raw_changes = payload.get("changes") if isinstance(payload, dict) else []
        changes_lines = format_changes_lines(
            raw_changes or [],
            old_player_data, player_data,
            old_item_data, item_data,
            map_data,
            quest_data=self._read_quest_data(),
        )
        changes_text = "\n".join(changes_lines)

        def on_stream_done() -> None:
            self.sections_page.set_waiting(False)
            self._last_story_options = options
            self.sections_page.set_option_candidates(options)
            if self._item_page is not None:
                self._item_page.set_frozen(False)
            self.window.clear_chat_badge()
            if world_builder_completed:
                self._request_opening_options_after_world_builder()
            elif self._awaiting_opening_options:
                self._awaiting_opening_options = False
                self.sections_page.set_options_available(True)
            self._check_and_prompt_forget_skill()

        self.sections_page.start_stream(
            narrative,
            status_line=status_line,
            changes_text=changes_text,
            options=options,
            on_done=on_stream_done,
        )

    def _request_opening_options_after_world_builder(self) -> None:
        log.info("World builder completed; requesting opening narrative/options")
        self._awaiting_opening_options = True
        self._request_assistant_reply()

    # ------------------------------------------------------------------
    # Player data helpers
    # ------------------------------------------------------------------

    def _read_player_and_items(self) -> tuple:
        if self._world_folder_path is None:
            return None, None, None
        player_data = read_world_json(self._world_folder_path, "player.json", {})
        item_data = read_world_json(self._world_folder_path, "item.json", [])
        map_data = read_world_json(self._world_folder_path, "map.json", [])
        return player_data, item_data, map_data

    def _read_quest_data(self) -> list:
        if self._world_folder_path is None:
            return []
        return read_world_json(self._world_folder_path, "quest.json", [])

    # ------------------------------------------------------------------
    # Records persistence
    # ------------------------------------------------------------------

    def get_records(self) -> list[ChatRecord]:
        return list(self.records)

    def clear_records(self) -> None:
        self.records.clear()

    def save_records(self, file_path: str | Path) -> None:
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = [asdict(r) for r in self.records]
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self.story_file_path = path

    def load_records(self, file_path: str | Path) -> None:
        path = Path(file_path)
        if not path.exists():
            self._ensure_world_prompt()
            return
        data = json.loads(path.read_text(encoding="utf-8"))
        self.records = [ChatRecord(**item) for item in data]
        self.story_file_path = path
        self._ensure_world_prompt()

    def _dump_logs_memory(self) -> None:
        if self._world_folder_path is None:
            return
        dump_logs(self._world_folder_path, self.records)

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------

    def reset_story(self) -> None:
        if self._world_folder_path is not None:
            archive_and_remove_world(self._base_path, self._world_folder_path)

        self.clear_records()
        self._world_folder_path = None
        self._awaiting_init_export = False
        self._awaiting_opening_options = False
        self._init_export_done = False
        self.sections_page.clear_story_ui()
        self.sections_page.set_options_available(False)
        self._api_client = self._build_api_client()

        if self.story_file_path is not None:
            self.story_file_path.parent.mkdir(parents=True, exist_ok=True)
            self.story_file_path.write_text("[]\n", encoding="utf-8")

        self._ensure_world_prompt()

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def run(self) -> int:
        self.window.show()
        return self.app.exec()
