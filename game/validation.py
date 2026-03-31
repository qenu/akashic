from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.valid


# ---------------------------------------------------------------------------
# Shared low-level checks
# ---------------------------------------------------------------------------


class _Rules:
    EQUIPMENT_CLASSES = {"武器", "防具", "飾品"}
    CHANGE_ACTIONS = {"add", "update", "remove"}
    CHANGE_TYPES = {"玩家", "任務", "NPC", "道具", "裝備", "技能", "地圖"}

    # Fields required when adding each type via a change entry.
    ADD_REQUIRED: dict[str, list[str]] = {
        "任務": ["id", "敘述", "進度"],
        "NPC": ["id", "名稱", "身分", "性格", "關係", "目標"],
        "技能": ["id", "名稱", "效果"],
        "裝備": ["id", "名稱", "分類", "用途"],
        "道具": ["id", "名稱", "用途", "數量"],
        "地圖": ["id", "名稱", "形容", "路徑"],
    }

    # Fields allowed when updating each type via a change entry.
    UPDATE_ALLOWED: dict[str, set[str]] = {
        "玩家": {"地點", "狀態", "身分"},
        "任務": {"敘述", "進度"},
        "NPC": {"身分", "性格", "關係", "目標"},
        "技能": {"效果"},
        "裝備": {"用途"},
        "道具": {"數量"},
        "地圖": {"形容", "路徑"},
    }

    @staticmethod
    def check_non_empty_string(value: Any, label: str, errors: list[str]) -> bool:
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{label} must be a non-empty string")
            return False
        return True

    @staticmethod
    def check_positive_int(value: Any, label: str, errors: list[str]) -> bool:
        if not isinstance(value, int) or value < 0:
            errors.append(f"{label} must be a non-negative integer")
            return False
        return True

    @staticmethod
    def check_list(value: Any, label: str, errors: list[str]) -> bool:
        if not isinstance(value, list):
            errors.append(f"{label} must be a list")
            return False
        return True

    @staticmethod
    def check_snakecase_id(value: Any, label: str, errors: list[str]) -> bool:
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{label} must be a non-empty string")
            return False
        if not all(c.isalnum() or c == "_" for c in value):
            errors.append(
                f"{label} must be snake_case (letters, digits, underscores only)"
            )
            return False
        return True


# ---------------------------------------------------------------------------
# Init payload validator  (init.md JSON structure)
# ---------------------------------------------------------------------------


