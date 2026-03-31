from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app_logger import AppLogger
from game.world_io import read_world_json
from game.validation import _Rules

log = AppLogger.get_logger("changes")

# Maps the Chinese type names from the API to (json filename, storage kind).
# "dict" means the file is a single object (player.json).
# "list" means the file is an array of objects keyed by "id".
_TYPE_MAP: dict[str, tuple[str, str]] = {
    "玩家": ("player.json", "dict"),  "player": ("player.json", "dict"),
    "任務": ("quest.json", "list"),   "quest":  ("quest.json", "list"),
    "NPC":  ("npc.json", "list"),     "npc":    ("npc.json", "list"),
    "道具": ("item.json", "list"),    "item":   ("item.json", "list"),
    "裝備": ("equipment.json", "list"), "equipment": ("equipment.json", "list"),
    "技能": ("skill.json", "list"),   "skill":  ("skill.json", "list"),
    "地圖": ("map.json", "list"),     "map":    ("map.json", "list"),
}

# Maps English aliases back to the canonical Chinese key used in _ADD_REQUIRED / _UPDATE_ALLOWED.
_CANONICAL_TYPE: dict[str, str] = {
    "player": "玩家", "quest": "任務", "npc": "NPC",
    "item": "道具", "equipment": "裝備", "skill": "技能", "map": "地圖",
}

# Which fields are required/allowed for add/update per type are centralised in
# game.validation._Rules.  Do not duplicate them here.


def apply_changes(world_folder: Path, changes: list[dict[str, Any]]) -> None:
    """Validate and apply a list of change entries to world JSON files."""
    if not changes:
        return

    # Track IDs removed in this batch to catch remove-then-update.
    removed_ids: set[str] = set()

    for entry in changes:
        if not isinstance(entry, dict):
            log.warning("Skipping non-dict change entry: {}", entry)
            continue
        try:
            _apply_single(world_folder, entry, removed_ids)
        except Exception as exc:
            log.warning("Change rejected: {} — {}", entry, exc)


def _apply_single(
    world_folder: Path,
    entry: dict[str, Any],
    removed_ids: set[str],
) -> None:
    action = _normalise_action(entry.get("action", ""))
    raw_type = str(entry.get("type", "")).strip()
    normalised = raw_type if raw_type in _TYPE_MAP else raw_type.lower()
    type_name = _CANONICAL_TYPE.get(normalised, normalised)
    entry_id = str(entry.get("id", "")).strip()

    if not action:
        raise ValueError(f"missing or invalid action: {entry.get('action')}")
    if not type_name or type_name not in _TYPE_MAP:
        raise ValueError(f"unknown type: {raw_type}")
    if not entry_id:
        raise ValueError("missing id")

    file_name, kind = _TYPE_MAP[type_name]

    if action == "update" and entry_id in removed_ids:
        raise ValueError(f"cannot update '{entry_id}' after removing it in the same turn")

    if kind == "dict":
        _apply_dict(world_folder, file_name, type_name, action, entry_id, entry)
    else:
        _apply_list(world_folder, file_name, type_name, action, entry_id, entry, removed_ids)


def _normalise_action(raw: Any) -> str:
    value = str(raw).strip().lower()
    if value in _Rules.CHANGE_ACTIONS:
        return value
    return ""


# ------------------------------------------------------------------
# Dict-type file (player.json)
# ------------------------------------------------------------------

def _apply_dict(
    world_folder: Path,
    file_name: str,
    type_name: str,
    action: str,
    entry_id: str,
    entry: dict[str, Any],
) -> None:
    data = read_world_json(world_folder, file_name, {})
    if not isinstance(data, dict):
        data = {}

    if action == "remove":
        log.warning("Cannot remove player object; ignoring")
        return

    if action == "add":
        log.warning("Cannot add to player object; treating as update")

    changes_payload = entry.get("changes") or entry.get("data") or {}
    if not isinstance(changes_payload, dict):
        raise ValueError("changes/data must be a dict")

    allowed = _Rules.UPDATE_ALLOWED.get(type_name)
    if allowed:
        changes_payload = {k: v for k, v in changes_payload.items() if k in allowed}

    _clamp_negatives(changes_payload)

    # Deep-merge status fields.
    for key, value in changes_payload.items():
        if key == "狀態" and isinstance(value, dict) and isinstance(data.get("狀態"), dict):
            data["狀態"].update(value)
            _clamp_negatives(data["狀態"])
        else:
            data[key] = value

    _write_json(world_folder, file_name, data)
    log.info("Applied {} on {} (player)", action, type_name)


