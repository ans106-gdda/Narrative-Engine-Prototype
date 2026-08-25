from vesper import ledger, llm, world
from vesper.schema import DialogueOption, Ledger, Violation

HARD_RULES = [
    "Never reveal a plot_thread whose revealed_to_player is false.",
    "Never contradict immutable_canon.",
    "A candidate whose alive is false does not speak or act.",
    "Tone toward the player is governed by trust: <= -3 hostile, -2..0 guarded, 1..2 warm, >= 3 confiding.",
    "emotional_state overrides trust for this turn only.",
    "Reference at least one open plot thread or one stated_position.",
    "Do not invent numbers, dates, or names not present in the ledger or the canon.",
    "Write 120-200 words. Second person, present tense. No dice, no stats, no menus.",
]


def _build_system(L: Ledger) -> str:
    parts = [
        "You are the Dungeon Master for The Vesper Contract. You narrate; you never decide facts.",
        L.model_dump_json(indent=2),
        "FACTS THAT CAN NEVER BE CONTRADICTED\n" + "\n".join(world.IMMUTABLE_CANON),
        "HARD RULES\n" + "\n".join(HARD_RULES),
    ]

    dormant = ledger.dormant_thread(L)
    if dormant is not None:
        parts.append(f"Push this thread forward: {dormant.id}")

    return "\n\n".join(parts)


def narrate(
    L: Ledger,
    chosen: DialogueOption | None,
    events: list[str],
    violations: list[Violation] | None = None,
) -> str:
    system = _build_system(L)

    if violations is not None:
        system += f"\n\nYour previous attempt was rejected. Fix these and rewrite: {[v.model_dump() for v in violations]}"

    beat = world.beat(L.chime)
    user_parts = [f"BEAT: {beat['beat']}"]
    if chosen is not None:
        user_parts.append(f"PLAYER ACTION: {chosen.surface_text}")
    if events:
        user_parts.append("EVENTS:\n" + "\n".join(events))
    user = "\n\n".join(user_parts)

    return llm.complete(system, user, max_tokens=4096, effort="medium")
