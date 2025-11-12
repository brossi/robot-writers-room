#!/usr/bin/env python3
"""
Test dual-write integration between Card Tools and StateStore.

This validates that Card Tools correctly write to both:
1. Legacy cards.json file
2. StateStore (events.jsonl + cards.index.json)

And that reads can come from either source based on configuration.
"""
import os
import sys
import tempfile
import shutil
import json

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_dual_write_create():
    """Test that creating a card writes to both legacy and state store."""
    print("\n" + "="*60)
    print("TEST: Dual-Write Create Card")
    print("="*60)

    test_dir = tempfile.mkdtemp(prefix="dual_write_test_")

    try:
        # Set environment to enable dual-write
        os.environ["STATE_DATA_DIR"] = test_dir
        os.environ["CARDS_FILE"] = os.path.join(test_dir, "cards.json")
        os.environ["DUAL_WRITE"] = "true"
        os.environ["USE_STATE_FOR_READS"] = "false"  # Read from legacy for this test

        # Reload modules to pick up new env vars
        import importlib
        import BrainstormingBoard.tool as tool_module
        import state.jsonl_store as store_module
        importlib.reload(store_module)
        importlib.reload(tool_module)

        from BrainstormingBoard.tool import CreateCardTool
        from state.jsonl_store import JSONLStore

        # Create a card using the tool
        tool = CreateCardTool()
        result = tool._run(name="Test Card", category="World Element", description="A test card for dual-write")

        print(f"  Tool result: {result}")

        # Check legacy cards.json exists and has the card
        cards_file = os.path.join(test_dir, "cards.json")
        assert os.path.exists(cards_file), f"Legacy cards.json not created at {cards_file}"

        with open(cards_file, 'r') as f:
            legacy_cards = json.load(f)

        assert "0" in legacy_cards, "Card not found in legacy cards.json"
        assert legacy_cards["0"]["name"] == "Test Card", "Card name mismatch in legacy"
        print(f"  ✓ PASS: Legacy cards.json contains card")

        # Check StateStore has the card
        events_file = os.path.join(test_dir, "events.jsonl")
        assert os.path.exists(events_file), f"Events file not created at {events_file}"

        store = JSONLStore(data_dir=test_dir)
        state_card = store.read_card("0")

        assert state_card is not None, "Card not found in StateStore"
        assert state_card["name"] == "Test Card", "Card name mismatch in StateStore"
        print(f"  ✓ PASS: StateStore contains card")

        # Verify data equivalence
        assert legacy_cards["0"]["name"] == state_card["name"], "Name mismatch between stores"
        assert legacy_cards["0"]["category"] == state_card["category"], "Category mismatch between stores"
        assert legacy_cards["0"]["description"] == state_card["description"], "Description mismatch between stores"
        print(f"  ✓ PASS: Both stores have equivalent data")

        # Clean up env
        del os.environ["STATE_DATA_DIR"]
        del os.environ["CARDS_FILE"]
        del os.environ["DUAL_WRITE"]
        del os.environ["USE_STATE_FOR_READS"]

        return True

    finally:
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir)


