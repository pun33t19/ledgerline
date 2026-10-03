"""Write the Lab API's OpenAPI schema to build/openapi.json (input for the UI's generated types)."""

from __future__ import annotations

import json
from pathlib import Path

from ledgerline.api.app import create_app
from ledgerline.api.security import LocalGuard

OUT = Path(__file__).resolve().parents[1] / "build" / "openapi.json"

if __name__ == "__main__":
    app = create_app(LocalGuard(allowed_hosts=set(), token="schema-export"))  # noqa: S106 - placeholder, never served
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(Path.cwd()) if OUT.is_relative_to(Path.cwd()) else OUT}")
