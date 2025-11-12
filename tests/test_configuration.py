#!/usr/bin/env python3
"""
Test configuration loading from environment variables.

This validates that critical hardcoded values have been replaced
with environment variable reads.
"""
import os
import sys
import tempfile
import shutil

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_brainstorming_board_config():
    """Test that BrainstormingBoard/tool.py respects STATE_DATA_DIR."""
    print("\n" + "="*60)
    print("TEST: BrainstormingBoard Configuration")
    print("="*60)

    # Create temp directory
    test_dir = tempfile.mkdtemp(prefix="config_test_")

    try:
        # Set environment variable
        os.environ["STATE_DATA_DIR"] = test_dir
        os.environ["CARDS_FILE"] = os.path.join(test_dir, "test_cards.json")

        # Import after setting env vars (reimport to pick up new env)
        import importlib
        import BrainstormingBoard.tool as tool_module
        importlib.reload(tool_module)

        # Test that CARDS_FILE uses the configured directory
        from BrainstormingBoard.tool import CARDS_FILE, DATA_DIR

        assert DATA_DIR == test_dir, f"Expected DATA_DIR={test_dir}, got {DATA_DIR}"
        expected_cards_file = os.path.join(test_dir, "test_cards.json")
        assert CARDS_FILE == expected_cards_file, f"Expected CARDS_FILE={expected_cards_file}, got {CARDS_FILE}"

        print(f"  ✓ PASS: DATA_DIR respects STATE_DATA_DIR ({test_dir})")
        print(f"  ✓ PASS: CARDS_FILE is correctly set ({expected_cards_file})")

        # Test that saving cards creates files in correct directory
        from BrainstormingBoard.tool import BaseCardTool
        test_cards = {"0": {"id": 0, "name": "Test Card", "category": "Test", "description": "Test"}}
        BaseCardTool._save_cards(test_cards)

        assert os.path.exists(expected_cards_file), f"Cards file not created at {expected_cards_file}"
        print(f"  ✓ PASS: Cards saved to correct directory")

        # Clean up env
        del os.environ["STATE_DATA_DIR"]
        del os.environ["CARDS_FILE"]

        return True

    finally:
        # Clean up
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir)


def test_run_configuration():
    """Test that run.py reads environment variables correctly."""
    print("\n" + "="*60)
    print("TEST: run.py Configuration")
    print("="*60)

    # Set environment variables
    os.environ["LLM_MODEL"] = "gpt-3.5-turbo"
    os.environ["LLM_STREAMING"] = "false"
    os.environ["LLM_TEMPERATURE"] = "0.5"
    os.environ["BRAINSTORM_ITERATIONS"] = "5"
    os.environ["NUM_CHAPTERS"] = "50"
    os.environ["PAGES_PER_CHAPTER"] = "15"

    try:
        # Import after setting env vars
        import importlib
        import run as run_module
        importlib.reload(run_module)

        # Test LLM configuration
        assert run_module.LLM_MODEL == "gpt-3.5-turbo", f"Expected gpt-3.5-turbo, got {run_module.LLM_MODEL}"
        assert run_module.LLM_STREAMING == False, f"Expected False, got {run_module.LLM_STREAMING}"
        assert run_module.LLM_TEMPERATURE == 0.5, f"Expected 0.5, got {run_module.LLM_TEMPERATURE}"

        print(f"  ✓ PASS: LLM_MODEL = {run_module.LLM_MODEL}")
        print(f"  ✓ PASS: LLM_STREAMING = {run_module.LLM_STREAMING}")
        print(f"  ✓ PASS: LLM_TEMPERATURE = {run_module.LLM_TEMPERATURE}")

        # Test story generation parameters
        assert run_module.ITERATIONS_FOR_BRAINSTORMING == 5, f"Expected 5, got {run_module.ITERATIONS_FOR_BRAINSTORMING}"
        assert run_module.NUM_CHAPTERS == 50, f"Expected 50, got {run_module.NUM_CHAPTERS}"
        assert run_module.PAGES_PER_CHAPTER == 15, f"Expected 15, got {run_module.PAGES_PER_CHAPTER}"

        print(f"  ✓ PASS: BRAINSTORM_ITERATIONS = {run_module.ITERATIONS_FOR_BRAINSTORMING}")
        print(f"  ✓ PASS: NUM_CHAPTERS = {run_module.NUM_CHAPTERS}")
        print(f"  ✓ PASS: PAGES_PER_CHAPTER = {run_module.PAGES_PER_CHAPTER}")

        # Test create_llm function
        llm = run_module.create_llm()
        assert llm.model_name == "gpt-3.5-turbo", f"Expected gpt-3.5-turbo, got {llm.model_name}"
        assert llm.temperature == 0.5, f"Expected 0.5, got {llm.temperature}"

        print(f"  ✓ PASS: create_llm() creates LLM with correct model and temperature")

        # Clean up env
        del os.environ["LLM_MODEL"]
        del os.environ["LLM_STREAMING"]
        del os.environ["LLM_TEMPERATURE"]
        del os.environ["BRAINSTORM_ITERATIONS"]
        del os.environ["NUM_CHAPTERS"]
        del os.environ["PAGES_PER_CHAPTER"]

        return True

    except ImportError as e:
        print(f"  ✗ FAIL: Could not import run.py: {e}")
        return False


