"""Supabase persistence adapter for shadow snapshots.

This module is intentionally isolated from the legacy tables. It writes only to a
new append-only table named ``football_intelligence_shadow_snapshots``.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Sequence

from .models import DecisionStatus
from .shadow import ShadowSnapshot


SHADOW_TABLE = "football_intelligence_shadow_snapshots"


class SupabaseShadowSnapshotStore:
    """Append-only Supabase adapter for shadow-mode observations.

    The adapter expects an already-created Supabase client. It never touches
    ``historico``, ``radar_estado`` or ``alavancagem_historico``.
    """

    def __init__(self, client: Any, table_name: str = SHADOW_TABLE) -> None:
        self.client = client
        self.table_name = table_name

    @staticmethod
    def _assessment_to_dict(item: Any) -> dict[str, Any]:
        payload = asdict(item)
        decision = payload.get("decision")
        if isinstance(decision, DecisionStatus):
            payload["decision"] = decision.value
        return payload

    def _to_row(self, snapshot: ShadowSnapshot) -> dict[str, Any]:
        return {
            "fixture_id": snapshot.fixture_id,
            "generated_at": snapshot.generated_at.isoformat(),
            "model_name": snapshot.model_name,
            "expected_home_goals": snapshot.expected_home_goals,
            "expected_away_goals": snapshot.expected_away_goals,
            "data_quality": snapshot.data_quality,
            "model_quality": snapshot.model_quality,
            "assessments": [self._assessment_to_dict(item) for item in snapshot.assessments],
        }

    def save(self, snapshot: ShadowSnapshot) -> None:
        """Append one immutable shadow snapshot."""
        self.client.table(self.table_name).insert(self._to_row(snapshot)).execute()

    def list_for_fixture(self, fixture_id: int, limit: int = 100) -> Sequence[dict[str, Any]]:
        """Return newest persisted shadow snapshots for one fixture."""
        response = (
            self.client.table(self.table_name)
            .select("*")
            .eq("fixture_id", fixture_id)
            .order("generated_at", desc=True)
            .limit(limit)
            .execute()
        )
        return tuple(response.data or ())
