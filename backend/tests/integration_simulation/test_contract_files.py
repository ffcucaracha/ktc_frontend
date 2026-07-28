import json
from pathlib import Path

import yaml

CONTRACT_DIR = Path(__file__).resolve().parents[3] / "contracts" / "simulation-api"


def test_contract_files_exist_and_are_parseable() -> None:
    openapi = yaml.safe_load((CONTRACT_DIR / "openapi.yaml").read_text(encoding="utf-8"))
    websocket_events = (CONTRACT_DIR / "websocket-events.md").read_text(encoding="utf-8")

    assert openapi["paths"]["/v1/sessions"]
    assert "state.snapshot" in websocket_events

    for example_path in (CONTRACT_DIR / "examples").glob("*.json"):
        json.loads(example_path.read_text(encoding="utf-8"))