def test_dual_write_update():
    """Test that updating a card writes to both legacy and state store."""
    print("\n" + "="*60)
    print("TEST: Dual-Write Update Card")
    print("="*60)

    test_dir = tempfile.mkdtemp(prefix="dual_write_update_")

    try:
        # Set environment
        os.environ["STATE_DATA_DIR"] = test_dir
        os.environ["CARDS_FILE"] = os.path.join(test_dir, "cards.json")
        os.environ["DUAL_WRITE"] = "true"
        os.environ["USE_STATE_FOR_READS"] = "false"

        # Reload modules
        import importlib
        import BrainstormingBoard.tool as tool_module
        import state.jsonl_store as store_module
        importlib.reload(store_module)
        importlib.reload(tool_module)

        from BrainstormingBoard.tool import CreateCardTool, UpdateCardTool
        from state.jsonl_store import JSONLStore

        # Create initial card
        create_tool = CreateCardTool()
        create_tool._run(name="Original", category="Plot", description="Original description")

        # Update the card
        update_tool = UpdateCardTool()
        result = update_tool._run(id="0", name="Updated", category="Character", description="Updated description")

        print(f"  Tool result: {result}")

        # Check legacy file
        cards_file = os.path.join(test_dir, "cards.json")
        with open(cards_file, 'r') as f:
            legacy_cards = json.load(f)

        assert legacy_cards["0"]["name"] == "Updated", "Legacy card not updated"
        print(f"  ✓ PASS: Legacy cards.json updated")

        # Check StateStore
        store = JSONLStore(data_dir=test_dir)
        state_card = store.read_card("0")

        assert state_card["name"] == "Updated", "StateStore card not updated"
        print(f"  ✓ PASS: StateStore updated")

        # Verify equivalence
        assert legacy_cards["0"]["name"] == state_card["name"], "Updated name mismatch"
        assert legacy_cards["0"]["category"] == state_card["category"], "Updated category mismatch"
        print(f"  ✓ PASS: Both stores have equivalent updated data")

        # Clean up env
        del os.environ["STATE_DATA_DIR"]
        del os.environ["CARDS_FILE"]
        del os.environ["DUAL_WRITE"]
        del os.environ["USE_STATE_FOR_READS"]

        return True

    finally:
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir)


def test_read_from_state_store():
    """Test that reads can come from StateStore when enabled."""
    print("\n" + "="*60)
    print("TEST: Read from StateStore")
    print("="*60)

    test_dir = tempfile.mkdtemp(prefix="state_read_test_")

    try:
        # Set environment to enable state reads
        os.environ["STATE_DATA_DIR"] = test_dir
        os.environ["CARDS_FILE"] = os.path.join(test_dir, "cards.json")
        os.environ["DUAL_WRITE"] = "true"
        os.environ["USE_STATE_FOR_READS"] = "true"  # Enable state reads

        # Reload modules
        import importlib
        import BrainstormingBoard.tool as tool_module
        import state.jsonl_store as store_module
        importlib.reload(store_module)
        importlib.reload(tool_module)

        from BrainstormingBoard.tool import CreateCardTool, ReadCardTool, ListCardTool

        # Create a card (will write to both)
        create_tool = CreateCardTool()
        create_tool._run(name="State Read Test", category="Theme", description="Testing state reads")

        # Now delete the legacy file to prove reads come from state
        cards_file = os.path.join(test_dir, "cards.json")
        if os.path.exists(cards_file):
            os.remove(cards_file)
        print(f"  Deleted legacy cards.json to force state read")

        # Try to read the card - should come from StateStore
        read_tool = ReadCardTool()
        card = read_tool._run(card_id="0")

        assert card["name"] == "State Read Test", "Failed to read from StateStore"
        print(f"  ✓ PASS: Successfully read card from StateStore (not legacy)")

        # Try to list cards - should come from StateStore
        list_tool = ListCardTool()
        cards_list = list_tool._run()

        assert len(cards_list) == 1, f"Expected 1 card, got {len(cards_list)}"
        assert cards_list[0][1] == "State Read Test", "List didn't return correct card from StateStore"
        print(f"  ✓ PASS: Successfully listed cards from StateStore (not legacy)")

        # Clean up env
        del os.environ["STATE_DATA_DIR"]
        del os.environ["CARDS_FILE"]
        del os.environ["DUAL_WRITE"]
        del os.environ["USE_STATE_FOR_READS"]

        return True

    finally:
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir)


def main():
    """Run all dual-write tests."""
    print("\n" + "="*60)
    print("Robot Writers Room - Dual-Write Test Suite")
    print("="*60)

    passed = 0
    failed = 0

    tests = [
        test_dual_write_create,
        test_dual_write_update,
        test_read_from_state_store,
    ]

    for test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  ✗ FAIL: {test_func.__name__} raised exception: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "="*60)
    print("DUAL-WRITE TEST SUMMARY")
    print("="*60)
    print(f"Passed: {passed}/{passed+failed}")
    print(f"Failed: {failed}/{passed+failed}")
    print("="*60 + "\n")

    if failed == 0:
        print("✓ All dual-write tests passed!")
        print("  - Card creates write to both stores")
        print("  - Card updates write to both stores")
        print("  - Reads can come from StateStore when enabled")
        print("  - Data is equivalent across both stores")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