class InitPayloadValidator:
    """Validates the full world-creation JSON produced by init.md."""

    MIN_MAP = 3
    MAX_MAP = 5
    MIN_NPC = 3
    MAX_NPC = 6
    MIN_SKILLS = 1
    MAX_SKILLS = 2
    MIN_EQUIPMENT = 1
    MAX_EQUIPMENT = 2
    MIN_ITEMS = 2
    MAX_ITEMS = 4
    MAX_ITEM_QUANTITY = 5

    def validate(self, payload: Any) -> ValidationResult:
        errors: list[str] = []

        if not isinstance(payload, dict):
            return ValidationResult(
                valid=False, errors=["Payload must be a JSON object"]
            )

        self._check_worldview(payload.get("世界觀"), errors)
        map_ids = self._check_map(payload.get("地圖"), errors)
        self._check_player(payload.get("玩家"), map_ids, errors)
        self._check_npcs(payload.get("NPC"), map_ids, errors)
        self._check_skills(payload.get("技能"), errors)
        self._check_equipment(payload.get("裝備"), errors)
        self._check_items(payload.get("道具"), errors)

        return ValidationResult(valid=len(errors) == 0, errors=errors)

    # ------------------------------------------------------------------

    def _check_worldview(self, wv: Any, errors: list[str]) -> None:
        if not isinstance(wv, dict):
            errors.append("世界觀 must be an object")
            return
        _Rules.check_non_empty_string(wv.get("標題"), "世界觀.標題", errors)
        _Rules.check_non_empty_string(wv.get("背景"), "世界觀.背景", errors)

    def _check_map(self, maps: Any, errors: list[str]) -> set[str]:
        """Validate map list and return the set of valid map IDs."""
        ids: set[str] = set()
        if not _Rules.check_list(maps, "地圖", errors):
            return ids
        count = len(maps)
        if not (self.MIN_MAP <= count <= self.MAX_MAP):
            errors.append(
                f"地圖 must have {self.MIN_MAP}–{self.MAX_MAP} entries, got {count}"
            )
        for i, entry in enumerate(maps):
            if not isinstance(entry, dict):
                errors.append(f"地圖[{i}] must be an object")
                continue
            label = f"地圖[{i}]"
            if _Rules.check_snakecase_id(entry.get("id"), f"{label}.id", errors):
                raw_id = entry["id"]
                if raw_id in ids:
                    errors.append(f"{label}.id '{raw_id}' is duplicated")
                else:
                    ids.add(raw_id)
            _Rules.check_non_empty_string(entry.get("名稱"), f"{label}.名稱", errors)
            _Rules.check_non_empty_string(entry.get("形容"), f"{label}.形容", errors)
            if not isinstance(entry.get("路徑"), list):
                errors.append(f"{label}.路徑 must be a list")
        return ids

    def _check_player(self, player: Any, map_ids: set[str], errors: list[str]) -> None:
        if not isinstance(player, dict):
            errors.append("玩家 must be an object")
            return
        location = player.get("地點")
        if not isinstance(location, str) or not location.strip():
            errors.append("玩家.地點 must be a non-empty string")
        elif map_ids and location not in map_ids:
            errors.append(f"玩家.地點 '{location}' is not a valid map id")

        status = player.get("狀態")
        if not isinstance(status, dict):
            errors.append("玩家.狀態 must be an object")
        else:
            for stat in ("生命", "消耗", "飽腹感"):
                val = status.get(stat)
                # Accept "100/100" strings (from the template) or plain ints/floats
                if isinstance(val, str):
                    parts = val.split("/")
                    if len(parts) != 2 or not all(p.strip().isdigit() for p in parts):
                        errors.append(
                            f"玩家.狀態.{stat} has invalid format '{val}'; expected int or 'n/n'"
                        )
                elif not isinstance(val, (int, float)) or val < 0:
                    errors.append(f"玩家.狀態.{stat} must be a non-negative number")

        _Rules.check_non_empty_string(player.get("消耗名稱"), "玩家.消耗名稱", errors)
        _Rules.check_non_empty_string(player.get("身分"), "玩家.身分", errors)

    def _check_npcs(self, npcs: Any, map_ids: set[str], errors: list[str]) -> None:
        if not _Rules.check_list(npcs, "NPC", errors):
            return
        count = len(npcs)
        if not (self.MIN_NPC <= count <= self.MAX_NPC):
            errors.append(
                f"NPC must have {self.MIN_NPC}–{self.MAX_NPC} entries, got {count}"
            )
        ids: set[str] = set()
        for i, npc in enumerate(npcs):
            if not isinstance(npc, dict):
                errors.append(f"NPC[{i}] must be an object")
                continue
            label = f"NPC[{i}]"
            if _Rules.check_snakecase_id(npc.get("id"), f"{label}.id", errors):
                raw_id = npc["id"]
                if raw_id in ids:
                    errors.append(f"{label}.id '{raw_id}' is duplicated")
                else:
                    ids.add(raw_id)
            for f in ("名稱", "身分", "性格", "關係", "目標"):
                _Rules.check_non_empty_string(npc.get(f), f"{label}.{f}", errors)
            loc = npc.get("地點")
            if not isinstance(loc, str) or not loc.strip():
                errors.append(f"{label}.地點 must be a non-empty string")
            elif map_ids and loc not in map_ids:
                errors.append(f"{label}.地點 '{loc}' is not a valid map id")

    def _check_skills(self, skills: Any, errors: list[str]) -> None:
        if not _Rules.check_list(skills, "技能", errors):
            return
        count = len(skills)
        if not (self.MIN_SKILLS <= count <= self.MAX_SKILLS):
            errors.append(
                f"技能 must have {self.MIN_SKILLS}–{self.MAX_SKILLS} entries, got {count}"
            )
        ids: set[str] = set()
        for i, skill in enumerate(skills):
            if not isinstance(skill, dict):
                errors.append(f"技能[{i}] must be an object")
                continue
            label = f"技能[{i}]"
            if _Rules.check_snakecase_id(skill.get("id"), f"{label}.id", errors):
                raw_id = skill["id"]
                if raw_id in ids:
                    errors.append(f"{label}.id '{raw_id}' is duplicated")
                else:
                    ids.add(raw_id)
            _Rules.check_non_empty_string(skill.get("名稱"), f"{label}.名稱", errors)
            _Rules.check_non_empty_string(skill.get("效果"), f"{label}.效果", errors)

    def _check_equipment(self, equipment: Any, errors: list[str]) -> None:
        if not _Rules.check_list(equipment, "裝備", errors):
            return
        count = len(equipment)
        if not (self.MIN_EQUIPMENT <= count <= self.MAX_EQUIPMENT):
            errors.append(
                f"裝備 must have {self.MIN_EQUIPMENT}–{self.MAX_EQUIPMENT} entries, got {count}"
            )
        ids: set[str] = set()
        classes_seen: set[str] = set()
        for i, eq in enumerate(equipment):
            if not isinstance(eq, dict):
                errors.append(f"裝備[{i}] must be an object")
                continue
            label = f"裝備[{i}]"
            if _Rules.check_snakecase_id(eq.get("id"), f"{label}.id", errors):
                raw_id = eq["id"]
                if raw_id in ids:
                    errors.append(f"{label}.id '{raw_id}' is duplicated")
                else:
                    ids.add(raw_id)
            _Rules.check_non_empty_string(eq.get("名稱"), f"{label}.名稱", errors)
            _Rules.check_non_empty_string(eq.get("用途"), f"{label}.用途", errors)
            cls = eq.get("分類")
            if cls not in _Rules.EQUIPMENT_CLASSES:
                errors.append(
                    f"{label}.分類 must be one of {_Rules.EQUIPMENT_CLASSES}, got '{cls}'"
                )
            elif cls in classes_seen:
                errors.append(
                    f"{label}.分類 '{cls}' duplicates an existing equipment class"
                )
            else:
                classes_seen.add(cls)

    def _check_items(self, items: Any, errors: list[str]) -> None:
        if not _Rules.check_list(items, "道具", errors):
            return
        count = len(items)
        if not (self.MIN_ITEMS <= count <= self.MAX_ITEMS):
            errors.append(
                f"道具 must have {self.MIN_ITEMS}–{self.MAX_ITEMS} entries, got {count}"
            )
        ids: set[str] = set()
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                errors.append(f"道具[{i}] must be an object")
                continue
            label = f"道具[{i}]"
            if _Rules.check_snakecase_id(item.get("id"), f"{label}.id", errors):
                raw_id = item["id"]
                if raw_id in ids:
                    errors.append(f"{label}.id '{raw_id}' is duplicated")
                else:
                    ids.add(raw_id)
            _Rules.check_non_empty_string(item.get("名稱"), f"{label}.名稱", errors)
            _Rules.check_non_empty_string(item.get("用途"), f"{label}.用途", errors)
            qty = item.get("數量")
            if not isinstance(qty, int) or qty < 0:
                errors.append(f"{label}.數量 must be a non-negative integer")
            elif qty > self.MAX_ITEM_QUANTITY:
                errors.append(
                    f"{label}.數量 must not exceed {self.MAX_ITEM_QUANTITY}, got {qty}"
                )


