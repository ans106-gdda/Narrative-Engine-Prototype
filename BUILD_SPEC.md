# BUILD SPEC — The Vesper Contract
### Executable implementation spec. Follow literally. Do not improvise.

**Read this whole file before writing any code.**

---

## 0. Rules of engagement

1. **Never invent an API shape.** Every Anthropic SDK call in this spec is given verbatim. Do not add parameters that are not listed.
2. **The LLM never writes to the ledger.** Only `ledger.apply_patch()` mutates state. If you find yourself parsing narration to update state, you have made an error.
3. **Do not add features.** No web UI, no save/load beyond what is specified, no extra NPCs, no extra intents.
4. **Every phase ends with its Acceptance Check.** Run it. Do not start the next phase until it passes.
5. **All code, comments, strings, and narrative content in English.**
6. Python interpreter is `./.venv/bin/python` (3.11.15). Never use `python3` or `python`.

### Hard-won API rules (violating these causes silent failures)

```python
# RULE A: content[0] is NOT always text. Opus 5 thinks by default.
text = "".join(b.text for b in response.content if b.type == "text").strip()

# RULE B: thinking shares the max_tokens budget. Too low = empty text, NO error raised.
#         Always use max_tokens >= 4096 and always verify stop_reason.
if response.stop_reason != "end_turn":
    raise LLMError(f"truncated or refused: {response.stop_reason}")

# RULE C: model id is exactly this string. No date suffix.
MODEL = "claude-opus-5"
```

---

## 1. Final file tree

Create exactly these files. Nothing more.

```
vesper/
  __init__.py          empty
  world.py             F2  constants only, no logic
  schema.py            F2  pydantic models only, no logic
  ledger.py            F3  pure deterministic logic, NO imports from anthropic
  render.py            F4  terminal output, no logic
  llm.py               F5  the only file that imports anthropic
  agents/
    __init__.py        empty
    narrator.py        F5
    optioner.py        F6
    extractor.py       F6
    auditor.py         F7
  engine.py            F8
main.py                F8  CLI entry point
fixtures/              F9  generated at runtime, not hand-written
logs/                  F8  generated at runtime
README.md              F10
```

---

## PHASE F2 — `world.py` and `schema.py`

### F2.1 `vesper/world.py`

Constants only. No functions except the three pure lookups at the end.

```python
MODEL = "claude-opus-5"
TOTAL_CHIMES = 6
CANDIDATE_IDS = ["marrow", "ilsabet", "tobias"]
```

**`ARCHETYPES`** — dict keyed by candidate id. Each value has exactly these keys:
`name`, `role`, `archetype`, `flaw`, `voice`, `secret_they_hold`, `initial_trust`.

| id | name | role | archetype | flaw | initial_trust |
|---|---|---|---|---|---|
| `marrow` | Marrow | Ghoul, 40 years serving House Ashgrove | Loyal, resentful, knows everything | Believes he has earned it; nobody counts him a real candidate | `0` |
| `ilsabet` | Ilsabet Crane | Vampire hunter, infiltrated | Cold, competent, lies easily | Came to kill Vesper and has begun to doubt | `0` |
| `tobias` | Tobias Vane | Nineteen, tubercular, dying | Desperate, transparent, honest | He is the only one who *needs* to win | `0` |

`voice` is a one-sentence style instruction for the narrator, e.g. Marrow: `"Speaks in clipped, deferential sentences that curdle into bitterness when he is not being watched."` Write one for each in the same register.

`secret_they_hold`:
- marrow: `"vesper_blood_failed_before"`
- ilsabet: `"ilsabet_is_a_hunter"`
- tobias: `"tobias_is_dying"`

**`VESPER`** — dict with `name: "Vesper Ashgrove"`, `voice`, and `hidden_rule` = `"Vesper does not reward kindness or cruelty. He rewards a candidate who decides and holds to it."`

