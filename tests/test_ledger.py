from vesper import ledger, world


def test_new_game():
    L = ledger.new_game()
    assert len(L.candidates) == 3
    assert all(c.trust == 0 for c in L.candidates.values())
    assert len(L.immutable_canon) == len(world.IMMUTABLE_CANON)


def test_build_trust_twice():
    L = ledger.new_game()
    p1 = ledger.resolve_effects(L, "build_trust", "marrow")
    L = ledger.apply_patch(L, p1)
    p2 = ledger.resolve_effects(L, "build_trust", "marrow")
    L = ledger.apply_patch(L, p2)
    assert L.candidates["marrow"].trust == 4


def test_trust_clamps_at_5():
    L = ledger.new_game()
    for _ in range(3):
        p = ledger.resolve_effects(L, "build_trust", "marrow")
        L = ledger.apply_patch(L, p)
    assert L.candidates["marrow"].trust == 5


def test_contradiction_and_coherence():
    L = ledger.new_game()
    p1 = ledger.resolve_effects(L, "declare_position", None, tag="fearless")
    L = ledger.apply_patch(L, p1)
    p2 = ledger.resolve_effects(L, "declare_position", None, tag="fearful")
    L = ledger.apply_patch(L, p2)
    L = ledger.recompute_coherence(L)
    assert L.player.contradictions_committed == 1
    assert L.player.coherence_score == 0.5


def test_rumor_applies_once_at_correct_chime():
    L = ledger.new_game()
    from vesper.schema import Rumor
    L.rumor_network.append(Rumor(
        fact="test rumor", true=True, origin_chime=1, spread_by="player",
        known_by=[], reaches_vesper_at=4, vesper_delta=2,
    ))
    L, events = ledger.advance_chime(L)
    assert L.chime == 2
    assert not L.rumor_network[0].applied
    L, events = ledger.advance_chime(L)
    assert L.chime == 3
    assert not L.rumor_network[0].applied
    standing_before = L.player.standing_with_vesper
    L, events = ledger.advance_chime(L)
    assert L.chime == 4
    assert L.rumor_network[0].applied
    assert L.player.standing_with_vesper == standing_before + 2
    L, events = ledger.advance_chime(L)
    L, events = ledger.advance_chime(L)
    assert L.rumor_network[0].applied
    assert L.player.standing_with_vesper == standing_before + 2


def test_apply_patch_does_not_mutate_input():
    L = ledger.new_game()
    snapshot = L.model_dump()
    p = ledger.resolve_effects(L, "build_trust", "marrow")
    ledger.apply_patch(L, p)
    assert L.model_dump() == snapshot


def test_pruned_intents_at_chime_5():
    L = ledger.new_game()
    for _ in range(4):
        L, _ = ledger.advance_chime(L)
    assert L.chime == 5
    pruned = ledger.pruned_intents(L)
    build_trust_pruned = [p for p in pruned if p["intent"] == "build_trust"]
    assert len(build_trust_pruned) > 0
    for p in build_trust_pruned:
        assert "5" in p["reason"]
        assert "3" in p["reason"]
