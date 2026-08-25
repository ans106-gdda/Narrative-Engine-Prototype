MODEL = "claude-opus-5"
TOTAL_CHIMES = 6
CANDIDATE_IDS = ["marrow", "ilsabet", "tobias"]

ARCHETYPES = {
    "marrow": {
        "name": "Marrow",
        "role": "Ghoul, 40 years serving House Ashgrove",
        "archetype": "Loyal, resentful, knows everything",
        "flaw": "Believes he has earned it; nobody counts him a real candidate",
        "voice": "Speaks in clipped, deferential sentences that curdle into bitterness when he is not being watched.",
        "secret_they_hold": "vesper_blood_failed_before",
        "initial_trust": 0,
    },
    "ilsabet": {
        "name": "Ilsabet Crane",
        "role": "Vampire hunter, infiltrated",
        "archetype": "Cold, competent, lies easily",
        "flaw": "Came to kill Vesper and has begun to doubt",
        "voice": "Speaks in flat, measured sentences, each word chosen to reveal nothing until doubt cracks her control.",
        "secret_they_hold": "ilsabet_is_a_hunter",
        "initial_trust": 0,
    },
    "tobias": {
        "name": "Tobias Vane",
        "role": "Nineteen, tubercular, dying",
        "archetype": "Desperate, transparent, honest",
        "flaw": "He is the only one who *needs* to win",
        "voice": "Speaks too fast, too openly, every sentence a plea he cannot help but make.",
        "secret_they_hold": "tobias_is_dying",
        "initial_trust": 0,
    },
}

VESPER = {
    "name": "Vesper Ashgrove",
    "voice": "Speaks slowly, precisely, as a man who has already seen how the sentence ends before he begins it.",
    "hidden_rule": "Vesper does not reward kindness or cruelty. He rewards a candidate who decides and holds to it.",
}

IMMUTABLE_CANON = [
    "Vesper Ashgrove dies at dawn. This cannot be prevented, delayed, or cured.",
    "Six chimes remain until dawn. The clock never runs backwards.",
    "Marrow has served House Ashgrove for forty years.",
    "Ilsabet Crane and Tobias Vane are human. Marrow is a ghoul. Only Vesper is a vampire.",
    "No one leaves the house before dawn.",
]

POSITION_TAGS = [
    "fearless", "fearful", "pro_marrow", "anti_marrow",
    "honest", "deceiver", "wants_power", "rejects_power",
]

CONTRADICTIONS = {
    "fearless": {"fearful"}, "fearful": {"fearless"},
    "pro_marrow": {"anti_marrow"}, "anti_marrow": {"pro_marrow"},
    "honest": {"deceiver"}, "deceiver": {"honest"},
    "wants_power": {"rejects_power"}, "rejects_power": {"wants_power"},
}

INTENTS = {
    "build_trust": {
        "description": "Build trust with a candidate.",
        "needs_target": True,
        "legal": "chime_lte_3",
    },
    "probe_secret": {
        "description": "Probe a candidate for their secret.",
        "needs_target": True,
        "legal": "probe_secret_legal",
    },
    "offer_alliance": {
        "description": "Offer a candidate an alliance.",
        "needs_target": True,
        "legal": "offer_alliance_legal",
    },
    "betray": {
        "description": "Betray a held secret to a candidate.",
        "needs_target": True,
        "legal": "betray_legal",
    },
    "bargain": {
        "description": "Strike a bargain with a candidate.",
        "needs_target": True,
        "legal": "chime_gte_2",
    },
    "threaten": {
        "description": "Threaten a candidate.",
        "needs_target": True,
        "legal": "chime_gte_3",
    },
    "declare_position": {
        "description": "Declare a stance to the room.",
        "needs_target": False,
        "legal": "always",
    },
    "deflect": {
        "description": "Deflect and give no answer.",
        "needs_target": False,
        "legal": "always",
    },
    "confess": {
        "description": "Confess honestly.",
        "needs_target": False,
        "legal": "always",
    },
}

THREAD_KEYWORDS = {
    "vesper_blood_failed": ["blood failed", "failed before", "prior heir", "previous heir"],
    "ilsabet_is_a_hunter": ["hunter", "hunt", "slayer", "stake"],
    "tobias_is_dying": ["dying", "tubercular", "consumption", "coughing blood"],
}

CHIME_SCRIPT = [
    {"chime": 1, "beat": "The interview. Vesper asks what you fear.", "pressure": "force a declare_position"},
    {"chime": 2, "beat": "Marrow's pact in the gallery.", "pressure": "none"},
    {"chime": 3, "beat": "Ilsabet counterattacks and plants a false rumor.", "pressure": "none"},
    {"chime": 4, "beat": "The rumor reaches Vesper.", "pressure": "none"},
    {"chime": 5, "beat": "Tobias collapses; his secret surfaces.", "pressure": "none"},
    {"chime": 6, "beat": "The bequest. Vesper decides.", "pressure": "none"},
]


def archetype(cid: str) -> dict:
    return ARCHETYPES[cid]


def intent_spec(intent_id: str) -> dict:
    return INTENTS[intent_id]


def beat(chime: int) -> dict:
    for b in CHIME_SCRIPT:
        if b["chime"] == chime:
            return b
    raise ValueError(f"no beat for chime {chime}")
