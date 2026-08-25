from vesper import ledger, llm, world
from vesper.schema import DialogueOption, Ledger, OptionSet

MAX_OPTIONS = 4

_UNTARGETED_ORDER = ["declare_position", "deflect", "confess"]


def _sort_key(L: Ledger, pair: tuple[str, str | None]):
    intent, target = pair
    has_mood = 0
    trust_abs = 0
    if target is not None:
        cand = L.candidates[target]
        has_mood = 0 if cand.emotional_state is not None else 1
        trust_abs = -abs(cand.trust)
    intent_order = list(world.INTENTS.keys()).index(intent)
    return (has_mood, trust_abs, intent_order)


def _select_pairs(L: Ledger) -> list[tuple[str, str | None]]:
    pairs = ledger.legal_intents(L)
    targeted = [p for p in pairs if p[1] is not None]
    untargeted = [p for p in pairs if p[1] is None]

    targeted.sort(key=lambda p: _sort_key(L, p))

    selected: list[tuple[str, str | None]] = []
    for p in targeted:
        if len(selected) >= MAX_OPTIONS:
            break
        selected.append(p)

    untargeted.sort(key=lambda p: _UNTARGETED_ORDER.index(p[0]) if p[0] in _UNTARGETED_ORDER else 999)
    for p in untargeted:
        if len(selected) >= MAX_OPTIONS:
            break
        selected.append(p)

    return selected[:MAX_OPTIONS]


def _fallback_options(pairs: list[tuple[str, str | None]]) -> list[DialogueOption]:
    options = []
    for intent, target in pairs:
        text = intent.replace("_", " ")
        if target:
            text += f" ({target})"
        options.append(DialogueOption(intent=intent, target=target, surface_text=text))
    return options


def generate_options(L: Ledger, narration: str) -> list[DialogueOption]:
    pairs = _select_pairs(L)
    if not pairs:
        return []

    pair_desc = [{"intent": i, "target": t} for i, t in pairs]
    candidate_state = {
        cid: {"trust": c.trust, "emotional_state": c.emotional_state.model_dump() if c.emotional_state else None}
        for cid, c in L.candidates.items()
    }

    system = (
        "You write short first-person dialogue lines for a player in an interactive narrative. "
        "You do not choose the player's moves; Python already chose them. "
        "For each of the given (intent, target) pairs, write a surface_text: what the player says or does, "
        "first person, at most 30 words, matching the intent."
    )
    user = (
        f"NARRATION:\n{narration}\n\n"
        f"SELECTED PAIRS (write exactly one option per pair, same order):\n{pair_desc}\n\n"
        f"CANDIDATE STATE:\n{candidate_state}"
    )

    def _try_once() -> list[DialogueOption]:
        result: OptionSet = llm.parse(system, user, OptionSet, max_tokens=4096)
        valid = []
        for opt in result.options:
            if (opt.intent, opt.target) in pairs:
                valid.append(opt)
        return valid

    valid = _try_once()
    if len(valid) < 2:
        valid = _try_once()
    if len(valid) < 2:
        return _fallback_options(pairs)

    return valid[:MAX_OPTIONS]
