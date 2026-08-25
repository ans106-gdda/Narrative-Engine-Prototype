from vesper import llm, world
from vesper.agents import narrator
from vesper.schema import AuditResult, DialogueOption, Ledger, Violation

MAX_RETRIES = 2

AUDITOR_SYSTEM_PREFIX = (
    "You are a continuity auditor. You are given a state ledger and a passage. "
    "You do not judge quality, style, or morality. You report only factual contradictions."
)

AUDITOR_CHECKS = [
    "Does the passage contradict any immutable_canon entry?",
    "Does any character's warmth or hostility contradict their trust and emotional_state?",
    "Does the passage assert something about the player that contradicts stated_positions or secrets_held?",
    "Does it reveal a thread whose revealed_to_player is false?",
    "Does it state a fact that appears in rumor_network with true: false as if it were true in the "
    "narrator's own voice? A character repeating a false rumor is correct and is NOT a violation. "
    "Only the narrator asserting it as fact is.",
]


def _pre_checks(L: Ledger, narration: str) -> list[Violation]:
    violations: list[Violation] = []
    lower = narration.lower()

    for thread in L.plot_threads:
        if not thread.revealed_to_player:
            for kw in world.THREAD_KEYWORDS.get(thread.id, []):
                if kw.lower() in lower:
                    violations.append(Violation(
                        rule="hidden_thread_leak",
                        quote=kw,
                        explanation=f"narration mentions '{kw}', tied to hidden thread '{thread.id}'",
                    ))

    for cid, cand in L.candidates.items():
        if not cand.alive:
            name = world.archetype(cid)["name"]
            if name.lower() in lower or cid.lower() in lower:
                violations.append(Violation(
                    rule="dead_speaks",
                    quote=name,
                    explanation=f"{name} is not alive but appears as speaking/acting",
                ))

    # absent_candidate: catch a character who does not exist being made to speak
    # or act. Earlier this was a blacklist of common words, which flagged every
    # capitalised noun in the prose -- including "Ashgrove", a name from canon.
    # Inverted to a whitelist (world.KNOWN_PROPER_NOUNS) AND narrowed to tokens
    # actually followed by a speech or action verb, which is the only case the
    # rule is meant to catch.
    ACTION_VERBS = {
        "says", "said", "say", "speaks", "spoke", "asks", "asked", "replies",
        "replied", "answers", "answered", "whispers", "whispered", "murmurs",
        "murmured", "laughs", "laughed", "nods", "nodded", "watches", "watched",
        "steps", "stepped", "turns", "turned", "moves", "moved", "stands",
        "stood", "sits", "sat", "smiles", "smiled", "leans", "leaned", "enters",
        "entered", "crosses", "crossed", "lifts", "lifted", "sets", "reaches",
        "reached", "tells", "told", "calls", "called", "is", "was", "has", "had",
    }

    def _clean(word: str) -> str:
        for suffix in ("'s", "\u2019s"):
            if word.endswith(suffix):
                word = word[: -len(suffix)]
        return word.strip("'\":;,.()\u201c\u201d!?")

    sentences = narration.replace("!", ".").replace("?", ".").split(".")
    flagged = set()
    for sentence in sentences:
        tokens = sentence.split()
        for idx, tok in enumerate(tokens):
            # Sentence-initial capitalisation carries no signal. A token right
            # after a closing quote also starts a sentence -- splitting on "."
            # does not see the break when dialogue ends the previous one.
            after_quote = tokens[idx - 1].endswith(('"', "'", "\u201d"))
            if idx == 0 or after_quote:
                continue
            cleaned = _clean(tok)
            if len(cleaned) < 3 or not cleaned[0].isupper():
                continue
            low = cleaned.lower()
            if low in world.KNOWN_PROPER_NOUNS or low in flagged:
                continue
            # Only a name that speaks or acts is an invented character.
            following = {_clean(t).lower() for t in tokens[idx + 1: idx + 4]}
            if not (following & ACTION_VERBS):
                continue
            flagged.add(low)
            violations.append(Violation(
                rule="absent_candidate",
                quote=cleaned,
                explanation=f"'{cleaned}' speaks or acts but is not a character in this world",
            ))

    return violations


def _llm_check(L: Ledger, narration: str) -> list[Violation]:
    system = (
        f"{AUDITOR_SYSTEM_PREFIX}\n\n"
        f"{L.model_dump_json(indent=2)}\n\n"
        f"FACTS THAT CAN NEVER BE CONTRADICTED\n{chr(10).join(world.IMMUTABLE_CANON)}\n\n"
        f"CHECKS\n" + "\n".join(f"{i+1}. {c}" for i, c in enumerate(AUDITOR_CHECKS))
    )
    user = f"PASSAGE:\n{narration}"

    result: AuditResult = llm.parse(
        system, user, AuditResult, max_tokens=4096,
    )
    return result.violations


def audit(L: Ledger, narration: str) -> AuditResult:
    violations = _pre_checks(L, narration)
    violations += _llm_check(L, narration)
    return AuditResult(consistent=(violations == []), violations=violations)


def audited_narration(L: Ledger, chosen: DialogueOption | None, events: list[str]) -> tuple[str, AuditResult, int]:
    violations: list[Violation] | None = None
    narration = ""
    result = AuditResult(consistent=False)

    for attempt in range(MAX_RETRIES + 1):
        narration = narrator.narrate(L, chosen, events, violations)
        result = audit(L, narration)
        if result.consistent:
            return narration, result, attempt
        violations = result.violations

    L.contradiction_log.extend(result.violations)
    return narration, result, MAX_RETRIES
