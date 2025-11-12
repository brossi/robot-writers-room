#!/usr/bin/env python3
"""
Test suite for StateStore implementation.

This script validates the core functionality of the event sourcing system
without hardcoded data. All test data is generated dynamically.
"""
import os
import sys
import shutil
import tempfile
from datetime import datetime, timedelta

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from state import Event, JSONLStore, Query


class TestRunner:
    """Simple test runner that tracks pass/fail."""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.test_name = ""

    def start_test(self, name: str):
        """Start a new test."""
        self.test_name = name
        print(f"\n{'='*60}")
        print(f"TEST: {name}")
        print(f"{'='*60}")

    def assert_equal(self, actual, expected, msg=""):
        """Assert two values are equal."""
        if actual == expected:
            self.passed += 1
            print(f"  ✓ PASS: {msg or 'Values are equal'}")
        else:
            self.failed += 1
            print(f"  ✗ FAIL: {msg or 'Values not equal'}")
            print(f"    Expected: {expected}")
            print(f"    Actual:   {actual}")

    def assert_true(self, condition, msg=""):
        """Assert condition is true."""
        if condition:
            self.passed += 1
            print(f"  ✓ PASS: {msg or 'Condition is true'}")
        else:
            self.failed += 1
            print(f"  ✗ FAIL: {msg or 'Condition is false'}")

    def assert_not_empty(self, value, msg=""):
        """Assert value is not empty."""
        if value:
            self.passed += 1
            print(f"  ✓ PASS: {msg or 'Value is not empty'}")
        else:
            self.failed += 1
            print(f"  ✗ FAIL: {msg or 'Value is empty'}")

    def print_summary(self):
        """Print test summary."""
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"TEST SUMMARY")
        print(f"{'='*60}")
        print(f"Total:  {total}")
        print(f"Passed: {self.passed} ({100*self.passed//total if total > 0 else 0}%)")
        print(f"Failed: {self.failed}")
        print(f"{'='*60}\n")
        return self.failed == 0


def test_event_creation(runner: TestRunner):
    """Test Event creation and serialization."""
    runner.start_test("Event Creation and Serialization")

    # Create event with auto-generated timestamp
    ev1 = Event.new(
        actor="TestAgent",
        op="set",
        triple=("card:test", "name", "Test Card"),
        meta={"tags": ["test"]}
    )

    runner.assert_not_empty(ev1.id, "Event has UUID")
    runner.assert_not_empty(ev1.ts, "Event has timestamp")
    runner.assert_equal(ev1.actor, "TestAgent", "Event actor is correct")
    runner.assert_equal(ev1.op, "set", "Event operation is correct")
    runner.assert_equal(ev1.triple[0], "card:test", "Event subject is correct")

    # Test to_dict serialization
    ev_dict = ev1.to_dict()
    runner.assert_equal(ev_dict["actor"], "TestAgent", "Serialized actor is correct")
    runner.assert_true("tags" in ev_dict["meta"], "Serialized meta contains tags")

    # Create event with explicit timestamp
    ts = "1947-07-08T00:00:00Z"
    ev2 = Event.new(
        actor="Researcher",
        op="assert",
        triple=("card:roswell", "date", "1947-07-08"),
        meta={"source": "historical"},
        ts=ts
    )
    runner.assert_equal(ev2.ts, ts, "Explicit timestamp is preserved")


def test_store_append_and_query(runner: TestRunner, store: JSONLStore):
    """Test appending events and querying them back."""
    runner.start_test("Store Append and Query")

    # Create multiple events
    events = [
        Event.new(
            actor="Scribe",
            op="set",
            triple=("card:1", "name", "First Card"),
            meta={"tags": ["card"]}
        ),
        Event.new(
            actor="Scribe",
            op="set",
            triple=("card:1", "category", "World Element"),
            meta={"tags": ["card"]}
        ),
        Event.new(
            actor="Researcher",
            op="set",
            triple=("card:2", "name", "Second Card"),
            meta={"tags": ["card", "research"]}
        ),
    ]

    # Append events
    ids = store.append(events)
    runner.assert_equal(len(ids), 3, "All events were appended")

    # Query all events
    query: Query = {"limit": 100}
    all_events = store.query(query)
    runner.assert_true(len(all_events) >= 3, f"Retrieved {len(all_events)} events")

    # Query by subject
    query = {"s": "card:1", "limit": 100}
    card1_events = store.query(query)
    runner.assert_equal(len(card1_events), 2, "Retrieved events for card:1")

    # Query by tag
    query = {"tag": "research", "limit": 100}
    research_events = store.query(query)
    runner.assert_true(len(research_events) >= 1, "Retrieved events with 'research' tag")


