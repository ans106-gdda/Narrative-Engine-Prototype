import json
import time
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from vesper import ledger
from vesper.agents import auditor, optioner
from vesper.schema import AuditResult, DialogueOption, Ledger, Patch

LOGS_DIR = Path(__file__).resolve().parent.parent / "logs"


class TurnResult(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    ledger: Ledger
    narration: str
    options: list[DialogueOption]
    patch: Patch
    audit: AuditResult
    retries: int
    diff: list[str]


def play_turn(L: Ledger, choice: DialogueOption | None, events: list[str]) -> TurnResult:
    narration, audit_result, retries = auditor.audited_narration(L, choice, events)

    if choice is not None:
        tag = ledger.declare_tag_for_chime(L) if choice.intent == "declare_position" else None
        patch = ledger.resolve_effects(L, choice.intent, choice.target, tag)
        L2 = ledger.apply_patch(L, patch)
    else:
        patch = Patch()
        L2 = L

    L2 = ledger.recompute_coherence(L2)
    options = optioner.generate_options(L2, narration)

    return TurnResult(
        ledger=L2,
        narration=narration,
        options=options,
        patch=patch,
        audit=audit_result,
        retries=retries,
        diff=ledger.diff(L, L2),
    )


def log_turn(session_path: Path, chime: int, player_input: str, chosen_intent: str,
             result: TurnResult) -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "chime": chime,
        "player_input": player_input,
        "chosen_intent": chosen_intent,
        "patch": result.patch.model_dump(),
        "diff": result.diff,
        "audit": result.audit.model_dump(),
        "retries": result.retries,
        "narration": result.narration,
        "ledger": result.ledger.model_dump(),
    }
    with session_path.open("a") as f:
        f.write(json.dumps(entry, default=str) + "\n")


def new_session_path() -> Path:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    ts = int(time.time())
    return LOGS_DIR / f"session_{ts}.jsonl"
