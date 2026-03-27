from __future__ import annotations

import json
import re
from typing import Any


def extract_json(text: str) -> Any:
    """Extract a JSON object from text, tolerating wrapper content."""
    stripped = text.strip()
    if not stripped:
        return None

    try:
        return json.loads(stripped)
    except Exception:
        match = re.search(r"\{[\s\S]*\}", stripped)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except Exception:
            return None


def pick_first_text(payload: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, list):
            parts = [str(item).strip() for item in value if str(item).strip()]
            if parts:
                return "\n".join(parts)
    return ""


def pick_options(payload: dict[str, Any], keys: list[str]) -> list[str]:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            options = [str(item).strip() for item in value if str(item).strip()]
            if options:
                return options
        if isinstance(value, dict):
            options = [
                str(item).strip()
                for item in value.values()
                if isinstance(item, str) and item.strip()
            ]
            if options:
                return options
        if isinstance(value, str) and value.strip():
            return [value.strip()]
    return []


def iter_nested_dicts(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from iter_nested_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_nested_dicts(child)


def extract_narrative_and_options(payload: dict[str, Any]) -> tuple[str, list[str]]:
    narrative = pick_first_text(payload, NARRATIVE_KEYS)
    options = pick_options(payload, OPTION_KEYS)

    if narrative and options:
        return narrative, options

    for nested in iter_nested_dicts(payload):
        if not narrative:
            narrative = pick_first_text(nested, NARRATIVE_KEYS)
        if not options:
            options = pick_options(nested, OPTION_KEYS)
        if narrative and options:
            break

    return narrative, options


def extract_options_from_text(text: str) -> list[str]:
    marker = "選項:"
    alt_marker = "Options:"
    segment = ""

    if marker in text:
        segment = text.split(marker, 1)[1]
    elif alt_marker in text:
        segment = text.split(alt_marker, 1)[1]
    else:
        return []

    parsed: list[str] = []
    for raw_line in segment.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = re.match(r"^\d+[\.)]?\s*(.+)$", line)
        parsed.append((match.group(1) if match else line).strip())

    return [item for item in parsed if item]


def condense_assistant_text(assistant_text: str) -> str:
    """Strip an assistant message to narrative + summary only (for API history)."""
    payload = extract_json(assistant_text)
    if not isinstance(payload, dict):
        return assistant_text

    narrative = pick_first_text(payload, NARRATIVE_KEYS)
    summary = pick_first_text(payload, SUMMARY_KEYS)

    if not narrative and not summary:
        for nested in iter_nested_dicts(payload):
            if not narrative:
                narrative = pick_first_text(nested, NARRATIVE_KEYS)
            if not summary:
                summary = pick_first_text(nested, SUMMARY_KEYS)
            if narrative and summary:
                break

    parts: list[str] = []
    if narrative:
        parts.append(narrative)
    if summary:
        parts.append(summary)
    return "\n\n".join(parts) if parts else assistant_text


NARRATIVE_KEYS: list[str] = ["敘事", "narrative", "故事", "內容", "text", "描述", "message"]
OPTION_KEYS: list[str] = ["選項", "options", "actions", "可選行動"]
SUMMARY_KEYS: list[str] = ["摘要", "summary"]

# -----------------------------------------------------------------------
# World-changes display
# -----------------------------------------------------------------------

_CHANGE_PRIORITY: dict[str, int] = {
    "任務": 0, "quest": 0,
    "裝備": 1, "equipment": 1,
    "技能": 2, "skill": 2,
    "道具": 3, "item": 3,
    "玩家": 4, "player": 4,
}

_CHANGE_CANONICAL: dict[str, str] = {
    "quest": "任務", "equipment": "裝備", "skill": "技能",
    "item": "道具", "player": "玩家", "npc": "NPC", "map": "地圖",
}


def format_changes_lines(
    changes: list[Any],
    old_player: Any = None,
    new_player: Any = None,
    old_items: Any = None,
    new_items: Any = None,
    map_data: Any = None,
    quest_data: Any = None,
) -> list[str]:
    """Format a list of world change entries into human-readable display lines."""
    if not changes:
        return []

    buckets: list[tuple[int, str, dict]] = []
    for entry in changes:
        if not isinstance(entry, dict):
            continue
        raw = str(entry.get("type", "")).strip()
        canonical = _CHANGE_CANONICAL.get(raw.lower(), raw)
        priority = _CHANGE_PRIORITY.get(canonical, 99)
        buckets.append((priority, canonical, entry))

    buckets.sort(key=lambda x: x[0])

    lines: list[str] = []
    for _, type_name, entry in buckets:
        action = str(entry.get("action", "")).strip().lower()
        lines.extend(_format_single_change(
            type_name, action, entry, old_player, new_player, old_items, new_items, map_data, quest_data
        ))
    return lines


def _get_str(d: Any, key: str) -> str:
    if isinstance(d, dict):
        v = d.get(key, "")
        return str(v).strip() if v is not None else ""
    return ""


def _find_item_in_list(items: Any, entry_id: str) -> "dict | None":
    if not isinstance(items, list):
        return None
    for item in items:
        if isinstance(item, dict) and str(item.get("id", "")).strip() == entry_id:
            return item
    return None


def _find_quest_name(entry_id: str, quest_data: Any) -> str:
    """Look up a quest's display name from quest.json by its id."""
    if not isinstance(quest_data, list) or not entry_id:
        return entry_id
    for quest in quest_data:
        if isinstance(quest, dict) and str(quest.get("id", "")).strip() == entry_id:
            name = str(quest.get("名稱", "")).strip()
            return name if name else entry_id
    return entry_id


def _format_single_change(
    type_name: str,
    action: str,
    entry: dict,
    old_player: Any,
    new_player: Any,
    old_items: Any,
    new_items: Any,
    map_data: Any,
    quest_data: Any = None,
) -> list[str]:
    data = entry.get("data") or entry.get("changes") or {}
    if not isinstance(data, dict):
        data = {}
    entry_id = str(entry.get("id", "")).strip()

    if type_name == "任務":
        desc = _get_str(data, "名稱") or _get_str(data, "敘述") or _find_quest_name(entry_id, quest_data)
        progress = _get_str(data, "進度")
        if action == "add":
            return [f"接受任務 - {desc}"]
        if action == "update":
            return [f"{desc} ({progress})"] if progress else [f"{desc}"]
        if action == "remove":
            return [f"完成任務 - {desc}"]

    elif type_name == "裝備":
        name = _get_str(data, "名稱") or entry_id
        usage = _get_str(data, "用途")
        if action == "add":
            return [f"獲得裝備 - {name}: {usage}"] if usage else [f"獲得裝備 - {name}"]
        if action == "remove":
            return [f"失去裝備 - {name}"]

    elif type_name == "技能":
        name = _get_str(data, "名稱") or entry_id
        effect = _get_str(data, "效果")
        if action == "add":
            return [f"習得技能 - {name}: {effect}"] if effect else [f"習得技能 - {name}"]
        if action == "update":
            return [f"技能修正 - {name}: {effect}"] if effect else [f"技能修正 - {name}"]

    elif type_name == "道具":
        name = _get_str(data, "名稱")
        if not name:
            fallback = _find_item_in_list(old_items, entry_id) or _find_item_in_list(new_items, entry_id)
            name = _get_str(fallback, "名稱") or entry_id
        usage = _get_str(data, "用途")

        if action == "add":
            qty = data.get("數量")
            base = f"獲得道具 - {name}"
            if usage:
                base += f": {usage}"
            if qty is not None:
                base += f" x{qty}"
            return [base]

        if action == "update":
            old_item = _find_item_in_list(old_items, entry_id)
            new_item = _find_item_in_list(new_items, entry_id)
            if old_item and new_item:
                try:
                    old_qty = int(old_item.get("數量", 0))
                    new_qty = int(new_item.get("數量", 0))
                    diff = new_qty - old_qty
                    if diff > 0:
                        return [f"獲得道具 - {name} x{diff}"]
                    if diff < 0:
                        return [f"失去道具 - {name} x{-diff}"]
                    return []
                except (ValueError, TypeError):
                    pass
            qty = data.get("數量")
            return [f"獲得道具 - {name} x{qty}"] if qty is not None else []

        if action == "remove":
            old_item = _find_item_in_list(old_items, entry_id)
            base = f"失去道具 - {name}"
            if old_item:
                try:
                    base += f" x{int(old_item.get('數量', 0))}"
                except (ValueError, TypeError):
                    pass
            return [base]

    elif type_name == "玩家":
        return _format_player_change(data, old_player, new_player, map_data)

    return []


def _format_player_change(
    changes_data: dict,
    old_player: Any,
    new_player: Any,
    map_data: Any,
) -> list[str]:
    if old_player is None and new_player is None:
        return []
    old_p = old_player if isinstance(old_player, dict) else {}
    new_p = new_player if isinstance(new_player, dict) else {}
    lines: list[str] = []

    new_loc = changes_data.get("地點")
    if new_loc is not None:
        old_loc = str(old_p.get("地點", "")).strip()
        new_loc_str = str(new_loc).strip()
        old_name = _resolve_map_name(old_loc, map_data) if old_loc else "?"
        new_name = _resolve_map_name(new_loc_str, map_data)
        lines.append(f"移動 {old_name} -> {new_name}")

    new_identity = changes_data.get("身分")
    if new_identity is not None:
        old_identity = str(old_p.get("身分", "")).strip()
        new_identity_str = str(new_identity).strip()
        if old_identity != new_identity_str:
            lines.append(f"身分 {old_identity} -> {new_identity_str}")

    status_changes = changes_data.get("狀態")
    if isinstance(status_changes, dict):
        old_status = old_p.get("狀態", {}) if isinstance(old_p.get("狀態"), dict) else {}
        new_status = new_p.get("狀態", {}) if isinstance(new_p.get("狀態"), dict) else {}
        consumable_name = str((old_p or new_p).get("消耗名稱", "")).strip()
        for field, _ in status_changes.items():
            old_val = old_status.get(field, "?")
            new_val = new_status.get(field, "?")
            label = consumable_name if field == "消耗" and consumable_name else field
            lines.append(f"{label} {old_val} -> {new_val}")

    return lines


def format_player_status_line(player_data: Any, item_data: Any = None, map_data: Any = None) -> str:
    """Build a one-line player status string from player.json data.

    Order: 生命 | 消耗名稱: 消耗 | 飽腹感 | 身分 | 地點
    消耗名稱 is the world-specific label (e.g. 靈氣, 魔力) stored at the top level;
    its value comes from 狀態.消耗.
    地點 is resolved to the map entry's 名稱 when map_data is provided.
    """
    if not isinstance(player_data, dict):
        return ""

    parts: list[str] = []
    status = player_data.get("狀態", {}) if isinstance(player_data.get("狀態"), dict) else {}

    hp = status.get("生命") if status else player_data.get("生命")
    if hp is not None:
        parts.append(f"生命: {hp}")

    consumable_value = status.get("消耗")
    consumable_name = str(player_data.get("消耗名稱", "")).strip()
    if consumable_value is not None and consumable_name:
        parts.append(f"{consumable_name}: {consumable_value}")

    fullness = status.get("飽腹感") if status else player_data.get("飽腹感")
    if fullness is not None:
        parts.append(f"飽腹感: {fullness}")

    identity = str(player_data.get("身分", "")).strip()
    if identity:
        parts.append(f"身分: {identity}")

    location_id = str(player_data.get("地點", "")).strip()
    if location_id:
        location_name = _resolve_map_name(location_id, map_data)
        parts.append(f"地點: {location_name}")

    return " | ".join(parts)


def _resolve_map_name(location_id: str, map_data: Any) -> str:
    """Return the map entry's 名稱 matching location_id, or fall back to the id itself."""
    if not isinstance(map_data, list):
        if isinstance(map_data, dict):
            regions = map_data.get("主要地區")
            if isinstance(regions, list):
                map_data = regions
            else:
                return location_id
        else:
            return location_id

    target = location_id.strip().lower()
    for entry in map_data:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("id", "")).strip().lower() == target:
            name = str(entry.get("名稱", "")).strip()
            return name if name else location_id
    return location_id


def assistant_chat_payload(
    assistant_text: str,
    player_data: Any = None,
    item_data: Any = None,
    map_data: Any = None,
) -> tuple[str, str, list[str]]:
    """Return (narrative_text, status_line, options).

    narrative_text  – story prose only (no options appended).
    status_line     – player stats string for a separate mono label; empty if unavailable.
    options         – list of option strings (UI builds the display text).
    """
    payload = extract_json(assistant_text)
    if not isinstance(payload, dict):
        return assistant_text, "", extract_options_from_text(assistant_text)

    if "世界觀" in payload:
        worldview = payload.get("世界觀") or {}
        bg = str(worldview.get("背景", "")).strip() if isinstance(worldview, dict) else ""
        return bg or "World builder complete.", "", []

    narrative, options = extract_narrative_and_options(payload)

    status_line = ""
    if player_data is not None:
        status_line = format_player_status_line(player_data, item_data, map_data)

    return narrative or "No narrative provided.", status_line, options
