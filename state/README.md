# State Management System

Event sourcing and state store for Robot Writers Room narrative tracking.

## Overview

This module provides an **append-only event log** for tracking all state changes in the narrative system. Events are stored as JSON Lines (JSONL) with a materialized index for fast card queries.

## Key Concepts

### Events
All state changes are recorded as immutable events with:
- **Triple structure**: `(subject, predicate, object)` - e.g., `("card:roswell", "category", "World Element")`
- **Operations**: `assert`, `set`, or `retract`
- **Timestamps**: Real-time or diegetic (for narrative purposes)
- **Actor tracking**: Which agent/tool made the change
- **Metadata**: Tags, source info, etc.

### Materialized Views
The current state is computed from the event log. This allows:
- Time-travel queries ("what was the state on July 8, 1947?")
- Audit trails (who changed what and when)
- Coexistence of contradictory claims (press vs. military sources)

## Quick Start

### Basic Usage

```python
from state import Event, JSONLStore, Query

# Initialize store
store = JSONLStore()

# Create an event
event = Event.new(
    actor="Scribe",
    op="set",
    triple=("card:roswell", "name", "Roswell Incident"),
    meta={"tags": ["card", "ufo"]}
)

# Append to log
store.append([event])

# Query current state
card = store.read_card("roswell")
print(card)  # {"name": "Roswell Incident"}
```

### Card Operations

```python
# Create/update a card
store.upsert_card("area51", {
    "name": "Area 51",
    "category": "Location",
    "year_established": "1955"
})

# Read a card
card = store.read_card("area51")

# List all cards
all_cards = store.list_cards()
```

### Time-Based Queries

```python
from state import Query

# Get events from the last 30 minutes
query: Query = {
    "s": "card:roswell",
    "since": "-30m",
    "limit": 50
}
events = store.query(query)

# Get events with specific tag
query = {
    "tag": "ufo",
    "since": "1947-07-01T00:00:00Z",
    "until": "1947-08-01T00:00:00Z"
}
events = store.query(query)
```

### Diegetic Timestamps

For narrative events that occurred at a specific story time:

```python
event = Event.new(
    actor="Researcher",
    op="assert",
    triple=("card:roswell", "crash_date", "1947-07-08"),
    meta={"source": "military_report", "tags": ["historical"]},
    ts="1947-07-08T00:00:00Z"  # Explicit diegetic timestamp
)
store.append([event])
```

## File Structure

```
data/
├── events.jsonl           # Append-only event log (one JSON object per line)
└── cards.index.json       # Materialized card index (for fast queries)
```

## Configuration

See `.env.example` for configuration options:

- `STATE_DATA_DIR`: Data directory (default: `data/`)
- `STATE_BACKEND`: Backend implementation (currently: `jsonl`)
- `USE_STATE_FOR_READS`: Enable reading from state store
- `DUAL_WRITE`: Write to both state store and legacy `cards.json`

## Testing

Run the test suite:

```bash
python3 tests/test_state_store.py
```

## Next Steps

- **Phase 2**: Integrate with Card Tools (dual-write mode)
- **Phase 3**: Add CLI tools (`state_tail.py`, `export_cards.py`)
- **Phase 4**: Context shard injection for agents
- **Phase 5**: Full diegetic timestamp support

## Architecture

See `StateInterface-overview.md` in the project root for detailed architecture documentation.
