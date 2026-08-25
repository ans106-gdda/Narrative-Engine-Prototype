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

    known_first_names = set()
    for cid in world.CANDIDATE_IDS:
        for part in world.archetype(cid)["name"].split():
            known_first_names.add(part.strip(".,").lower())
    known_first_names.add("vesper")

    _STOPWORDS = {
        "the", "a", "an", "you", "your", "he", "she", "it", "they", "i", "we",
        "still", "yet", "then", "now", "perhaps", "maybe", "well", "yes", "no",
        "oh", "ah", "hi", "hello", "did", "do", "does", "have", "has", "had",
        "was", "were", "is", "are", "one", "two", "three", "four", "five", "six",
        "but", "and", "or", "so", "if", "when", "where", "how", "what", "why",
        "not", "never", "always", "later", "here", "there", "this", "that",
        "these", "those", "even", "only", "just", "though", "although",
    }

    def _strip_possessive(word: str) -> str:
        if word.endswith("'s"):
            return word[:-2]
        if word.endswith("’s"):
            return word[:-2]
        return word

    sentences = narration.replace("!", ".").replace("?", ".").split(".")
    flagged = set()
    for sentence in sentences:
        stripped_sentence = sentence.strip()
        tokens = stripped_sentence.split()
        for idx, tok in enumerate(tokens):
            after_quote = idx > 0 and tokens[idx - 1].endswith(('"', "'", "“"))
            cleaned = _strip_possessive(tok.strip("'\":;,()“”"))
            if not cleaned or not cleaned[0].isupper() or len(cleaned) < 3:
                continue
            low = cleaned.lower()
            if low in _STOPWORDS or low in known_first_names:
                continue
            if idx == 0 or after_quote:
                continue
            if low in flagged:
                continue
            flagged.add(low)
            violations.append(Violation(
                rule="absent_candidate",
                quote=cleaned,
                explanation=f"'{cleaned}' is not in CANDIDATE_IDS + ['Vesper']",
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
