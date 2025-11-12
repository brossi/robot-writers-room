# tools/state_tail.py
import argparse, json
from typing import Optional
from state.jsonl_store import get_store
from state.store import Query

def main():
    ap = argparse.ArgumentParser(description="Tail and filter state events.")
    ap.add_argument("-n", "--num", type=int, default=50, help="How many events to display")
    ap.add_argument("--s", dest="s", default=None, help="Subject filter (exact)")
    ap.add_argument("--p", dest="p", default=None, help="Predicate filter (exact)")
    ap.add_argument("--o", dest="o", default=None, help="Object filter (exact)")
    ap.add_argument("--tag", dest="tag", default=None, help="Filter by meta.tags")
    ap.add_argument("--since", dest="since", default=None, help="ISO or relative (-10m, -2h, -3d)")
    ap.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = ap.parse_args()

    store = get_store()

    if any([args.s, args.p, args.o, args.tag, args.since]):
        q: Query = {
            "s": args.s,
            "p": args.p,
            "o": args.o,
            "tag": args.tag,
            "since": args.since,
            "limit": args.num,
            "newest_first": True,
        }
        events = store.query(q)
    else:
        events = store.tail(args.num)

    if args.json:
        print(json.dumps([e.to_dict() for e in events], indent=2, ensure_ascii=False))
    else:
        for e in events:
            tags = ",".join(e.meta.get("tags", []))
            print(f"{e.ts}  {e.actor:12}  {e.op:7}  {e.triple[0]} :: {e.triple[1]} -> {e.triple[2]}  [{tags}]")

if __name__ == "__main__":
    main()