**`IMMUTABLE_CANON`** — list of strings, the seed facts:
```
"Vesper Ashgrove dies at dawn. This cannot be prevented, delayed, or cured."
"Six chimes remain until dawn. The clock never runs backwards."
"Marrow has served House Ashgrove for forty years."
"Ilsabet Crane and Tobias Vane are human. Marrow is a ghoul. Only Vesper is a vampire."
"No one leaves the house before dawn."
```

**`POSITION_TAGS`** — the closed vocabulary of stances the player can take:
```python
POSITION_TAGS = ["fearless", "fearful", "pro_marrow", "anti_marrow",
                 "honest", "deceiver", "wants_power", "rejects_power"]
```

**`CONTRADICTIONS`** — symmetric dict mapping a tag to the set of tags it contradicts:
```python
CONTRADICTIONS = {
    "fearless": {"fearful"},   "fearful": {"fearless"},
    "pro_marrow": {"anti_marrow"}, "anti_marrow": {"pro_marrow"},
    "honest": {"deceiver"},    "deceiver": {"honest"},
    "wants_power": {"rejects_power"}, "rejects_power": {"wants_power"},
}
```

**`INTENTS`** — dict keyed by intent id. Each value: `description`, `needs_target` (bool), `legal` (a rule expressed as data, see below).

| intent | needs_target | legal when |
|---|---|---|
| `build_trust` | yes | `chime <= 3` |
| `probe_secret` | yes | `target.trust >= 0` and target's secret not yet in `player.secrets_held` |
| `offer_alliance` | yes | `target.trust >= 1` and `chime <= 4` |
| `betray` | yes | `player.secrets_held` is non-empty |
| `bargain` | yes | `chime >= 2` |
| `threaten` | yes | `chime >= 3` |
| `declare_position` | no | always |
| `deflect` | no | always |
| `confess` | no | always |

Encode `legal` as a **string key** naming a predicate implemented in `ledger.py` (e.g. `"chime_lte_3"`). `world.py` must contain no logic.

**`CHIME_SCRIPT`** — list of 6 dicts, `{"chime": n, "beat": "...", "pressure": "..."}` describing what the house does that turn. Use the six beats:
1. The interview. Vesper asks what you fear. *(pressure: force a `declare_position`)*
2. Marrow's pact in the gallery.
3. Ilsabet counterattacks and plants a false rumor.
4. The rumor reaches Vesper.
5. Tobias collapses; his secret surfaces.
6. The bequest. Vesper decides.

Final three pure lookups (no state, no side effects):
```python
def archetype(cid: str) -> dict: ...
def intent_spec(intent_id: str) -> dict: ...
def beat(chime: int) -> dict: ...
```

### F2.2 `vesper/schema.py`

Pydantic v2 models. **Every model sets `model_config = ConfigDict(extra="forbid")`.**

```python
class EmotionalState(BaseModel):
    mood: str                    # free-form single word
    cause: str
    decays_at_chime: int

class Candidate(BaseModel):
    id: str
    trust: int = 0               # clamped to [-5, 5] by ledger, never here
    alive: bool = True
    emotional_state: EmotionalState | None = None
    believes_about_player: list[str] = []
    knows_secrets: list[str] = []
    shared_secret_with_player: bool = False

class StatedPosition(BaseModel):
    claim: str
    tag: str                     # must be in world.POSITION_TAGS
    chime: int
    audience: list[str]

class Rumor(BaseModel):
    fact: str
    true: bool
    origin_chime: int
    spread_by: str               # "player" or a candidate id
    known_by: list[str]
    reaches_vesper_at: int
    vesper_delta: int            # applied once when it reaches Vesper
    applied: bool = False

class PlotThread(BaseModel):
    id: str
    state: Literal["open", "escalating", "resolved"]
    revealed_to_player: bool
    dormant_for: int = 0

class Player(BaseModel):
    standing_with_vesper: int = 0
    coherence_score: float = 1.0
    stated_positions: list[StatedPosition] = []
    contradictions_committed: int = 0
    secrets_held: list[str] = []

class Violation(BaseModel):
    rule: str                    # which check failed
    quote: str                   # the offending span from the narration
    explanation: str

class Ledger(BaseModel):
    chime: int = 1
    chimes_until_dawn: int = 5
    player: Player = Player()
    candidates: dict[str, Candidate]
    rumor_network: list[Rumor] = []
    plot_threads: list[PlotThread] = []
    immutable_canon: list[str] = []
    contradiction_log: list[Violation] = []
```

