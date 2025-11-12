diff --git a/tools/card_tools.py b/tools/card_tools.py
index e1cafe1..b00b135 100644
--- a/tools/card_tools.py
+++ b/tools/card_tools.py
@@
+from typing import Dict, Any
+import os, json
+from state.jsonl_store import get_store
+
+# Feature flags (optional: read from env or a central config)
+USE_STATE_FOR_READS = os.environ.get("USE_STATE_FOR_READS", "false").lower() == "true"
+DUAL_WRITE = True  # keep legacy cards.json for one release
+
+# Legacy file location (unchanged)
 CARDS_JSON = os.path.join("data", "cards.json")
 
 def _load_legacy_cards():
     try:
         with open(CARDS_JSON, "r", encoding="utf-8") as f:
             return json.load(f)
     except Exception:
         return {}
 
 def _save_legacy_cards(d):
     os.makedirs(os.path.dirname(CARDS_JSON), exist_ok=True)
     tmp = CARDS_JSON + ".tmp"
     with open(tmp, "w", encoding="utf-8") as f:
         json.dump(d, f, indent=2, ensure_ascii=False)
     os.replace(tmp, CARDS_JSON)
 
-def create_or_update_card(card_id: str, props: dict) -> None:
-    data = _load_legacy_cards()
-    card = data.get(card_id, {})
-    card.update(props)
-    data[card_id] = card
-    _save_legacy_cards(data)
+def create_or_update_card(card_id: str, props: Dict[str, Any]) -> None:
+    # legacy write (kept for safety)
+    data = _load_legacy_cards()
+    card = data.get(card_id, {})
+    card.update(props)
+    data[card_id] = card
+    if DUAL_WRITE:
+        _save_legacy_cards(data)
+
+    # state write
+    store = get_store()
+    store.upsert_card(card_id, props)
 
-def read_card(card_id: str) -> dict:
-    data = _load_legacy_cards()
-    return data.get(card_id, {})
+def read_card(card_id: str) -> Dict[str, Any]:
+    if USE_STATE_FOR_READS:
+        store = get_store()
+        v = store.read_card(card_id)
+        if v:  # found in state
+            return v
+    # fallback to legacy
+    data = _load_legacy_cards()
+    return data.get(card_id, {})
 
-def list_cards() -> list:
-    data = _load_legacy_cards()
-    return [{"id": cid, **props} for cid, props in data.items()]
+def list_cards() -> list:
+    if USE_STATE_FOR_READS:
+        store = get_store()
+        cards = store.list_cards()
+        if cards:
+            return cards
+    data = _load_legacy_cards()
+    return [{"id": cid, **props} for cid, props in data.items()]
