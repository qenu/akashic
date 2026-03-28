from __future__ import annotations

from pathlib import Path
from typing import Any

from game.records import ChatRecord
from game.world_io import read_world_json, read_summary
from game.parsing import extract_json, NARRATIVE_KEYS, OPTION_KEYS, pick_first_text, pick_options


def build_runtime_context(
    world_folder: Path, records: list[ChatRecord]
) -> dict[str, Any]:
    player_data = read_world_json(world_folder, "player.json", {})
    quest_data = read_world_json(world_folder, "quest.json", [])
    map_data = read_world_json(world_folder, "map.json", {})
    npc_data = read_world_json(world_folder, "npc.json", [])
    item_data = read_world_json(world_folder, "item.json", [])
    skill_data = read_world_json(world_folder, "skill.json", [])

    location_id = _extract_location_id(player_data)
    related_map = _filter_map_by_location(map_data, location_id)
    related_npc = _filter_list_by_location(npc_data, location_id)

    mention_text = _build_reference_scan_text(records)
    mentioned_items = _select_named_entries_by_reference(item_data, mention_text)
    summary = read_summary(world_folder)

    return {
        "player": player_data,
        "quest": quest_data,
        "location_id": location_id,
        "map": related_map,
        "npc": related_npc,
        "item": mentioned_items,
        "skill": skill_data,
        "summary": summary,
    }


def _extract_location_id(player_data: Any) -> str:
    if not isinstance(player_data, dict):
        return ""
    for key in ("地點", "初始地點", "location", "location_id"):
        value = player_data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _contains_location(value: Any, location_id: str) -> bool:
    if not location_id:
        return False
    target = location_id.strip().lower()
    if isinstance(value, str):
        text = value.strip().lower()
        return (text == target) or (target in text)
    if isinstance(value, list):
        return any(_contains_location(item, location_id) for item in value)
    if isinstance(value, dict):
        return any(_contains_location(item, location_id) for item in value.values())
    return False


def _filter_map_by_location(map_data: Any, location_id: str) -> Any:
    if not location_id:
        return map_data

    # map.json can be a list of map entries or a dict with "主要地區".
    if isinstance(map_data, list):
        filtered = [m for m in map_data if _contains_location(m, location_id)]
        return filtered if filtered else map_data

    if not isinstance(map_data, dict):
        return map_data

    regions = map_data.get("主要地區")
    if isinstance(regions, list):
        filtered = [r for r in regions if _contains_location(r, location_id)]
        if filtered:
            result = dict(map_data)
            result["主要地區"] = filtered
            return result

    if _contains_location(map_data, location_id):
        return map_data
    return {}


def _filter_list_by_location(values: Any, location_id: str) -> Any:
    if not location_id:
        return values
    if not isinstance(values, list):
        return values
    return [item for item in values if _contains_location(item, location_id)]


def _build_reference_scan_text(records: list[ChatRecord]) -> str:
    chunks: list[str] = []
    for record in records:
        text = record.text.strip()
        if not text:
            continue
        if record.role == "assistant":
            payload = extract_json(text)
            if isinstance(payload, dict):
                narrative = pick_first_text(payload, NARRATIVE_KEYS)
                options = pick_options(payload, OPTION_KEYS)
                if narrative:
                    chunks.append(narrative)
                if options:
                    chunks.extend(options)
                continue
        chunks.append(text)
    return "\n".join(chunks).lower()



def _extract_entry_name(entry: Any) -> str:
    if isinstance(entry, dict):
        for key in ("名稱", "name", "標題", "title"):
            value = entry.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    if isinstance(entry, str):
        return entry.strip()
    return ""


def _select_named_entries_by_reference(
    entries: Any, mention_text: str
) -> list[Any]:
    if not isinstance(entries, list):
        return []
    selected: list[Any] = []
    for entry in entries:
        name = _extract_entry_name(entry)
        if not name:
            continue
        if name.lower() in mention_text:
            selected.append(entry)
    return selected