**Patch model** — the ONLY way state changes. A patch is a list of typed operations:

```python
class Op(BaseModel):
    kind: Literal["trust_delta", "set_mood", "add_belief", "learn_secret",
                  "add_rumor", "add_position", "advance_thread",
                  "reveal_thread", "standing_delta", "add_canon"]
    target: str | None = None    # candidate id where applicable
    value: dict                  # kind-specific payload

class Patch(BaseModel):
    ops: list[Op] = []
    note: str = ""               # human-readable reason, for the log
```

**LLM output models** (used with `messages.parse`):

```python
class DialogueOption(BaseModel):
    intent: str
    target: str | None
    surface_text: str            # what the player sees, first person, <= 30 words

class OptionSet(BaseModel):
    options: list[DialogueOption]

class ExtractedIntent(BaseModel):
    intent: str
    target: str | None
    tag: str | None              # required iff intent == "declare_position"
    confidence: float

class AuditResult(BaseModel):
    consistent: bool
    violations: list[Violation] = []
```

### F2 Acceptance Check
```bash
./.venv/bin/python -c "
from vesper.schema import Ledger
from vesper import world
L = Ledger(candidates={c: __import__('vesper.schema',fromlist=['Candidate']).Candidate(id=c) for c in world.CANDIDATE_IDS}, immutable_canon=world.IMMUTABLE_CANON)
print(L.model_dump_json(indent=2)[:400]); print('F2 OK')"
```
Must print valid JSON and `F2 OK`.

---

## PHASE F3 — `vesper/ledger.py`

**This file must not import `anthropic`.** It is pure, deterministic, and unit-testable.

### Required functions, exact signatures

```python
def new_game() -> Ledger
```
Builds the opening ledger: chime 1, three candidates at `initial_trust`, `immutable_canon` seeded from `world.IMMUTABLE_CANON`, and three plot threads:
`vesper_blood_failed` (open, hidden), `ilsabet_is_a_hunter` (open, hidden), `tobias_is_dying` (open, hidden).

```python
def legal_intents(L: Ledger) -> list[tuple[str, str | None]]
```
Returns every `(intent_id, target_id)` pair currently legal, by evaluating each intent's `legal` predicate key. `needs_target=False` intents yield `(intent, None)`.

```python
def pruned_intents(L: Ledger) -> list[dict]
```
Returns `[{"intent":..., "target":..., "reason":...}]` for every pair that is **illegal**, with a human-readable reason string (e.g. `"chime 4 > 3"`, `"ilsabet.trust -2 < 1"`). **This is graded output — the reason must name the actual numbers.**

```python
def resolve_effects(L: Ledger, intent: str, target: str | None, tag: str | None = None) -> Patch
```
Pure function. Given state and a chosen intent, returns the Patch. **The LLM is never consulted here.** Effect table:

| intent | ops produced |
|---|---|
| `build_trust` | `trust_delta +2` on target; `set_mood` target→`{"mood":"warmed","decays_at_chime": chime+2}` |
| `probe_secret` | if `target.trust >= 2`: `learn_secret` target's secret + `trust_delta +1`; else `trust_delta -1` and `add_belief` target ← `"the player is prying"` |
| `offer_alliance` | `trust_delta +3` target; `add_belief` target ← `"the player is my ally"`; `add_rumor` fact `"the player allied with {target}"`, true, `vesper_delta +1`, known_by `[target]` |
| `betray` | `trust_delta -4` on the betrayed; `trust_delta +2` on the listener; `add_rumor` `"the player betrayed {betrayed}"`, true, `vesper_delta +1`, spread by the listener |
| `bargain` | `trust_delta +1` target; `standing_delta 0`; `add_belief` target ← `"the player wants something from me"` |
| `threaten` | `trust_delta -3` target; `set_mood` `cornered`; `add_rumor` `"the player makes threats"`, true, `vesper_delta -1` |
| `declare_position` | `add_position` with the given `tag` |
| `deflect` | `standing_delta -1` (Vesper despises indecision) |
| `confess` | `standing_delta +1`; `add_position` tag `honest` |

