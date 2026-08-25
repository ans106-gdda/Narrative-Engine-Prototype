from typing import Literal

from pydantic import BaseModel, ConfigDict


class EmotionalState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mood: str
    cause: str
    decays_at_chime: int


class Candidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    trust: int = 0
    alive: bool = True
    emotional_state: EmotionalState | None = None
    believes_about_player: list[str] = []
    knows_secrets: list[str] = []
    shared_secret_with_player: bool = False


class StatedPosition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim: str
    tag: str
    chime: int
    audience: list[str]


class Rumor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fact: str
    true: bool
    origin_chime: int
    spread_by: str
    known_by: list[str]
    reaches_vesper_at: int
    vesper_delta: int
    applied: bool = False


class PlotThread(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    state: Literal["open", "escalating", "resolved"]
    revealed_to_player: bool
    dormant_for: int = 0


class Player(BaseModel):
    model_config = ConfigDict(extra="forbid")

    standing_with_vesper: int = 0
    coherence_score: float = 1.0
    stated_positions: list[StatedPosition] = []
    contradictions_committed: int = 0
    secrets_held: list[str] = []


class Violation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule: str
    quote: str
    explanation: str


class Ledger(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chime: int = 1
    chimes_until_dawn: int = 5
    player: Player = Player()
    candidates: dict[str, Candidate]
    rumor_network: list[Rumor] = []
    plot_threads: list[PlotThread] = []
    immutable_canon: list[str] = []
    contradiction_log: list[Violation] = []


class Op(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal[
        "trust_delta", "set_mood", "add_belief", "learn_secret",
        "add_rumor", "add_position", "advance_thread",
        "reveal_thread", "standing_delta", "add_canon",
    ]
    target: str | None = None
    value: dict


class Patch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ops: list[Op] = []
    note: str = ""


class DialogueOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: str
    target: str | None
    surface_text: str


class OptionSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    options: list[DialogueOption]


class ExtractedIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: str
    target: str | None
    tag: str | None
    confidence: float


class AuditResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    consistent: bool
    violations: list[Violation] = []
