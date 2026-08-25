import argparse
from pathlib import Path

from vesper import engine, ledger, render, world
from vesper.agents import extractor
from vesper.schema import DialogueOption, Ledger


def _bequest(L: Ledger) -> str:
    rumor_count = len(L.rumor_network)
    coherence_weight = L.player.coherence_score * 10
    standing_weight = L.player.standing_with_vesper
    rumor_penalty = rumor_count * 0.5
    score = coherence_weight * 3 + standing_weight - rumor_penalty

    if L.player.coherence_score >= 0.75 and score >= 5:
        return "Vesper names you heir. You decided, and you held to it."
    if score >= 0:
        return "Vesper grants you a conditional inheritance, wary but not unmoved."
    return "Vesper turns away at the end. You were never truly decided."


def _save(L: Ledger, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(L.model_dump_json(indent=2))


def _print_turn(narration: str, ledger_state: Ledger, chime_events: list[str],
                 audit, retries: int, options: list[DialogueOption]) -> None:
    render.console.print()
    render.console.print(narration)
    render.console.print()
    render.panel(ledger_state, chime_events, ledger.pruned_intents(ledger_state), audit, retries)
    if options:
        render.show_options(options)


def _choose(L: Ledger, options: list[DialogueOption], raw: str) -> DialogueOption:
    if raw.isdigit():
        idx = int(raw) - 1
        if 0 <= idx < len(options):
            return options[idx]
    extracted = extractor.extract(L, raw)
    surface_text = raw if raw else "(hesitates)"
    return DialogueOption(intent=extracted.intent, target=extracted.target, surface_text=surface_text)


def interactive() -> None:
    L = ledger.new_game()
    session_path = engine.new_session_path()

    render.panel(L, [], ledger.pruned_intents(L), None, 0)

    choice: DialogueOption | None = None
    player_input = ""

    for turn_no in range(1, world.TOTAL_CHIMES + 1):
        events: list[str] = []
        result = engine.play_turn(L, choice, events)
        engine.log_turn(session_path, L.chime, player_input,
                         choice.intent if choice else "", result)
        L = result.ledger

        if turn_no < world.TOTAL_CHIMES:
            L, chime_events = ledger.advance_chime(L)
        else:
            chime_events = []

        _print_turn(result.narration, L, chime_events, result.audit, result.retries, result.options)

        if turn_no == world.TOTAL_CHIMES:
            break

        raw = input("\n> ").strip()
        if raw.lower() == "quit":
            _save(L, Path("fixtures") / "quit_autosave.json")
            print("Saved. Goodbye.")
            return

        player_input = raw
        choice = _choose(L, result.options, raw)

    print()
    print(_bequest(L))
    _save(L, Path("fixtures") / "final_autosave.json")


def single_turn(load_path: Path, player_input: str, save_path: Path | None) -> None:
    L = Ledger.model_validate_json(load_path.read_text())
    session_path = engine.new_session_path()

    extracted = extractor.extract(L, player_input)
    choice = DialogueOption(intent=extracted.intent, target=extracted.target, surface_text=player_input)

    result = engine.play_turn(L, choice, [])
    engine.log_turn(session_path, L.chime, player_input, choice.intent, result)

    render.panel(result.ledger, [], ledger.pruned_intents(result.ledger), result.audit, result.retries)
    render.console.print()
    render.console.print(result.narration)
    render.console.print()
    if result.options:
        render.show_options(result.options)

    if save_path:
        _save(result.ledger, save_path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--save", type=Path, default=None)
    parser.add_argument("--load", type=Path, default=None)
    parser.add_argument("--input", type=str, default=None)
    args = parser.parse_args()

    if args.load and args.input:
        single_turn(args.load, args.input, args.save)
        return

    interactive()


if __name__ == "__main__":
    main()
