from vesper import world
from vesper.schema import (
    Candidate,
    EmotionalState,
    Ledger,
    Op,
    Patch,
    PlotThread,
    StatedPosition,
    Violation,
)


def new_game() -> Ledger:
    candidates = {
        cid: Candidate(id=cid, trust=world.archetype(cid)["initial_trust"])
        for cid in world.CANDIDATE_IDS
    }
    plot_threads = [
        PlotThread(id="vesper_blood_failed", state="open", revealed_to_player=False),
        PlotThread(id="ilsabet_is_a_hunter", state="open", revealed_to_player=False),
        PlotThread(id="tobias_is_dying", state="open", revealed_to_player=False),
    ]
    return Ledger(
        chime=1,
        chimes_until_dawn=world.TOTAL_CHIMES - 1,
        candidates=candidates,
        immutable_canon=list(world.IMMUTABLE_CANON),
        plot_threads=plot_threads,
    )


def _predicate(key: str, L: Ledger, target: str | None) -> tuple[bool, str]:
    if key == "always":
        return True, ""
    if key == "chime_lte_3":
        ok = L.chime <= 3
        return ok, f"chime {L.chime} > 3"
    if key == "chime_gte_2":
        ok = L.chime >= 2
        return ok, f"chime {L.chime} < 2"
    if key == "chime_gte_3":
        ok = L.chime >= 3
        return ok, f"chime {L.chime} < 3"
    if key == "probe_secret_legal":
        cand = L.candidates[target]
        secret = world.archetype(target)["secret_they_hold"]
        if cand.trust < 0:
            return False, f"{target}.trust {cand.trust} < 0"
        if secret in L.player.secrets_held:
            return False, f"{target}'s secret already known"
        return True, ""
    if key == "offer_alliance_legal":
        cand = L.candidates[target]
        if cand.trust < 1:
            return False, f"{target}.trust {cand.trust} < 1"
        if L.chime > 4:
            return False, f"chime {L.chime} > 4"
        return True, ""
    if key == "betray_legal":
        ok = len(L.player.secrets_held) > 0
        return ok, "player.secrets_held is empty"
    raise ValueError(f"unknown legal predicate {key}")


def legal_intents(L: Ledger) -> list[tuple[str, str | None]]:
    pairs = []
    for intent_id, spec in world.INTENTS.items():
        if spec["needs_target"]:
            for cid in world.CANDIDATE_IDS:
                ok, _ = _predicate(spec["legal"], L, cid)
                if ok:
                    pairs.append((intent_id, cid))
        else:
            ok, _ = _predicate(spec["legal"], L, None)
            if ok:
                pairs.append((intent_id, None))
    return pairs


def pruned_intents(L: Ledger) -> list[dict]:
    pruned = []
    for intent_id, spec in world.INTENTS.items():
        if spec["needs_target"]:
            for cid in world.CANDIDATE_IDS:
                ok, reason = _predicate(spec["legal"], L, cid)
                if not ok:
                    pruned.append({"intent": intent_id, "target": cid, "reason": reason})
        else:
            ok, reason = _predicate(spec["legal"], L, None)
            if not ok:
                pruned.append({"intent": intent_id, "target": None, "reason": reason})
    return pruned


