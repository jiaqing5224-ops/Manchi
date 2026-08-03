"""Write pipeline data to a JSON file in artifacts_dir (folder component).

Replaces the old system action `_action_export_json`. Returns the input data
unchanged so the chain can continue.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


def run(params: dict, context: dict) -> Any:
    indent = int(params.get("indent", 2))
    filename = params.get("filename") or f"导出_{datetime.now():%Y%m%d_%H%M%S}.json"
    out = Path(context["artifacts_dir"]) / filename
    with open(out, "w", encoding="utf-8") as f:
        json.dump(context.get("input_data"), f, ensure_ascii=False, indent=indent, default=str)
    return context.get("input_data")


if __name__ == "__main__":
    import tempfile

    sample = [{"a": 1}, {"b": 2}]
    ctx = {"input_data": sample, "artifacts_dir": tempfile.mkdtemp()}
    out = run({"filename": "demo.json"}, ctx)
    print("returned items:", len(out))
    print("written to:", Path(ctx["artifacts_dir"]) / "demo.json")
