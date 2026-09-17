"""Human-readable shadow monitoring for validating the engine before rollout."""

from __future__ import annotations

from .models import DecisionStatus
from .shadow import ShadowSnapshot


def format_shadow_report(snapshot: ShadowSnapshot, max_markets: int = 8) -> str:
    """Return a compact report suitable for UI/logging.

    This is intentionally not connected to Telegram. It is a verification aid for
    developers/operators while the engine remains in shadow mode.
    """
    rows = sorted(
        snapshot.assessments,
        key=lambda a: (
            a.decision == DecisionStatus.BET_ELIGIBLE,
            a.expected_value if a.expected_value is not None else float("-inf"),
            a.edge if a.edge is not None else float("-inf"),
        ),
        reverse=True,
    )[:max_markets]

    lines = [
        f"SHADOW fixture={snapshot.fixture_id}",
        f"modelo={snapshot.model_name}",
        f"xG esperado={snapshot.expected_home_goals:.2f} x {snapshot.expected_away_goals:.2f}",
        f"qualidade_dados={snapshot.data_quality:.0%} qualidade_modelo={snapshot.model_quality:.0%}",
        "",
    ]

    for item in rows:
        line = f"{item.market} {item.selection}"
        if item.line is not None:
            line += f" {item.line}"
        line += f" | p={item.probability:.1%}"
        if item.offered_odds is not None:
            line += f" odd={item.offered_odds:.2f}"
        if item.edge is not None:
            line += f" edge={item.edge:+.1%}"
        if item.expected_value is not None:
            line += f" EV={item.expected_value:+.1%}"
        line += f" | {item.decision.value}"
        lines.append(line)

    return "\n".join(lines)