Trust is clamped to `[-5, 5]` inside `apply_patch`, never in the effect table.

```python
def apply_patch(L: Ledger, p: Patch) -> Ledger
```
Returns a **new** Ledger (deep copy; never mutate the argument). Applies every op in order. Clamps trust to `[-5,5]` and `standing_with_vesper` to `[-5,5]`. Raises `ValueError` on an unknown `kind`.

```python
def recompute_coherence(L: Ledger) -> Ledger
```
For each `StatedPosition`, count how many earlier positions carry a tag in `CONTRADICTIONS[tag]`. Set `player.contradictions_committed` to that count and
`coherence_score = round(1.0 - contradictions / max(1, len(stated_positions)), 2)`, floored at `0.0`.

```python
def advance_chime(L: Ledger) -> tuple[Ledger, list[str]]
```
Runs in this exact order, returning the new ledger plus a list of human-readable event strings for the render panel:
1. `chime += 1`, `chimes_until_dawn = TOTAL_CHIMES - chime`
2. **Decay moods**: any `emotional_state` with `decays_at_chime <= chime` becomes `None`.
3. **Propagate rumors**: for each rumor with `applied == False` and `reaches_vesper_at <= chime`, apply `standing_delta = vesper_delta`, set `applied = True`, emit event `"Vesper has heard: {fact}"`.
4. **Age threads**: every thread with `state != "resolved"` gets `dormant_for += 1`; reset to 0 for any thread touched this turn.
5. `recompute_coherence`.

```python
def dormant_thread(L: Ledger) -> PlotThread | None
```
Returns the non-resolved thread with the highest `dormant_for` if that value `>= 2`, else `None`. The narrator receives this as a nudge to push the plot.

```python
def diff(before: Ledger, after: Ledger) -> list[str]
```
Human-readable change lines, e.g. `"marrow.trust 0 -> +2"`, `"player.coherence 1.0 -> 0.83"`, `"+rumor 'the player allied with marrow'"`. Used by the render panel and the log.

### F3 Acceptance Check
Write `tests/test_ledger.py` with these cases and run `./.venv/bin/pytest -q` (add `pytest` to requirements):
1. `new_game()` has 3 candidates, all trust 0, 5 canon facts.
2. `build_trust` on marrow twice → trust exactly `+4`, not `+5` or clamped early.
3. Trust clamps at `+5` after three `build_trust`.
4. `declare_position` `fearless` then `fearful` → `contradictions_committed == 1` and `coherence_score == 0.5`.
5. A rumor with `reaches_vesper_at = 4` does not move `standing_with_vesper` at chime 3 and does move it exactly once at chime 4 — call `advance_chime` twice more and assert it is not applied again.
6. `apply_patch` does not mutate its input (`before.model_dump() == snapshot`).
7. `pruned_intents` at chime 5 includes `build_trust` with a reason containing `"5"` and `"3"`.

**All 7 must pass before F4.**

---

## PHASE F4 — `vesper/render.py`

Uses `rich`. One required function:

```python
def panel(L: Ledger, events: list[str], pruned: list[dict], audit: AuditResult, retries: int) -> None
```

Prints exactly this layout (bars are 10 chars, `█` filled / `░` empty, trust `[-5,5]` mapped to 0–10):

```
╔═ CHIME 4 ──────────────────── 2 until dawn ═╗
  VESPER  ██████░░░░  +2     COHERENCE  ████████░░  0.83

  Marrow    ███████░░░  +3   hopeful   (fades at 5)
  Ilsabet   ███░░░░░░░  -2   cornered  (fades at 4)
  Tobias    █████░░░░░   0   —

  RUMOR NETWORK
   ✓ "the player allied with marrow"   marrow, ilsabet  → Vesper NOW
   ✗ "the player fears Vesper"         tobias           → Vesper at 5

  PRUNED OPTIONS
   ✗ build_trust    · chime 4 > 3
   ✗ offer_alliance · ilsabet.trust -2 < 1

  AUDIT  ✅ consistent (1 retry)
╚═════════════════════════════════════════════╝
```

