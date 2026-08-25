"""Regression tests for the deterministic pre-checks.

The absent_candidate rule originally used a blacklist of common words, which
flagged every capitalised noun in the prose -- including "Ashgrove", a name
from immutable_canon. Across nine real narrations it produced 10 violations,
all false, costing two wasted retries per turn. These tests pin the corrected
behaviour: whitelist + speech/action-verb proximity.
"""
from vesper import ledger
from vesper.agents.auditor import _pre_checks


def _absent(text):
    return [v for v in _pre_checks(ledger.new_game(), text) if v.rule == "absent_candidate"]


def test_canon_proper_nouns_are_not_invented_characters():
    assert _absent("Marrow sets down the decanter in House Ashgrove and says nothing.") == []


def test_capitalised_common_words_are_ignored():
    assert _absent("The sixth chime is still shivering. Forty years of service taught him silence.") == []


def test_full_names_are_accepted():
    assert _absent("Ilsabet Crane lifts her lamp. Vesper Ashgrove watches from the stair.") == []


def test_word_after_closing_quote_starts_a_sentence():
    assert _absent('"Everyone is measuring, sir."  Still, he sets the tray on the rail.') == []


def test_invented_character_who_acts_is_caught():
    found = _absent("Marrow nods. Then Gideon steps from the alcove and says your name.")
    assert len(found) == 1 and found[0].quote == "Gideon"
