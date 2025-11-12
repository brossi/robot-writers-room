from typing import Optional, List, Any

from langchain.callbacks.manager import AsyncCallbackManagerForToolRun
from pydantic import BaseModel, Field
from langchain.tools import BaseTool
import json
import os

# Use configurable data directory (respects STATE_DATA_DIR environment variable)
DATA_DIR = os.environ.get("STATE_DATA_DIR", "data")
CARDS_FILE = os.environ.get("CARDS_FILE", os.path.join(DATA_DIR, "cards.json"))

# Phase 2: StateStore integration
# Feature flags for gradual rollout
USE_STATE_FOR_READS = os.environ.get("USE_STATE_FOR_READS", "false").lower() == "true"
DUAL_WRITE = os.environ.get("DUAL_WRITE", "true").lower() == "true"

# Import StateStore (optional - graceful fallback if not available)
try:
    from state.jsonl_store import get_store
    STATE_STORE_AVAILABLE = True
except ImportError:
    STATE_STORE_AVAILABLE = False
    get_store = None


def _state_write_card(card_id: str, props: dict) -> None:
    """Write card to StateStore (if enabled and available)."""
    if DUAL_WRITE and STATE_STORE_AVAILABLE:
        try:
            store = get_store()
            store.upsert_card(card_id, props)
        except Exception as e:
            # Log but don't fail - legacy file write is primary
            print(f"Warning: StateStore write failed: {e}")


def _state_read_card(card_id: str) -> Optional[dict]:
    """Read card from StateStore (if enabled and available)."""
    if USE_STATE_FOR_READS and STATE_STORE_AVAILABLE:
        try:
            store = get_store()
            card = store.read_card(card_id)
            if card:  # Found in state store
                return card
        except Exception as e:
            # Log and fall through to legacy read
            print(f"Warning: StateStore read failed, falling back to legacy: {e}")
    return None


def _state_list_cards() -> Optional[list]:
    """List cards from StateStore (if enabled and available)."""
    if USE_STATE_FOR_READS and STATE_STORE_AVAILABLE:
        try:
            store = get_store()
            return store.list_cards()
        except Exception as e:
            # Log and fall through to legacy read
            print(f"Warning: StateStore list failed, falling back to legacy: {e}")
    return None


class CardInput(BaseModel):
    name: str = Field(
        ...,
        description="The name of the idea.",
    )
    category: str = Field(
        ...,
        description="The category of the idea.",
    )
    description: str = Field(
        ...,
        description="A detailed description of the idea.",
    )


class BaseCardTool(BaseTool):
    @staticmethod
    def _load_cards():
        if os.path.exists(CARDS_FILE):
            with open(CARDS_FILE, 'r') as file:
                return json.load(file)
        else:
            return {}

    @staticmethod
    def _save_cards(cards):
        # Ensure data directory exists
        os.makedirs(os.path.dirname(CARDS_FILE) or '.', exist_ok=True)
        with open(CARDS_FILE, 'w') as file:
            json.dump(cards, file, indent=4)

    def _run(self, card_data: CardInput):
        raise NotImplementedError("BaseCardTool does not support sync")

    async def _arun(
            self, query: str, run_manager: Optional[AsyncCallbackManagerForToolRun] = None
    ) -> str:
        """Use the tool asynchronously."""
        raise NotImplementedError("BaseCardTool does not support async")


class CreateCardTool(BaseCardTool):
    name: str = "create_card"
    description: str = "Tool to create a new card. Please provide a name, category, and description."
    args_schema: type = CardInput

    def _run(self, name="", category="", description=""):
        # Legacy file write (primary)
        cards = super()._load_cards()
        next_id = len(cards)
        card_data = {"id": next_id, "name": name, "category": category, "description": description}
        cards[next_id] = card_data
        super()._save_cards(cards)

        # Dual-write to StateStore (if enabled)
        _state_write_card(str(next_id), card_data)

        return f'Card {next_id} created.'

    async def _arun(
            self, query: str, run_manager: Optional[AsyncCallbackManagerForToolRun] = None
    ) -> str:
        """Use the tool asynchronously."""
        raise NotImplementedError("CreateCardTool does not support async")


class ReadCardTool(BaseCardTool):
    name: str = "read_card"
    description: str = "Tool to read a card."
    args_schema: type = CardInput

    def _run(self, card_id: str):
        # Try StateStore first (if enabled)
        state_card = _state_read_card(card_id)
        if state_card is not None:
            return state_card

        # Fallback to legacy file read
        cards = super()._load_cards()
        if card_id not in cards:
            raise ValueError(f"No card with id {card_id} exists.")
        return cards[card_id]

    async def _arun(
            self, query: str, run_manager: Optional[AsyncCallbackManagerForToolRun] = None
    ) -> str:
        """Use the tool asynchronously."""
        raise NotImplementedError("ReadCardTool does not support async")


class UpdateCardTool(BaseCardTool):
    name: str = "update_card"
    description: str = "Tool to update a card, provided with an name, category, and description."
    args_schema: type = CardInput

    def _run(self, id="", name="", category="", description=""):
        # Legacy file write (primary)
        cards = super()._load_cards()
        if id not in cards.keys():
            raise ValueError(f"No card with id {id} exists.")
        card_data = {"id": id, "name": name, "category": category, "description": description}
        cards[id] = card_data
        super()._save_cards(cards)

        # Dual-write to StateStore (if enabled)
        _state_write_card(id, card_data)

        return f'Card {id} updated.'

    async def _arun(
            self, query: str, run_manager: Optional[AsyncCallbackManagerForToolRun] = None
    ) -> str:
        """Use the tool asynchronously."""
        raise NotImplementedError("UpdateCardTool does not support async")


class DeleteCardTool(BaseCardTool):
    name: str = "delete_card"
    description: str = "Tool to delete a card."
    args_schema: type = CardInput

    def _run(self, card_id: str):
        cards = super()._load_cards()
        if card_id not in cards.keys():
            raise ValueError(f"No card with id {card_id} exists.")
        del cards[card_id]
        super()._save_cards(cards)
        return f'Card {card_id} deleted.'

    async def _arun(
            self, query: str, run_manager: Optional[AsyncCallbackManagerForToolRun] = None
    ) -> str:
        """Use the tool asynchronously."""
        raise NotImplementedError("DeleteCardTool does not support async")


class ListCardTool(BaseTool):
    name: str = "list_card"
    description: str = "Tool to list ids and names of all cards."

    @staticmethod
    def _load_cards():
        if os.path.exists(CARDS_FILE):
            with open(CARDS_FILE, 'r') as file:
                return json.load(file)
        else:
            return {}

    def _run(self):
        # Try StateStore first (if enabled)
        state_cards = _state_list_cards()
        if state_cards is not None:
            return [(card.get('id'), card.get('name')) for card in state_cards]

        # Fallback to legacy file read
        cards = ListCardTool._load_cards()
        return [(card_id, card_data['name']) for card_id, card_data in cards.items()]

    async def _arun(
            self, query: str, run_manager: Optional[AsyncCallbackManagerForToolRun] = None
    ) -> str:
        """Use the tool asynchronously."""
        raise NotImplementedError("ListCardTool does not support async")