`✓` = rumor is true, `✗` = rumor is false. This distinction is the single most important visual in the project — do not drop it.

Also required: `def show_options(options: list[DialogueOption]) -> None` printing a numbered list of `surface_text`.

### F4 Acceptance Check
`./.venv/bin/python -c "from vesper import ledger, render; L=ledger.new_game(); render.panel(L, [], ledger.pruned_intents(L), None, 0)"` renders without error.

---

## PHASE F5 — `vesper/llm.py` + `agents/narrator.py`

### F5.1 `vesper/llm.py`

The only file importing `anthropic`. Loads `.env` via `dotenv.load_dotenv()`.

```python
class LLMError(RuntimeError): ...

def complete(system: str, user: str, max_tokens: int = 4096, effort: str = "medium") -> str
```
Calls:
```python
client.messages.create(
    model=world.MODEL,
    max_tokens=max_tokens,
    system=system,
    messages=[{"role": "user", "content": user}],
    output_config={"effort": effort},
)
```
Then applies **RULE A** and **RULE B** from §0. Raises `LLMError` if `stop_reason != "end_turn"` or the extracted text is empty.

```python
def parse(system: str, user: str, model_cls, max_tokens: int = 4096):
```
Calls:
```python
client.messages.parse(
    model=world.MODEL,
    max_tokens=max_tokens,
    system=system,
    messages=[{"role": "user", "content": user}],
    output_format=model_cls,
)
```
Returns `response.parsed_output`. Raises `LLMError` if it is `None`.

Both functions log every call to `logs/llm_calls.jsonl`: `{ts, fn, system_hash, user, output, usage, stop_reason}`.

### F5.2 `vesper/agents/narrator.py`

```python
def narrate(L: Ledger, chosen: DialogueOption | None, events: list[str],
            violations: list[Violation] | None = None) -> str
```

System prompt must contain, in this order:
1. Role: `"You are the Dungeon Master for The Vesper Contract. You narrate; you never decide facts."`
2. The full ledger as JSON (`L.model_dump_json(indent=2)`).
3. `world.IMMUTABLE_CANON` under the header `FACTS THAT CAN NEVER BE CONTRADICTED`.
4. The **hard rules**, verbatim:
   - `Never reveal a plot_thread whose revealed_to_player is false.`
   - `Never contradict immutable_canon.`
   - `A candidate whose alive is false does not speak or act.`
   - `Tone toward the player is governed by trust: <= -3 hostile, -2..0 guarded, 1..2 warm, >= 3 confiding.`
   - `emotional_state overrides trust for this turn only.`
   - `Reference at least one open plot thread or one stated_position.`
   - `Do not invent numbers, dates, or names not present in the ledger or the canon.`
   - `Write 120-200 words. Second person, present tense. No dice, no stats, no menus.`
5. If `dormant_thread(L)` is not None: `"Push this thread forward: {id}"`.
6. If `violations` is not None: `"Your previous attempt was rejected. Fix these and rewrite: {violations}"`.

User message: the chime beat from `world.beat()`, the chosen option's `surface_text`, and `events`.

Call with `effort="medium"`, `max_tokens=4096`.

### F5 Acceptance Check
Narrate chime 1 from `new_game()` with `chosen=None`. Output must be 120–200 words and must not contain the strings `"hunter"`, `"dying"`, or `"blood failed"` (all three threads start hidden).

---

## PHASE F6 — `agents/optioner.py` + `agents/extractor.py`

### F6.1 `optioner.py`

```python
def generate_options(L: Ledger, narration: str) -> list[DialogueOption]
```