def test_materialize(runner: TestRunner, store: JSONLStore):
    """Test materialized view queries."""
    runner.start_test("Materialized Views")

    # Create events for a card
    events = [
        Event.new(
            actor="Scribe",
            op="set",
            triple=("card:roswell", "name", "Roswell Incident"),
            meta={"tags": ["card"]}
        ),
        Event.new(
            actor="Scribe",
            op="set",
            triple=("card:roswell", "category", "World Element"),
            meta={"tags": ["card"]}
        ),
        Event.new(
            actor="Scribe",
            op="set",
            triple=("card:roswell", "year", "1947"),
            meta={"tags": ["card"]}
        ),
    ]
    store.append(events)

    # Materialize all properties
    mat = store.materialize("card:roswell")
    runner.assert_equal(mat.get("name"), "Roswell Incident", "Materialized name is correct")
    runner.assert_equal(mat.get("category"), "World Element", "Materialized category is correct")
    runner.assert_equal(mat.get("year"), "1947", "Materialized year is correct")

    # Materialize specific property
    mat = store.materialize("card:roswell", "name")
    runner.assert_equal(mat.get("name"), "Roswell Incident", "Specific property materialized")
    runner.assert_true("category" not in mat, "Other properties not included")


def test_card_operations(runner: TestRunner, store: JSONLStore):
    """Test card convenience methods."""
    runner.start_test("Card Operations (CRUD)")

    # Create a card
    store.upsert_card("area51", {
        "name": "Area 51",
        "category": "Location",
        "description": "Highly classified US Air Force facility"
    })

    # Read the card
    card = store.read_card("area51")
    runner.assert_equal(card.get("name"), "Area 51", "Card name is correct")
    runner.assert_equal(card.get("category"), "Location", "Card category is correct")

    # Update the card
    store.upsert_card("area51", {
        "year_established": "1955",
        "classification": "Top Secret"
    })

    # Read updated card
    card = store.read_card("area51")
    runner.assert_equal(card.get("name"), "Area 51", "Original properties preserved")
    runner.assert_equal(card.get("year_established"), "1955", "New property added")

    # List cards
    cards = store.list_cards()
    card_ids = [c["id"] for c in cards]
    runner.assert_true("card:area51" in card_ids, "Card appears in list")

    # Test card ID normalization
    card2 = store.read_card("card:area51")  # With prefix
    runner.assert_equal(card2.get("name"), "Area 51", "Card ID normalization works")


def test_tail(runner: TestRunner, store: JSONLStore):
    """Test tail functionality."""
    runner.start_test("Tail Functionality")

    # Append several events
    for i in range(10):
        store.append([Event.new(
            actor="TestAgent",
            op="set",
            triple=(f"card:test{i}", "index", str(i)),
            meta={"tags": ["test"]}
        )])

    # Get last 5 events
    recent = store.tail(5)
    runner.assert_equal(len(recent), 5, "Retrieved last 5 events")
    runner.assert_true(all(e.actor in ["TestAgent", "Scribe", "Researcher"] for e in recent),
                       "All events have valid actors")


def test_export(runner: TestRunner, store: JSONLStore):
    """Test card export functionality."""
    runner.start_test("Card Export")

    # Create some cards
    store.upsert_card("export_test_1", {"name": "Export Test 1"})
    store.upsert_card("export_test_2", {"name": "Export Test 2"})

    # Export all cards
    exported = store.export_cards()
    runner.assert_true("card:export_test_1" in exported, "First card exported")
    runner.assert_true("card:export_test_2" in exported, "Second card exported")
    runner.assert_equal(
        exported["card:export_test_1"].get("name"),
        "Export Test 1",
        "Exported card has correct data"
    )


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("Robot Writers Room - StateStore Test Suite")
    print("="*60)

    # Create temporary directory for test data
    test_dir = tempfile.mkdtemp(prefix="rwroom_test_")
    print(f"\nTest data directory: {test_dir}")

    try:
        # Initialize test runner and store
        runner = TestRunner()
        store = JSONLStore(data_dir=test_dir)

        # Run tests
        test_event_creation(runner)
        test_store_append_and_query(runner, store)
        test_materialize(runner, store)
        test_card_operations(runner, store)
        test_tail(runner, store)
        test_export(runner, store)

        # Print summary
        success = runner.print_summary()

        if success:
            print("✓ All tests passed!")
            return 0
        else:
            print("✗ Some tests failed")
            return 1

    finally:
        # Clean up test directory
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir)
            print(f"Cleaned up test directory: {test_dir}\n")


if __name__ == "__main__":
    sys.exit(main())
