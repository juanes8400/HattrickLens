from dataclasses import dataclass, field
from datetime import datetime

from app.domain.value_objects.skill import Age, Skill, SkillType


@dataclass(slots=True)
class Player:
    ht_player_id: int
    first_name: str
    last_name: str
    age: Age
    tsi: int
    form: int
    stamina: int
    experience: int
    salary: int
    specialty: int | None
    skills: dict[SkillType, Skill] = field(default_factory=dict)
    injury_level: int = -1  # -1 sano, 0 magullado (puede jugar), >=1 semanas de baja
    is_transfer_listed: bool = False
    captured_at: datetime | None = None

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def skill(self, t: SkillType) -> Skill:
        return self.skills.get(t, Skill(t, 0))
