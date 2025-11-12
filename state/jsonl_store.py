# state/jsonl_store.py
"""
JSONL-based implementation of the StateStore protocol.

This module provides an append-only event log stored as JSON Lines (JSONL),
with a materialized index for efficient card queries.
"""
from __future__ import annotations
import json
import os
from typing import Any, Dict, Iterable, List, Optional, Tuple
import datetime as _dt
from collections import defaultdict

from .store import Event, StateStore, Query, parse_relative

DEFAULT_DATA_DIR = os.environ.get("STATE_DATA_DIR", "data")
EVENTS_FILE = os.path.join(DEFAULT_DATA_DIR, "events.jsonl")
CARDS_INDEX_FILE = os.path.join(DEFAULT_DATA_DIR, "cards.index.json")


def _ensure_dirs():
    """Ensure data directory and files exist."""
    os.makedirs(DEFAULT_DATA_DIR, exist_ok=True)
    if not os.path.exists(EVENTS_FILE):
        with open(EVENTS_FILE, "w", encoding="utf-8") as f:
            pass
    if not os.path.exists(CARDS_INDEX_FILE):
        with open(CARDS_INDEX_FILE, "w", encoding="utf-8") as f:
            f.write("{}")


def _dt_from_iso(s: str) -> _dt.datetime:
    """Parse ISO8601 timestamp to datetime."""
    return _dt.datetime.fromisoformat(s.replace("Z", ""))


