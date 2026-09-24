"""Export the FastAPI OpenAPI document and a matching Postman collection."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.api.main import app

DOCS = ROOT / "docs"


def export_specs() -> None:
    """Write the API specifications used by analysts and API clients."""
    DOCS.mkdir(exist_ok=True)
    openapi = app.openapi()
    (DOCS / "openapi.json").write_text(
        json.dumps(openapi, indent=2) + "\n", encoding="utf-8"
    )
    requests = []
    for path, methods in openapi["paths"].items():
        for method in methods:
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            requests.append(
                {
                    "name": f"{method.upper()} {path}",
                    "request": {
                        "method": method.upper(),
                        "header": [],
                        "url": {
                            "raw": f"{{{{base_url}}}}{path}",
                            "host": ["{{base_url}}"],
                            "path": path.strip("/").split("/"),
                        },
                    },
                }
            )
    collection = {
        "info": {
            "name": "Nifty 100 Financial Intelligence API",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "variable": [{"key": "base_url", "value": "http://localhost:8000/api/v1"}],
        "item": requests,
    }
    (DOCS / "postman_collection.json").write_text(
        json.dumps(collection, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    export_specs()
