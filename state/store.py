# state/store.py
"""
Core state store interface and event definitions.

This module defines the Event class and StateStore protocol for event sourcing
in the Robot Writers Room narrative system.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any, Dict, Iterable, List, Optional, Tuple, TypedDict, Protocol
import uuid
import datetime as _dt

Triple = Tuple[str, str, str]


class Query(TypedDict, total=False):
    """Query parameters for filtering events.

    Attributes:
        s: Subject filter (use None as wildcard)
        p: Predicate filter (use None as wildcard)
        o: Object filter (use None as wildcard)
        since: ISO8601 timestamp or relative time (e.g., "-10m", "-2h", "-3d")
        until: ISO8601 timestamp or relative time
        tag: Filter by tag (stored in meta.tags)
        limit: Maximum number of events to return
        newest_first: Return events in reverse chronological order if True
    """
    s: Optional[str]
    p: Optional[str]
    o: Optional[str]
    since: Optional[str]
    until: Optional[str]
    tag: Optional[str]
    limit: Optional[int]
    newest_first: Optional[bool]


@dataclass(frozen=True)
class Event:
    """Immutable event record for the event log.

    Events use a triple-based structure (subject, predicate, object) to represent
    state changes. For example: ("card:roswell", "category", "World Element")

    Attributes:
        id: Unique event identifier (UUID)
        ts: ISO8601 timestamp (UTC recommended)
        actor: Agent or tool that created this event (e.g., "Scribe", "Researcher")
        op: Operation type - "assert", "set", or "retract"
        triple: Subject-predicate-object tuple representing the state change
        meta: Additional metadata (e.g., tags, source info)
    """
    id: str
    ts: str
    actor: str
    op: str  # "assert" | "set" | "retract"
    triple: Triple
    meta: Dict[str, Any]

    @staticmethod
    def now_iso() -> str:
        """Generate current UTC timestamp in ISO8601 format."""
        return _dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

    @staticmethod
    def new(
        *,
        actor: str,
        op: str,
        triple: Triple,
        meta: Optional[Dict[str, Any]] = None,
        ts: Optional[str] = None
    ) -> "Event":
        """Create a new event with auto-generated ID and timestamp.

        Args:
            actor: Name of the agent or tool creating the event
            op: Operation type ("assert", "set", or "retract")
            triple: (subject, predicate, object) tuple
            meta: Optional metadata dictionary
            ts: Optional explicit timestamp (for diegetic time). If None, uses current time.

        Returns:
            New Event instance
        """
        return Event(
            id=str(uuid.uuid4()),
            ts=ts if ts else Event.now_iso(),
            actor=actor,
            op=op,
            triple=triple,
            meta=meta or {},
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for serialization."""
        return asdict(self)


class StateStore(Protocol):
    """Abstract state store interface.

    Implementations must be drop-in swappable, supporting both event log
    operations and materialized view queries.
    """

    def append(self, events: Iterable[Event]) -> List[str]:
        """Append events to the log.

        Args:
            events: Iterable of Event objects to append

        Returns:
            List of event IDs that were appended
        """
        ...

    def query(self, q: Query) -> List[Event]:
        """Query events matching the pattern and time filters.

        Args:
            q: Query parameters (subject, predicate, object, time range, tags)

        Returns:
            List of matching events
        """
        ...

    def materialize(self, s: str, p: Optional[str] = None) -> Dict[str, Any]:
        """Get latest values for a subject.

        Args:
            s: Subject to materialize
            p: Optional predicate filter (if None, returns all predicates)

        Returns:
            Dictionary mapping predicates to their latest values
        """
        ...

    def upsert_card(self, card_id: str, props: Dict[str, Any]) -> None:
        """Create or update a card (backward-compatible with Card Tools).

        Args:
            card_id: Card identifier (will be prefixed with "card:" if needed)
            props: Dictionary of card properties to set
        """
        ...

    def read_card(self, card_id: str) -> Dict[str, Any]:
        """Read current state of a card.

        Args:
            card_id: Card identifier

        Returns:
            Dictionary of card properties
        """
        ...

    def list_cards(self) -> List[Dict[str, Any]]:
        """List all cards with their current properties.

        Returns:
            List of card dictionaries (each includes "id" field)
        """
        ...

    def tail(self, n: int = 50) -> List[Event]:
        """Get the last N events from the log.

        Args:
            n: Number of events to retrieve

        Returns:
            List of recent events
        """
        ...

    def export_cards(self) -> Dict[str, Dict[str, Any]]:
        """Export all cards as a dictionary.

        Returns:
            Dictionary mapping card IDs to their properties
        """
        ...


def parse_relative(s: Optional[str]) -> Optional[_dt.datetime]:
    """Parse relative time strings or ISO8601 timestamps.

    Supports:
        - ISO8601: "2025-11-12T10:30:00Z"
        - Relative minutes: "-10m"
        - Relative hours: "-2h"
        - Relative days: "-3d"
        - Relative weeks: "-2w"

    Args:
        s: Time string to parse

    Returns:
        UTC datetime object, or None if parsing fails
    """
    if not s:
        return None

    # Try ISO8601
    if s.endswith("Z") or "T" in s:
        try:
            return _dt.datetime.fromisoformat(s.replace("Z", ""))
        except Exception:
            return None

    # Try relative time
    if not s.startswith("-"):
        return None

    num = "".join(ch for ch in s if ch.isdigit())
    unit = s[-1].lower() if s[-1].isalpha() else "m"

    try:
        val = int(num)
    except Exception:
        return None

    now = _dt.datetime.utcnow()
    if unit == "m":
        return now - _dt.timedelta(minutes=val)
    elif unit == "h":
        return now - _dt.timedelta(hours=val)
    elif unit == "d":
        return now - _dt.timedelta(days=val)
    elif unit == "w":
        return now - _dt.timedelta(weeks=val)

    return None