# ---------------------------------------------------------------------------
# Change entry validator  (system.md changes protocol)
# ---------------------------------------------------------------------------


class ChangeEntryValidator:
    """Validates a single change entry from the assistant's changes array."""

    def validate(self, entry: Any) -> ValidationResult:
        errors: list[str] = []

        if not isinstance(entry, dict):
            return ValidationResult(
                valid=False, errors=["Change entry must be a JSON object"]
            )

        action = str(entry.get("action", "")).strip().lower()
        raw_type = str(entry.get("type", "")).strip()
        entry_id = str(entry.get("id", "")).strip()

        if action not in _Rules.CHANGE_ACTIONS:
            errors.append(
                f"action must be one of {_Rules.CHANGE_ACTIONS}, got '{action}'"
            )
        if raw_type not in _Rules.CHANGE_TYPES:
            errors.append(
                f"type must be one of {_Rules.CHANGE_TYPES}, got '{raw_type}'"
            )
        _Rules.check_snakecase_id(entry_id, "id", errors)

        if errors:
            # Cannot proceed with type-specific checks without valid action/type/id
            return ValidationResult(valid=False, errors=errors)

        if action == "add":
            self._check_add(raw_type, entry, errors)
        elif action == "update":
            self._check_update(raw_type, entry, errors)
        # remove needs no additional field checks

        return ValidationResult(valid=len(errors) == 0, errors=errors)

    def _check_add(self, type_name: str, entry: dict, errors: list[str]) -> None:
        data = entry.get("data")
        if not isinstance(data, dict):
            errors.append("add entry must have a 'data' object")
            return

        required = _Rules.ADD_REQUIRED.get(type_name, [])
        for f in required:
            if f == "id":
                continue  # id is on the entry root
            if f not in data:
                errors.append(f"add '{type_name}' missing required field '{f}' in data")
                continue
            if f == "數量":
                if not isinstance(data[f], int) or data[f] < 0:
                    errors.append(f"data.數量 must be a non-negative integer")
            elif f == "路徑":
                if not isinstance(data[f], list):
                    errors.append(f"data.路徑 must be a list")
            elif f == "分類":
                if data[f] not in _Rules.EQUIPMENT_CLASSES:
                    errors.append(
                        f"data.分類 must be one of {_Rules.EQUIPMENT_CLASSES}"
                    )
            else:
                _Rules.check_non_empty_string(data.get(f), f"data.{f}", errors)

    def _check_update(self, type_name: str, entry: dict, errors: list[str]) -> None:
        changes = entry.get("changes")
        if not isinstance(changes, dict):
            errors.append("update entry must have a 'changes' object")
            return

        allowed = _Rules.UPDATE_ALLOWED.get(type_name)
        if allowed is None:
            return  # no restrictions defined

        unknown = set(changes.keys()) - allowed
        if unknown:
            errors.append(f"update '{type_name}' contains disallowed fields: {unknown}")

        # Specific value checks
        if "數量" in changes:
            if not isinstance(changes["數量"], int) or changes["數量"] < 0:
                errors.append("changes.數量 must be a non-negative integer")
        if "狀態" in changes and isinstance(changes["狀態"], dict):
            for stat, val in changes["狀態"].items():
                if not isinstance(val, (int, float)) or val < 0:
                    errors.append(f"changes.狀態.{stat} must be a non-negative number")
