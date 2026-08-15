#!/usr/bin/env python3
"""Validate the generated JSON against the schemas, plus cross-file checks.

    python3 -m venv .venv && .venv/bin/pip install jsonschema
    .venv/bin/python tools/validate_content.py

Run this in CI. It catches three classes of breakage the build itself cannot:
schema drift, a location reference that points at nothing, and a translation
that has fallen out of step with the Arabic source of record.
"""

import json
import sys
from pathlib import Path

try:
    from jsonschema import Draft202012Validator
except ImportError:
    sys.exit("jsonschema is not installed — see the docstring")

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"
SCHEMA = ROOT / "schema"

PAIRS = [("locations.json", "locations.schema.json"), ("routes.json", "routes.schema.json")]
PAIRS += [(f"prophets.{lang}.json", "prophets.schema.json") for lang in ("ar", "en", "de")]
PAIRS += [(f"muhammad.{lang}.json", "muhammad.schema.json") for lang in ("ar", "en", "de")]


def main() -> int:
    failures = 0
    docs = {}

    for doc_name, schema_name in PAIRS:
        path = CONTENT / doc_name
        if not path.exists():
            print(f"SKIP {doc_name} (not generated yet)")
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        docs[doc_name] = doc
        schema = json.loads((SCHEMA / schema_name).read_text(encoding="utf-8"))
        errors = sorted(Draft202012Validator(schema).iter_errors(doc), key=lambda e: list(e.path))
        if errors:
            failures += len(errors)
            print(f"FAIL {doc_name} — {len(errors)} schema error(s)")
            for err in errors[:10]:
                print(f"     {'.'.join(str(p) for p in err.path)}: {err.message}")
        else:
            print(f"OK   {doc_name}")

    # Every referenced location must exist.
    known = {loc["id"] for loc in docs.get("locations.json", {}).get("locations", [])}
    for name, route in docs.get("routes.json", {}).get("routes", {}).items():
        for wp in route["waypoints"]:
            if wp not in known:
                failures += 1
                print(f"FAIL routes.json: {name} references unknown waypoint {wp!r}")
    for name, doc in docs.items():
        for item in doc.get("prophets", []) + doc.get("events", []):
            for loc in item["locations"]:
                if loc not in known:
                    failures += 1
                    print(f"FAIL {name}: {item.get('id')} references unknown location {loc!r}")

    # Translations must mirror the Arabic exactly in structure.
    for kind, key, id_key in (("prophets", "prophets", "id"), ("muhammad", "events", "id")):
        base = docs.get(f"{kind}.ar.json")
        if not base:
            continue
        base_ids = [item[id_key] for item in base[key]]
        for lang in ("en", "de"):
            other = docs.get(f"{kind}.{lang}.json")
            if not other:
                continue
            other_ids = [item[id_key] for item in other[key]]
            if other_ids != base_ids:
                failures += 1
                missing = set(base_ids) - set(other_ids)
                extra = set(other_ids) - set(base_ids)
                print(f"FAIL {kind}.{lang}.json is out of step with the Arabic: "
                      f"missing={sorted(missing)} extra={sorted(extra)}")

    print("\nall checks passed" if not failures else f"\n{failures} problem(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
