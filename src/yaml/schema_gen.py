"""
Generates schemas/<Kind>.json files from msgspec type definitions.

Prototype: only the Rules kind is migrated to this approach so far. The
generated schema is the same source of truth used to decode/validate Rule
data at runtime (`src.yaml.models.resolve_rule`), so the two can no
longer drift apart the way a hand-authored schema.json can from its
NamedTuple counterpart.

Run with: `uv run python -m src.yaml.schema_gen`
"""

import json
from pathlib import Path

import msgspec

from src.constants import SCHEMA_DIR
from src.models import CONFIG_KIND_TO_PARDIR, CONFIG_KIND_TO_STRUCT


def main() -> None:
    for kind, struct in CONFIG_KIND_TO_STRUCT.items():
        pardir = Path(SCHEMA_DIR) / CONFIG_KIND_TO_PARDIR[kind]
        pardir.mkdir(exist_ok=True)
        schema = msgspec.json.schema(struct)
        out_path = pardir / f"{kind}.json"
        out_path.write_text(json.dumps(schema, indent=2) + "\n")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
