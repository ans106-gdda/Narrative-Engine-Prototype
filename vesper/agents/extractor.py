from vesper import ledger, llm
from vesper.schema import ExtractedIntent, Ledger


def extract(L: Ledger, free_text: str) -> ExtractedIntent:
    pairs = ledger.legal_intents(L)
    pair_desc = [{"intent": i, "target": t} for i, t in pairs]

    system = (
        "You map a player's free-text action to exactly one legal (intent, target) pair. "
        "You do not invent new intents or targets. If the text declares a stance, tag must be one of "
        "the closed vocabulary of position tags and intent must be declare_position. "
        "Report your confidence in the mapping from 0.0 to 1.0."
    )
    user = f"LEGAL PAIRS:\n{pair_desc}\n\nPLAYER TEXT:\n{free_text}"

    result = llm.parse(system, user, ExtractedIntent, max_tokens=4096)

    if (result.intent, result.target) not in pairs or result.confidence < 0.5:
        return ExtractedIntent(intent="deflect", target=None, tag=None, confidence=0.0)

    return result
