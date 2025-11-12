# state/store.py
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any, Dict, Iterable, List, Optional, Tuple, TypedDict, Protocol
import uuid
import datetime as _dt

Triple = Tuple[str, str, str]


class Query(TypedDict, total=False):
    # Basic triple pattern (use None as wildcard)
    s: Optional[str]
    p: Optional[str]
    o: Optional[str]
    # ISO8601 or relative (e.g., "-10m", "-2h", "-3d")
    since: Optional[str]
    until: Optional[str]
    # Filter by tag (stored in meta.tags)
    tag: Optional[str]
    # Max events to return
    limit: Optional[int]
    # Reverse chronological if True
    newest_first: Optional[bool]


@dataclass(frozen=True)
class Event:
    id: str
    ts: str              # ISO8601 timestamp (UTC recommended)
    actor: str
    op: str              # "assert" | "set" | "retract"
    triple: Triple
    meta: Dict[str, Any]

    @staticmethod
    def now_iso() -> str:
        return _dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

    @staticmethod
    def new(*, actor: str, op: str, triple: Triple, meta: Optional[Dict[str, Any]] = None) -> "Event":
        return Event(
            id=str(uuid.uuid4()),
            ts=Event.now_iso(),
            actor=actor,
            op=op,
            triple=triple,
            meta=meta or {},
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class StateStore(Protocol):
    """Abstract state store interface. Implementations must be drop-in swappable."""

    # --- Event log ---
    def append(self, events: Iterable[Event]) -> List[str]:
        """Append events to the log. Returns list of event IDs."""
        ...

    def query(self, q: Query) -> List[Event]:
        """Return events matching the pattern/time filters."""
        ...

    # --- Materialized state views ---
    def materialize(self, s: str, p: Optional[str] = None) -> Dict[str, Any]:
        """Return latest values for a subject (optionally property-scoped)."""
        ...

    # --- Card convenience (backward-compatible with Card Tools) ---
    def upsert_card(self, card_id: str, props: Dict[str, Any]) -> None:
        ...

    def read_card(self, card_id: str) -> Dict[str, Any]:
        ...

    def list_cards(self) -> List[Dict[str, Any]]:
        ...

    # --- Utilities ---
    def tail(self, n: int = 50) -> List[Event]:
        ...

    def export_cards(self) -> Dict[str, Dict[str, Any]]:
        ...


def parse_relative(s: Optional[str]) -> Optional[_dt.datetime]:
    """Parse relative times like '-10m', '-2h', '-3d'. Returns UTC naive dt."""
    if not s:
        return None
    if s.endswith("Z") or "T" in s:
        try:
            # very lenient ISO
            return _dt.datetime.fromisoformat(s.replace("Z", ""))
        except Exception:
            return None
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
    if unit == "h":
        return now - _dt.timedelta(hours=val)
    if unit == "d":
        return now - _dt.timedelta(days=val)
    if unit == "w":
        return now - _dt.timedelta(weeks=val)
    return None