1. Compute `pairs = ledger.legal_intents(L)` in Python.
2. Cap at 4 options. Selection rule (deterministic, no LLM): prefer pairs whose target has a non-`None` `emotional_state`, then highest `abs(trust)`, then intent order as listed in `world.INTENTS`. `declare_position`/`deflect`/`confess` fill remaining slots.
3. Call `llm.parse(..., OptionSet)` passing **only the selected pairs** plus the narration and the relevant candidate state, asking it to write `surface_text` for each.
4. **Validate**: every returned option's `(intent, target)` must be in the selected pairs. Drop any that is not, and log it. If fewer than 2 survive, retry once; then fall back to raw intent names as surface text.

> The model chooses wording. Python chose the moves. Never let the model return a pair that was not passed in.

### F6.2 `extractor.py`

```python
def extract(L: Ledger, free_text: str) -> ExtractedIntent
```
Used only when the player types instead of picking a number. Passes the legal pairs and asks the model to map the text to exactly one. Validates the result is in the legal set; if not, or if `confidence < 0.5`, return `ExtractedIntent(intent="deflect", target=None, tag=None, confidence=0.0)` and tell the player their action was read as hesitation.

### F6 Acceptance Check
- `generate_options` on a chime-1 ledger returns 2–4 options, all with `(intent,target)` in `legal_intents`.
- `extract(L, "I tell Marrow I'll back him")` returns intent `offer_alliance` or `build_trust` targeting `marrow`.
- `extract(L, "asdfgh")` returns `deflect` with confidence `0.0`.

---

## PHASE F7 — `agents/auditor.py` — THE CONSISTENCY AGENT

This is the graded centerpiece. Two layers.

```python
def audit(L: Ledger, narration: str) -> AuditResult
```

**Layer 1 — deterministic pre-checks (Python, no LLM).** Run first; each failure is a `Violation`:
- `hidden_thread_leak`: narration contains a keyword tied to any thread with `revealed_to_player == False`. Keyword map lives in `world.THREAD_KEYWORDS` (e.g. `ilsabet_is_a_hunter` → `["hunter","hunt","slayer","stake"]`).
- `dead_speaks`: a candidate with `alive == False` is named as speaking.
- `absent_candidate`: a name appears that is not in `CANDIDATE_IDS + ["Vesper"]`.

**Layer 2 — LLM check.** `llm.parse(..., AuditResult)` with `effort="high"` and `thinking={"type":"adaptive"}` — this is the one place deep reasoning is worth paying for.

System prompt: `"You are a continuity auditor. You are given a state ledger and a passage. You do not judge quality, style, or morality. You report only factual contradictions."` Then the ledger JSON, the canon, and these checks:
1. Does the passage contradict any `immutable_canon` entry?
2. Does any character's warmth or hostility contradict their `trust` and `emotional_state`?
3. Does the passage assert something about the player that contradicts `stated_positions` or `secrets_held`?
4. Does it reveal a thread whose `revealed_to_player` is false?
5. Does it state a fact that appears in `rumor_network` with `true: false` **as if it were true in the narrator's own voice**? A *character* repeating a false rumor is correct and is NOT a violation. Only the narrator asserting it as fact is.

> Check 5 is the heart of the project. Get it exactly right: tracked misinformation is legal, narrator hallucination is not.

Merge both layers. `consistent = (violations == [])`.

```python
def audited_narration(L: Ledger, chosen, events) -> tuple[str, AuditResult, int]
```
Loop up to **2 retries**: narrate → audit → if inconsistent, re-narrate passing `violations`. On final failure, **accept the narration anyway**, append every violation to `L.contradiction_log`, and return `retries` used. Never hang, never crash the game.

### F7 Acceptance Check
Craft a ledger where `marrow.trust = -5`, then hand the auditor the passage `"Marrow embraces you warmly and calls you his dearest friend."` → must return `consistent=False` with a violation naming trust.
Then hand it `"Marrow watches you from the doorway and says nothing."` → must return `consistent=True`.

---

## PHASE F8 — `engine.py` + `main.py`

### `engine.py`