class JSONLStore(StateStore):
    """Append-only JSONL event log with materialized index for cards.

    This implementation stores events in a JSONL file (one JSON object per line)
    and maintains an in-memory index of the latest card states for fast queries.

    The event log is immutable (append-only), providing a complete audit trail
    of all state changes over time.
    """

    def __init__(self, data_dir: Optional[str] = None):
        """Initialize the store.

        Args:
            data_dir: Optional custom data directory (defaults to "data/")
        """
        if data_dir:
            global DEFAULT_DATA_DIR, EVENTS_FILE, CARDS_INDEX_FILE
            DEFAULT_DATA_DIR = data_dir
            EVENTS_FILE = os.path.join(DEFAULT_DATA_DIR, "events.jsonl")
            CARDS_INDEX_FILE = os.path.join(DEFAULT_DATA_DIR, "cards.index.json")

        _ensure_dirs()

        # Build minimal in-memory indices
        self._latest_by_sp: Dict[Tuple[str, str], Tuple[str, str]] = {}
        self._cards: Dict[str, Dict[str, Any]] = self._load_cards_index()

    # ---------- Low-level I/O ----------

    def _load_cards_index(self) -> Dict[str, Dict[str, Any]]:
        """Load the materialized card index from disk."""
        try:
            with open(CARDS_INDEX_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_cards_index(self) -> None:
        """Save the materialized card index to disk."""
        tmp = CARDS_INDEX_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._cards, f, indent=2, ensure_ascii=False)
        os.replace(tmp, CARDS_INDEX_FILE)

    def _append_line(self, d: Dict[str, Any]) -> None:
        """Append a single JSON object to the event log."""
        with open(EVENTS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")

    def _iter_events(self):
        """Iterate over all events in the log."""
        with open(EVENTS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    yield obj
                except Exception:
                    continue

    # ---------- StateStore Protocol Implementation ----------

    def append(self, events: Iterable[Event]) -> List[str]:
        """Append events to the log and update materialized indices.

        Args:
            events: Iterable of Event objects to append

        Returns:
            List of event IDs that were appended
        """
        ids: List[str] = []
        for ev in events:
            d = ev.to_dict()
            self._append_line(d)
            ids.append(ev.id)

            # Update materialized index for simple lookups
            s, p, o = ev.triple
            if ev.op in ("set", "assert"):
                self._latest_by_sp[(s, p)] = (ev.ts, o)
            elif ev.op == "retract":
                self._latest_by_sp.pop((s, p), None)

        return ids

    def query(self, q: Query) -> List[Event]:
        """Query events matching pattern and time filters.

        Args:
            q: Query parameters

        Returns:
            List of matching events (sorted by timestamp)
        """
        s = q.get("s")
        p = q.get("p")
        o = q.get("o")
        tag = q.get("tag")
        limit = q.get("limit", 100)
        newest_first = q.get("newest_first", True)

        since_s = q.get("since")
        until_s = q.get("until")
        since = parse_relative(since_s) if since_s else None
        until = parse_relative(until_s) if until_s else None

        out: List[Event] = []
        for obj in self._iter_events():
            ts = _dt_from_iso(obj.get("ts", "1970-01-01T00:00:00"))
            if since and ts < since:
                continue
            if until and ts > until:
                continue

            tr = tuple(obj.get("triple", []))
            if len(tr) != 3:
                continue

            if s is not None and tr[0] != s:
                continue
            if p is not None and tr[1] != p:
                continue
            if o is not None and tr[2] != o:
                continue

            if tag is not None:
                meta = obj.get("meta") or {}
                tags = meta.get("tags") or []
                if tag not in tags:
                    continue

            out.append(Event(
                id=obj["id"],
                ts=obj["ts"],
                actor=obj["actor"],
                op=obj["op"],
                triple=(tr[0], tr[1], tr[2]),
                meta=obj.get("meta") or {},
            ))

            if len(out) >= limit:
                break

        if newest_first:
            out.sort(key=lambda e: e.ts, reverse=True)
        else:
            out.sort(key=lambda e: e.ts)

        return out

    def materialize(self, s: str, p: Optional[str] = None) -> Dict[str, Any]:
        """Get latest values for a subject.

        Args:
            s: Subject to materialize
            p: Optional predicate filter

        Returns:
            Dictionary mapping predicates to their latest values
        """
        res: Dict[str, Any] = {}

        # If index is empty, build it by scanning the event log
        if not self._latest_by_sp:
            for obj in self._iter_events():
                tr = obj.get("triple", [])
                if len(tr) == 3 and obj.get("op") in ("set", "assert"):
                    self._latest_by_sp[(tr[0], tr[1])] = (obj.get("ts"), tr[2])

        # Query the materialized index
        for (ss, pp), (ts, val) in self._latest_by_sp.items():
            if ss != s:
                continue
            if p is not None and pp != p:
                continue
            res[pp] = val

        return res

    # ---------- Card Convenience Methods ----------

    def _normalize_card_id(self, card_id: str) -> str:
        """Ensure card ID has 'card:' prefix."""
        if card_id.startswith("card:"):
            return card_id
        return f"card:{card_id}"

    def upsert_card(self, card_id: str, props: Dict[str, Any]) -> None:
        """Create or update a card.

        Args:
            card_id: Card identifier (will be prefixed with "card:" if needed)
            props: Dictionary of card properties to set
        """
        card_key = self._normalize_card_id(card_id)

        # Update materialized card index
        cur = self._cards.get(card_key, {})
        cur.update(props)
        self._cards[card_key] = cur
        self._save_cards_index()

        # Emit events for each property
        evs: List[Event] = []
        for k, v in props.items():
            evs.append(Event.new(
                actor="CardTool",
                op="set",
                triple=(card_key, k, str(v)),
                meta={"tags": ["card"], "card_id": card_id},
            ))
        self.append(evs)

    def read_card(self, card_id: str) -> Dict[str, Any]:
        """Read current state of a card.

        Args:
            card_id: Card identifier

        Returns:
            Dictionary of card properties (empty if card doesn't exist)
        """
        key = self._normalize_card_id(card_id)
        return dict(self._cards.get(key, {}))

    def list_cards(self) -> List[Dict[str, Any]]:
        """List all cards with their current properties.

        Returns:
            List of card dictionaries (each includes "id" field)
        """
        out = []
        for cid, props in self._cards.items():
            out.append({"id": cid, **props})
        return out

    # ---------- Utilities ----------

    def tail(self, n: int = 50) -> List[Event]:
        """Get the last N events from the log.

        Uses efficient tail reading by seeking from end of file.

        Args:
            n: Number of events to retrieve

        Returns:
            List of recent events
        """
        lines: List[str] = []
        with open(EVENTS_FILE, "rb") as f:
            try:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                block = 4096
                buf = b""
                while size > 0 and len(lines) < n:
                    step = min(block, size)
                    size -= step
                    f.seek(size)
                    buf = f.read(step) + buf
                    parts = buf.split(b"\n")
                    buf = parts[0]
                    lines = parts[1:] + lines
                if buf:
                    lines = [buf] + lines
            except Exception:
                pass

        lines = [ln.decode("utf-8").strip() for ln in lines if ln.strip()]
        events: List[Event] = []
        for ln in lines[-n:]:
            try:
                obj = json.loads(ln)
                tr = tuple(obj.get("triple", []))
                events.append(Event(
                    id=obj["id"],
                    ts=obj["ts"],
                    actor=obj["actor"],
                    op=obj["op"],
                    triple=(tr[0], tr[1], tr[2]),
                    meta=obj.get("meta") or {},
                ))
            except Exception:
                continue

        return events

    def export_cards(self) -> Dict[str, Dict[str, Any]]:
        """Export all cards as a dictionary.

        Returns:
            Dictionary mapping card IDs to their properties
        """
        return dict(self._cards)


# ---------- Singleton Factory ----------

_STORE_SINGLETON: Optional[JSONLStore] = None


def get_store() -> JSONLStore:
    """Get the singleton JSONLStore instance.

    Returns:
        Shared JSONLStore instance
    """
    global _STORE_SINGLETON
    if _STORE_SINGLETON is None:
        _STORE_SINGLETON = JSONLStore()
    return _STORE_SINGLETON
