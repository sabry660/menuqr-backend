"""Regenerate openapi.yaml from the live FastAPI schema.

Usage:
    python scripts/export_openapi.py            # write openapi.yaml (and docs/openapi.json)
    python scripts/export_openapi.py --check    # exit 1 if openapi.yaml is out of date (CI)
"""
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
YAML_PATH = ROOT / "openapi.yaml"
JSON_PATH = ROOT / "docs" / "openapi.json"


def render() -> tuple[str, str]:
    schema = app.openapi()
    return (
        yaml.safe_dump(schema, sort_keys=False, allow_unicode=True),
        json.dumps(schema, indent=2, sort_keys=False) + "\n",
    )


def main() -> int:
    yaml_text, json_text = render()
    if "--check" in sys.argv:
        current = YAML_PATH.read_text() if YAML_PATH.exists() else ""
        if current != yaml_text:
            print("openapi.yaml is out of date. Run: python scripts/export_openapi.py")
            return 1
        print("openapi.yaml is up to date.")
        return 0
    YAML_PATH.write_text(yaml_text)
    JSON_PATH.write_text(json_text)
    print(f"Wrote {YAML_PATH} and {JSON_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
