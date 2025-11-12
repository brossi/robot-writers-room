What stays untouched
	•	Agents, prompts, DialogueSimulator, and run.py turn-taking remain as they are.  ￼

Core improvements (small, focused PR)

1) Add a StateStore interface + JSONL implementation

Why: Replace ad-hoc cards.json persistence with an append-only, queryable event log (and keep a materialized view).
Files to add
	•	state/__init__.py
	•	state/store.py (interface)
	•	state/jsonl_store.py (JSONL events + on-load materialization)

Event schema (append-only)

{
  "id": "uuid",
  "ts": "1947-07-09T12:15:00Z",     // diegetic or real time
  "actor": "Scribe",                // which agent/tool
  "op": "set|assert|retract",
  "triple": ["card:42","category","World Element"],
  "meta": {"source": "scribe", "tags": ["card"]}
}

Materialized view: last value per (s,p) + simple indices for s and tags.

This cleanly subsumes the current Card Tools JSON file while keeping a drop-in seam for future backends. The README already centralizes card operations and describes JSON persistence—exactly the seam we’ll hook.  ￼

2) Add a thin adapter for Card Tools

Why: Keep agent code unchanged; only the tools switch to the store.

Edits
	•	In the Card Tools module referenced in the README (Create/Read/Update/Delete/List), replace direct file I/O with:
	•	store.upsert_card(card_id, props) (writes)
	•	store.read_card(card_id) and store.list_cards() (reads)
	•	Keep dual-write to cards.json for one release to de-risk.

README’s Card Tools section shows the exact classes and behaviors to wrap (Create/Read/Update/Delete/List via cards.json).  ￼

3) Add a tiny “context shard” hook before agent prompts

Why: Let any agent optionally pull a small, relevant slice of state without changing prompts.

Edits
	•	In run.py (or Agents.py helper), add:

def build_context_shard(focus_id: str):
    card = store.read_card(f"card:{focus_id}")
    recent = store.query({"s": f"card:{focus_id}", "since": "-30m", "limit": 30})
    return {"card": card, "recent_events": recent}


	•	Thread this dict into the existing per-turn context block that agents already use (keep formatting minimal).

This preserves the existing round-robin loop and agent roles.  ￼

4) Configuration, not surgery

Why: Make it easy to toggle/rollback.
	•	Add .env or config keys:
	•	STATE_BACKEND=jsonl (future: graphiti)
	•	USE_STATE_FOR_READS=true|false (default: false → shadow mode)
	•	If reads fail (key missing), fall back to legacy cards.json.

5) CLI + exporter (developer ergonomics)

Why: Your project is artifact-heavy; you’ll want to inspect/curate the canon.
	•	tools/state_tail.py — tail last N events
	•	tools/export_cards.py — write a pretty cards.json/Markdown dump from state
	•	tools/state_validate.py — catch conflicting sets on same (s,p) within a tick

6) Tests you actually need (fast, high-signal)
	•	Parity tests: Card Tools calls result in identical cards.json content pre/post (while dual-writing).
	•	Event → materialize: Setting ("card:1","category","World") twice yields the latest only; history remains in events.
	•	Time-scoped query: since filter returns the right slice.
	•	Golden prompt snapshot: Capture an agent prompt before/after enabling context shard; only the preface changes.

Acceptance criteria (done = shippable)
	1.	Running run.py still produces the same files (outline.txt, characters.txt, etc.).  ￼
	2.	Card operations work with USE_STATE_FOR_READS=true and false.
	3.	events.jsonl grows with meaningful, source-tagged entries for every card change.
	4.	A single command prints a coherent per-card timeline for audit.
	5.	No change to prompts or agent logic beyond an optional context block.

File-level change list (concise)
	•	ADD state/store.py, state/jsonl_store.py
	•	ADD tools/state_tail.py, tools/export_cards.py, tools/state_validate.py
	•	MOD Card Tools module: replace file I/O with store calls; keep dual-write to cards.json (as currently described).  ￼
	•	MOD (tiny) run.py or Agents.py: build_context_shard() + optional injection
	•	ADD config.py / .env.example with the two flags

Why this is enough for your UFO narrative now
	•	You get a living archive that tracks what each artifact “asserted” and when (perfect for staged, decades-long reveals).
	•	Character/world stabilization becomes mechanical: the state answers “who/what/where as-of YYYY,” while allowing contradictory claims to coexist (press vs. military vs. private letters).
	•	No orchestration churn: your current multi-agent pipeline remains intact.
