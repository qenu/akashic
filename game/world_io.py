from __future__ import annotations

import json
import re
import shutil
from dataclasses import asdict
from pathlib import Path
from typing import Any

from app_logger import AppLogger
from game.records import ChatRecord, InitWorldData

log = AppLogger.get_logger("world-io")

DEFAULT_REQUIRED_FILES = {"player.json", "quest.json"}


def resolve_latest_world_folder(
    base_path: Path,
    required_files: set[str] | None = None,
) -> Path | None:
    if required_files is None:
        required_files = DEFAULT_REQUIRED_FILES

    candidates: list[Path] = []
    for child in base_path.iterdir():
        if not child.is_dir():
            continue
        existing = {p.name for p in child.iterdir() if p.is_file()}
        if required_files.issubset(existing):
            candidates.append(child)

    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def is_world_initialized(base_path: Path, world_folder: Path | None) -> bool:
    folder = world_folder or resolve_latest_world_folder(base_path)
    if folder is None:
        return False
    existing = {p.name for p in folder.iterdir() if p.is_file()}
    return DEFAULT_REQUIRED_FILES.issubset(existing)


def read_world_json(world_folder: Path, file_name: str, fallback: Any) -> Any:
    file_path = world_folder / file_name
    if not file_path.exists():
        return fallback
    try:
        return json.loads(file_path.read_text(encoding="utf-8"))
    except Exception as exc:
        log.warning("Failed to read world context file {}: {}", file_path, exc)
        return fallback


def dump_logs(world_folder: Path, records: list[ChatRecord]) -> None:
    payload = [asdict(r) for r in records]
    (world_folder / "logs.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def restore_records_from_logs(world_folder: Path) -> list[ChatRecord]:
    logs_file = world_folder / "logs.json"
    if not logs_file.exists():
        return []

    try:
        payload = json.loads(logs_file.read_text(encoding="utf-8"))
    except Exception as exc:
        log.warning("Failed to restore logs.json from {}: {}", logs_file, exc)
        return []

    if not isinstance(payload, list):
        return []

    restored: list[ChatRecord] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "")).strip().lower()
        text = str(item.get("text", ""))
        ts = str(item.get("timestamp_utc", ""))
        if role not in {"user", "assistant"}:
            continue
        restored.append(ChatRecord(role=role, text=text, timestamp_utc=ts))
    return restored


def append_novel(world_folder: Path, text: str) -> None:
    """Append a narrative or user entry to novel.md, separated by blank lines."""
    cleaned = " ".join(text.splitlines()).strip()
    if not cleaned:
        return
    novel_path = world_folder / "novel.md"
    existing = ""
    if novel_path.exists():
        existing = novel_path.read_text(encoding="utf-8").rstrip()
    separator = "\n\n" if existing else ""
    novel_path.write_text(
        existing + separator + cleaned + "\n", encoding="utf-8"
    )


def archive_and_remove_world(base_path: Path, world_folder: Path) -> None:
    """Move novel.md to archive/ renamed as the world folder name, then delete the world folder."""
    novel_path = world_folder / "novel.md"
    if novel_path.exists():
        archive_dir = base_path / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        archived_name = world_folder.name + ".md"
        dest = archive_dir / archived_name
        # Avoid overwriting an existing archive.
        counter = 1
        while dest.exists():
            dest = archive_dir / f"{world_folder.name}_{counter}.md"
            counter += 1
        shutil.copy2(novel_path, dest)
        log.info("Archived novel to {}", dest)

    shutil.rmtree(world_folder, ignore_errors=True)
    log.info("Removed world folder {}", world_folder)


def safe_world_folder_name(title: str) -> str:
    cleaned = re.sub(r"[<>:\"/\\|?*\x00-\x1f]", "_", title).strip().rstrip(".")
    return cleaned or "world"


def parse_init_response(assistant_text: str) -> InitWorldData:
    text = assistant_text.strip()
    if not text:
        raise ValueError("Init response is empty")

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            raise ValueError("Init response does not contain valid JSON") from None
        payload = json.loads(match.group(0))

    if not isinstance(payload, dict):
        raise ValueError("Init response JSON root must be an object")

    worldview = payload.get("世界觀")
    if not isinstance(worldview, dict):
        raise ValueError("Init response missing 世界觀 object")

    title = str(worldview.get("標題", "")).strip()
    if not title:
        raise ValueError("Init response missing 世界觀.標題")

    skill_data = payload.get("技能")
    equipment_data = payload.get("裝備")
    item_data = payload.get("道具")

    system_data = payload.get("系統")
    if isinstance(system_data, dict):
        if skill_data is None:
            skill_data = system_data.get("技能")
        if equipment_data is None:
            equipment_data = system_data.get("裝備")
        if item_data is None:
            item_data = system_data.get("道具")

    return InitWorldData(
        world_title=title,
        background_story=str(worldview.get("背景", "")).strip(),
        quest_data=payload.get("任務", []),
        map_data=payload.get("地圖", {}),
        player_data=payload.get("玩家", {}),
        npc_data=payload.get("NPC", []),
        skill_data=skill_data if skill_data is not None else [],
        equipment_data=equipment_data if equipment_data is not None else [],
        item_data=item_data if item_data is not None else [],
    )


def export_init_world_files(base_path: Path, assistant_text: str) -> Path | None:
    try:
        world_data = parse_init_response(assistant_text)
    except Exception as exc:
        log.warning("Init world export skipped: {}", exc)
        return None

    world_folder = base_path / safe_world_folder_name(world_data.world_title)
    world_folder.mkdir(parents=True, exist_ok=True)

    files = {
        "novel.md": world_data.background_story,
        "quest.json": json.dumps(world_data.quest_data, ensure_ascii=False, indent=2),
        "map.json": json.dumps(world_data.map_data, ensure_ascii=False, indent=2),
        "player.json": json.dumps(world_data.player_data, ensure_ascii=False, indent=2),
        "npc.json": json.dumps(world_data.npc_data, ensure_ascii=False, indent=2),
        "skill.json": json.dumps(world_data.skill_data, ensure_ascii=False, indent=2),
        "equipment.json": json.dumps(world_data.equipment_data, ensure_ascii=False, indent=2),
        "item.json": json.dumps(world_data.item_data, ensure_ascii=False, indent=2),
    }
    for name, content in files.items():
        (world_folder / name).write_text(content, encoding="utf-8")

    log.info("Init world files exported to {}", world_folder)
    return world_folder