def resolve_effects(L: Ledger, intent: str, target: str | None, tag: str | None = None) -> Patch:
    ops: list[Op] = []
    chime = L.chime

    if intent == "build_trust":
        ops.append(Op(kind="trust_delta", target=target, value={"delta": 2}))
        ops.append(Op(kind="set_mood", target=target, value={"mood": "warmed", "decays_at_chime": chime + 2}))

    elif intent == "probe_secret":
        cand = L.candidates[target]
        if cand.trust >= 2:
            secret = world.archetype(target)["secret_they_hold"]
            ops.append(Op(kind="learn_secret", target=target, value={"secret": secret}))
            ops.append(Op(kind="trust_delta", target=target, value={"delta": 1}))
        else:
            ops.append(Op(kind="trust_delta", target=target, value={"delta": -1}))
            ops.append(Op(kind="add_belief", target=target, value={"belief": "the player is prying"}))

    elif intent == "offer_alliance":
        ops.append(Op(kind="trust_delta", target=target, value={"delta": 3}))
        ops.append(Op(kind="add_belief", target=target, value={"belief": "the player is my ally"}))
        ops.append(Op(kind="add_rumor", target=None, value={
            "fact": f"the player allied with {target}",
            "true": True,
            "origin_chime": chime,
            "spread_by": "player",
            "known_by": [target],
            "reaches_vesper_at": chime + 1,
            "vesper_delta": 1,
        }))

    elif intent == "betray":
        betrayed = target
        listener = None
        for cid in world.CANDIDATE_IDS:
            if cid != betrayed:
                listener = cid
                break
        ops.append(Op(kind="trust_delta", target=betrayed, value={"delta": -4}))
        ops.append(Op(kind="trust_delta", target=listener, value={"delta": 2}))
        ops.append(Op(kind="add_rumor", target=None, value={
            "fact": f"the player betrayed {betrayed}",
            "true": True,
            "origin_chime": chime,
            "spread_by": listener,
            "known_by": [listener],
            "reaches_vesper_at": chime + 1,
            "vesper_delta": 1,
        }))

    elif intent == "bargain":
        ops.append(Op(kind="trust_delta", target=target, value={"delta": 1}))
        ops.append(Op(kind="standing_delta", target=None, value={"delta": 0}))
        ops.append(Op(kind="add_belief", target=target, value={"belief": "the player wants something from me"}))

    elif intent == "threaten":
        ops.append(Op(kind="trust_delta", target=target, value={"delta": -3}))
        ops.append(Op(kind="set_mood", target=target, value={"mood": "cornered", "decays_at_chime": chime + 2}))
        ops.append(Op(kind="add_rumor", target=None, value={
            "fact": "the player makes threats",
            "true": True,
            "origin_chime": chime,
            "spread_by": "player",
            "known_by": [target] if target else [],
            "reaches_vesper_at": chime + 1,
            "vesper_delta": -1,
        }))

    elif intent == "declare_position":
        ops.append(Op(kind="add_position", target=None, value={"tag": tag}))

    elif intent == "deflect":
        ops.append(Op(kind="standing_delta", target=None, value={"delta": -1}))

    elif intent == "confess":
        ops.append(Op(kind="standing_delta", target=None, value={"delta": 1}))
        ops.append(Op(kind="add_position", target=None, value={"tag": "honest"}))

    else:
        raise ValueError(f"unknown intent {intent}")

    return Patch(ops=ops, note=f"{intent} -> {target}")


def _clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


def apply_patch(L: Ledger, p: Patch) -> Ledger:
    L2 = L.model_copy(deep=True)

    for op in p.ops:
        if op.kind == "trust_delta":
            cand = L2.candidates[op.target]
            cand.trust = _clamp(cand.trust + op.value["delta"], -5, 5)

        elif op.kind == "set_mood":
            cand = L2.candidates[op.target]
            cand.emotional_state = EmotionalState(
                mood=op.value["mood"],
                cause=op.value.get("cause", op.value["mood"]),
                decays_at_chime=op.value["decays_at_chime"],
            )

        elif op.kind == "add_belief":
            cand = L2.candidates[op.target]
            cand.believes_about_player.append(op.value["belief"])

        elif op.kind == "learn_secret":
            cand = L2.candidates[op.target]
            cand.knows_secrets.append(op.value["secret"])
            if op.value["secret"] not in L2.player.secrets_held:
                L2.player.secrets_held.append(op.value["secret"])

        elif op.kind == "add_rumor":
            from vesper.schema import Rumor
            L2.rumor_network.append(Rumor(**op.value))

        elif op.kind == "add_position":
            L2.player.stated_positions.append(StatedPosition(
                claim=op.value.get("claim", op.value["tag"]),
                tag=op.value["tag"],
                chime=L2.chime,
                audience=op.value.get("audience", []),
            ))

        elif op.kind == "advance_thread":
            for t in L2.plot_threads:
                if t.id == op.target:
                    t.state = op.value.get("state", t.state)
                    t.dormant_for = 0

        elif op.kind == "reveal_thread":
            for t in L2.plot_threads:
                if t.id == op.target:
                    t.revealed_to_player = True
                    t.dormant_for = 0

        elif op.kind == "standing_delta":
            L2.player.standing_with_vesper = _clamp(
                L2.player.standing_with_vesper + op.value["delta"], -5, 5
            )

        elif op.kind == "add_canon":
            L2.immutable_canon.append(op.value["fact"])

        else:
            raise ValueError(f"unknown op kind {op.kind}")

    return L2


