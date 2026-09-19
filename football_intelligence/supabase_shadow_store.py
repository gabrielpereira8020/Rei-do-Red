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
    """Append-only Supabase adapter for shadow-mode observations."""

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

    def _to_row(
        self,
        snapshot: ShadowSnapshot,
        *,
        match_meta: dict[str, Any] | None = None,
        gemini_text: str | None = None,
    ) -> dict[str, Any]:
        match_meta = match_meta or {}
        return {
            "fixture_id": snapshot.fixture_id,
            "generated_at": snapshot.generated_at.isoformat(),
            "model_name": snapshot.model_name,
            "expected_home_goals": snapshot.expected_home_goals,
            "expected_away_goals": snapshot.expected_away_goals,
            "data_quality": snapshot.data_quality,
            "model_quality": snapshot.model_quality,
            "assessments": [self._assessment_to_dict(item) for item in snapshot.assessments],
            "home_team": match_meta.get("home_team"),
            "away_team": match_meta.get("away_team"),
            "league_name": match_meta.get("league_name"),
            "kickoff": match_meta.get("kickoff"),
            "gemini_text": gemini_text,
        }

    def save(
        self,
        snapshot: ShadowSnapshot,
        *,
        match_meta: dict[str, Any] | None = None,
        gemini_text: str | None = None,
    ) -> None:
        """Append one immutable shadow snapshot with optional match/Gemini context."""
        self.client.table(self.table_name).insert(
            self._to_row(snapshot, match_meta=match_meta, gemini_text=gemini_text)
        ).execute()

    def list_for_fixture(self, fixture_id: int, limit: int = 100) -> Sequence[dict[str, Any]]:
        response = (
            self.client.table(self.table_name)
            .select("*")
            .eq("fixture_id", fixture_id)
            .order("generated_at", desc=True)
            .limit(limit)
            .execute()
        )
        return tuple(response.data or ())