# ------------------------------------------------------------------
# List-type files (quest, npc, item, etc.)
# ------------------------------------------------------------------

def _apply_list(
    world_folder: Path,
    file_name: str,
    type_name: str,
    action: str,
    entry_id: str,
    entry: dict[str, Any],
    removed_ids: set[str],
) -> None:
    data = read_world_json(world_folder, file_name, [])
    if not isinstance(data, list):
        data = []

    existing_idx = _find_by_id(data, entry_id)

    if action == "add":
        if existing_idx is not None:
            log.warning("ID '{}' already exists in {}; treating add as update", entry_id, file_name)
            _do_update(data, existing_idx, type_name, entry)
        else:
            _do_add(data, type_name, entry_id, entry)

    elif action == "update":
        if existing_idx is None:
            log.warning("ID '{}' not found in {} for update; treating as add", entry_id, file_name)
            _do_add(data, type_name, entry_id, entry)
        else:
            _do_update(data, existing_idx, type_name, entry)
            # Auto-remove items whose quantity has dropped to zero.
            if type_name in ("道具", "item"):
                updated = data[existing_idx]
                if isinstance(updated, dict) and int(updated.get("數量", -1)) == 0:
                    data.pop(existing_idx)
                    removed_ids.add(entry_id)
                    log.info("Auto-removed {} id='{}' (數量 reached 0)", type_name, entry_id)

    elif action == "remove":
        if existing_idx is not None:
            data.pop(existing_idx)
            removed_ids.add(entry_id)
        else:
            log.warning("ID '{}' not found in {} for remove; ignoring", entry_id, file_name)
            return

    _write_json(world_folder, file_name, data)
    log.info("Applied {} on {} id='{}' in {}", action, type_name, entry_id, file_name)


def _do_add(
    data: list[Any],
    type_name: str,
    entry_id: str,
    entry: dict[str, Any],
) -> None:
    new_obj = entry.get("data") or entry.get("changes") or {}
    if not isinstance(new_obj, dict):
        raise ValueError("data must be a dict for add")

    new_obj["id"] = entry_id

    # Fill missing required fields with empty defaults.
    required = _Rules.ADD_REQUIRED.get(type_name, [])
    for field in required:
        if field not in new_obj:
            new_obj[field] = 0 if field == "數量" else ""

    _coerce_quantity(new_obj)
    _clamp_negatives(new_obj)
    data.append(new_obj)


def _do_update(
    data: list[Any],
    idx: int,
    type_name: str,
    entry: dict[str, Any],
) -> None:
    changes_payload = entry.get("changes") or entry.get("data") or {}
    if not isinstance(changes_payload, dict):
        raise ValueError("changes must be a dict for update")

    allowed = _Rules.UPDATE_ALLOWED.get(type_name)
    if allowed:
        changes_payload = {k: v for k, v in changes_payload.items() if k in allowed}

    _coerce_quantity(changes_payload)
    _clamp_negatives(changes_payload)

    existing = data[idx]
    if isinstance(existing, dict):
        existing.update(changes_payload)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _find_by_id(data: list[Any], entry_id: str) -> int | None:
    for i, item in enumerate(data):
        if isinstance(item, dict) and str(item.get("id", "")) == entry_id:
            return i
    return None


def _coerce_quantity(obj: dict[str, Any]) -> None:
    """Ensure 數量 is an integer if present."""
    if "數量" in obj:
        try:
            obj["數量"] = int(obj["數量"])
        except (ValueError, TypeError):
            obj["數量"] = 0


def _clamp_negatives(obj: dict[str, Any]) -> None:
    """Clamp any numeric values to >= 0."""
    for key, value in obj.items():
        if isinstance(value, (int, float)) and value < 0:
            obj[key] = 0


def _write_json(world_folder: Path, file_name: str, data: Any) -> None:
    path = world_folder / file_name
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
