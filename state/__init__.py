"""
State management for Robot Writers Room.

This package provides event sourcing and state store capabilities
for tracking narrative elements across time.
"""

from .store import Event, StateStore, Query
from .jsonl_store import JSONLStore, get_store

__all__ = ["Event", "StateStore", "Query", "JSONLStore", "get_store"]
