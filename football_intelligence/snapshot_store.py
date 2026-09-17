"""Append-only in-memory snapshot contracts for shadow analysis.

Persistence adapters (Supabase, files, etc.) can implement the same interface later
without coupling the statistical engine to storage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, Sequence

from .shadow import ShadowSnapshot


class ShadowSnapshotStore(Protocol):
    def save(self, snapshot: ShadowSnapshot) -> None: ...

    def list_for_fixture(self, fixture_id: int) -> Sequence[ShadowSnapshot]: ...


@dataclass
class InMemoryShadowSnapshotStore:
    """Simple append-only store used for tests and local validation."""

    _items: list[ShadowSnapshot] = field(default_factory=list)

    def save(self, snapshot: ShadowSnapshot) -> None:
        self._items.append(snapshot)

    def list_for_fixture(self, fixture_id: int) -> Sequence[ShadowSnapshot]:
        return tuple(item for item in self._items if item.fixture_id == fixture_id)

    def all(self) -> Sequence[ShadowSnapshot]:
        return tuple(self._items)
