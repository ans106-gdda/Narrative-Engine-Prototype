from rich.console import Console
from rich.text import Text

from vesper.schema import AuditResult, DialogueOption, Ledger

console = Console()

BAR_WIDTH = 10


def _bar(value: int, lo: int, hi: int) -> str:
    span = hi - lo
    filled = round((value - lo) / span * BAR_WIDTH)
    filled = max(0, min(BAR_WIDTH, filled))
    return "█" * filled + "░" * (BAR_WIDTH - filled)


def _signed(n: int) -> str:
    return f"+{n}" if n > 0 else str(n)


def panel(L: Ledger, events: list[str], pruned: list[dict], audit: AuditResult | None, retries: int) -> None:
    width = 47
    title = f" CHIME {L.chime} "
    dawn = f" {L.chimes_until_dawn} until dawn "
    fill = width - len(title) - len(dawn) - 2
    console.print(f"╔═{title}{'─' * max(fill, 1)}{dawn}═╗")

    vesper_bar = _bar(L.player.standing_with_vesper, -5, 5)
    coherence_bar = _bar(round(L.player.coherence_score * 10), 0, 10)
    console.print(
        f"  VESPER  {vesper_bar}  {_signed(L.player.standing_with_vesper)}     "
        f"COHERENCE  {coherence_bar}  {L.player.coherence_score}"
    )
    console.print()

    for cid, cand in L.candidates.items():
        name = cid.capitalize()
        bar = _bar(cand.trust, -5, 5)
        mood = "—"
        if cand.emotional_state is not None:
            mood = f"{cand.emotional_state.mood}   (fades at {cand.emotional_state.decays_at_chime})"
        console.print(f"  {name:<9} {bar}  {_signed(cand.trust):>3}   {mood}")
    console.print()

    console.print("  RUMOR NETWORK")
    if not L.rumor_network:
        console.print("   (none)")
    for r in L.rumor_network:
        mark = "✓" if r.true else "✗"
        known = ", ".join(r.known_by) if r.known_by else "—"
        arrival = "→ Vesper NOW" if r.applied else f"→ Vesper at {r.reaches_vesper_at}"
        console.print(f'   {mark} "{r.fact}"   {known}           {arrival}')
    console.print()

    console.print("  PRUNED OPTIONS")
    if not pruned:
        console.print("   (none)")
    for p in pruned:
        intent = p["intent"] if p["target"] is None else p["intent"]
        console.print(f"   ✗ {intent:<15} · {p['reason']}")
    console.print()

    if audit is None:
        console.print("  AUDIT  — (not yet run)")
    else:
        icon = "✅" if audit.consistent else "❌"
        status = "consistent" if audit.consistent else "inconsistent"
        console.print(f"  AUDIT  {icon} {status} ({retries} retry)" if retries == 1
                       else f"  AUDIT  {icon} {status} ({retries} retries)")

    console.print(f"╚{'═' * (width - 2)}╝")


def show_options(options: list[DialogueOption]) -> None:
    for i, opt in enumerate(options, start=1):
        console.print(f"  {i}. {opt.surface_text}")