def test_defaults():
    """Test that defaults are used when env vars are not set."""
    print("\n" + "="*60)
    print("TEST: Default Configuration Values")
    print("="*60)

    # Make sure env vars are not set
    for var in ["LLM_MODEL", "LLM_STREAMING", "LLM_TEMPERATURE",
                "BRAINSTORM_ITERATIONS", "NUM_CHAPTERS", "PAGES_PER_CHAPTER",
                "STATE_DATA_DIR"]:
        os.environ.pop(var, None)

    try:
        # Reimport with no env vars
        import importlib
        import run as run_module
        importlib.reload(run_module)

        # Test defaults
        assert run_module.LLM_MODEL == "gpt-4", f"Expected gpt-4, got {run_module.LLM_MODEL}"
        assert run_module.LLM_STREAMING == True, f"Expected True, got {run_module.LLM_STREAMING}"
        assert run_module.LLM_TEMPERATURE == 0.7, f"Expected 0.7, got {run_module.LLM_TEMPERATURE}"
        assert run_module.ITERATIONS_FOR_BRAINSTORMING == 2, f"Expected 2, got {run_module.ITERATIONS_FOR_BRAINSTORMING}"
        assert run_module.NUM_CHAPTERS == 30, f"Expected 30, got {run_module.NUM_CHAPTERS}"
        assert run_module.PAGES_PER_CHAPTER == 10, f"Expected 10, got {run_module.PAGES_PER_CHAPTER}"

        print(f"  ✓ PASS: All defaults are correct")
        print(f"    LLM_MODEL = gpt-4")
        print(f"    LLM_STREAMING = True")
        print(f"    LLM_TEMPERATURE = 0.7")
        print(f"    BRAINSTORM_ITERATIONS = 2")
        print(f"    NUM_CHAPTERS = 30")
        print(f"    PAGES_PER_CHAPTER = 10")

        return True

    except ImportError as e:
        print(f"  ✗ FAIL: Could not import run.py: {e}")
        return False


def main():
    """Run all configuration tests."""
    print("\n" + "="*60)
    print("Robot Writers Room - Configuration Test Suite")
    print("="*60)

    passed = 0
    failed = 0

    tests = [
        test_brainstorming_board_config,
        test_run_configuration,
        test_defaults,
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
    print("CONFIGURATION TEST SUMMARY")
    print("="*60)
    print(f"Passed: {passed}/{passed+failed}")
    print(f"Failed: {failed}/{passed+failed}")
    print("="*60 + "\n")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