def recompute_coherence(L: Ledger) -> Ledger:
    L2 = L.model_copy(deep=True)
    positions = L2.player.stated_positions
    contradictions = 0
    for i, pos in enumerate(positions):
        for earlier in positions[:i]:
            if earlier.tag in world.CONTRADICTIONS.get(pos.tag, set()):
                contradictions += 1
    L2.player.contradictions_committed = contradictions
    score = 1.0 - contradictions / max(1, len(positions))
    L2.player.coherence_score = max(0.0, round(score, 2))
    return L2


def advance_chime(L: Ledger) -> tuple[Ledger, list[str]]:
    L2 = L.model_copy(deep=True)
    events: list[str] = []

    L2.chime += 1
    L2.chimes_until_dawn = world.TOTAL_CHIMES - L2.chime

    for cand in L2.candidates.values():
        if cand.emotional_state is not None and cand.emotional_state.decays_at_chime <= L2.chime:
            cand.emotional_state = None

    touched_threads: set[str] = set()
    for rumor in L2.rumor_network:
        if not rumor.applied and rumor.reaches_vesper_at <= L2.chime:
            L2.player.standing_with_vesper = _clamp(
                L2.player.standing_with_vesper + rumor.vesper_delta, -5, 5
            )
            rumor.applied = True
            events.append(f"Vesper has heard: {rumor.fact}")

    for thread in L2.plot_threads:
        if thread.state != "resolved":
            if thread.id in touched_threads:
                thread.dormant_for = 0
            else:
                thread.dormant_for += 1

    L2 = recompute_coherence(L2)
    return L2, events


def declare_tag_for_chime(L: Ledger) -> str:
    """Deterministic pure lookup: which position tag `declare_position` commits to this chime.

    Rotates through world.POSITION_TAGS by chime number so repeated declarations
    eventually create contradictions (by design, per Vesper's hidden rule).
    """
    return world.POSITION_TAGS[(L.chime - 1) % len(world.POSITION_TAGS)]


def dormant_thread(L: Ledger) -> PlotThread | None:
    candidates = [t for t in L.plot_threads if t.state != "resolved" and t.dormant_for >= 2]
    if not candidates:
        return None
    return max(candidates, key=lambda t: t.dormant_for)


def diff(before: Ledger, after: Ledger) -> list[str]:
    lines: list[str] = []

    for cid in before.candidates:
        b, a = before.candidates[cid], after.candidates[cid]
        if b.trust != a.trust:
            sign = "+" if a.trust >= 0 else ""
            lines.append(f"{cid}.trust {b.trust} -> {sign}{a.trust}")

    if before.player.coherence_score != after.player.coherence_score:
        lines.append(f"player.coherence {before.player.coherence_score} -> {after.player.coherence_score}")

    if before.player.standing_with_vesper != after.player.standing_with_vesper:
        lines.append(f"player.standing_with_vesper {before.player.standing_with_vesper} -> {after.player.standing_with_vesper}")

    before_rumors = {r.fact for r in before.rumor_network}
    for r in after.rumor_network:
        if r.fact not in before_rumors:
            lines.append(f"+rumor '{r.fact}'")

    return lines