```python
def play_turn(L: Ledger, choice: DialogueOption | None, events: list[str]) -> TurnResult
```
Exact order — do not reorder:
1. `narration, audit, retries = auditor.audited_narration(L, choice, events)`
2. If `choice`: `patch = ledger.resolve_effects(L, choice.intent, choice.target, tag)` → `L2 = apply_patch(L, patch)`; else `patch = Patch()`, `L2 = L`
3. `L2 = recompute_coherence(L2)`
4. `options = optioner.generate_options(L2, narration)`
5. Return `TurnResult(ledger=L2, narration=..., options=..., patch=..., audit=..., retries=..., diff=ledger.diff(L, L2))`

Between turns the caller invokes `advance_chime`.

**Logging** — append one JSON object per turn to `logs/session_<ts>.jsonl`:
```json
{"chime":n,"player_input":"...","chosen_intent":"...","patch":{...},
 "diff":["..."],"audit":{...},"retries":0,"narration":"...","ledger":{...}}
```
The full ledger goes in every line. This file *is* the State Tracking evidence.

### `main.py` — interactive REPL (primary mode)

```
./.venv/bin/python main.py                          # interactive, 6 chimes
./.venv/bin/python main.py --save fixtures/pact.json # dump ledger on exit
./.venv/bin/python main.py --load fixtures/x.json --input "..."   # single turn, for A/B
```
Each turn: render panel → print narration → `show_options` → read input. A digit picks that option; anything else goes to `extractor.extract`. `quit` exits and saves.

At chime 6, print the bequest: Vesper's decision computed **in Python** from `coherence_score`, `standing_with_vesper`, and rumor count — then narrated. Highest weight on coherence, per `VESPER["hidden_rule"]`.

### F8 Acceptance Check
A full 6-chime interactive run completes without exception, and `logs/session_*.jsonl` has exactly 6 lines, each containing a complete `ledger` object.

---

## PHASE F9 — the A/B fixtures

1. Play chimes 1–2 choosing **accept Marrow's pact** (`offer_alliance` → marrow). Save as `fixtures/pact.json`.
2. Replay chimes 1–2 identically but choose **betray Marrow to Ilsabet** (`betray` → marrow). Save as `fixtures/betrayal.json`.
3. Run both:
```bash
./.venv/bin/python main.py --load fixtures/pact.json     --input "Marrow, I need the truth about the blood."
./.venv/bin/python main.py --load fixtures/betrayal.json --input "Marrow, I need the truth about the blood."
```
4. Capture both full panels + narrations into `docs/ab_demo.txt`.

**Required outcome:** the two runs must differ in all three layers — prose, available options, and pruning reasons. If the option lists come out identical, the fixtures are not divergent enough; re-derive them before writing the README.

---

## PHASE F10 — `README.md`

Sections, in order:
1. **The World** — premise, cast table, the clock, Vesper's hidden rule. ~200 words.
2. **What the Ledger Tracks** — the four layers, each with the real JSON from a played session and one sentence on why it exists. Name `rumor_network`, `coherence_score`, `believes_about_player`, `immutable_canon`.
3. **Architecture** — the four-agent diagram and the line: *the LLM narrates; Python decides.*
4. **Consistency: how contradictions are stopped** — the two auditor layers, the retry loop, and a real entry from `contradiction_log` if one occurred.
5. **One moment that surprised me** — **must come from the actual F9 run.** Do not write this section before F9 is done. Quote the transcript.
6. **Reactive dialogue: A/B** — the two runs side by side from `docs/ab_demo.txt`.
7. **Running it** — venv, `.env`, the commands.

---

## Definition of done

- [ ] `pytest` green: all 7 ledger tests
- [ ] 6-chime interactive run completes, 6 log lines with full ledgers
- [ ] `contradiction_log` mechanism demonstrated (an entry, or a logged retry that fixed one)
- [ ] `docs/ab_demo.txt` shows divergence in prose, options, and pruning
- [ ] README has all 7 sections; §5 quotes the real transcript
- [ ] No file except `llm.py` imports `anthropic`
- [ ] `.env` is git-ignored and contains no committed key
