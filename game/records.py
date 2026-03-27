from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ChatRecord:
    role: str
    text: str
    timestamp_utc: str


@dataclass
class InitWorldData:
    world_title: str
    background_story: str
    quest_data: Any
    map_data: Any
    player_data: Any
    npc_data: Any
    skill_data: Any
    equipment_data: Any
    item_data: Any
