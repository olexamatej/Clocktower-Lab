from fastapi.testclient import TestClient

from clocktower.api import create_app
from clocktower.config import demo_config


def test_persona_config_roundtrip_and_security(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        config = demo_config().model_dump()
        response = client.post("/api/configs", json={"config": config})
        assert response.status_code == 200
        saved = response.json()
        refs = [p["persona"] for p in saved["config"]["players"]]
        assert len(set(refs)) == 7 and all(not r.startswith("builtin:") for r in refs)
        text = client.get("/api/persona", params={"ref": refs[0]}).json()["text"]
        changed = text.replace("# Analyst", "# Custom analyst")
        assert client.post("/api/personas", json={"text": changed, "ref": refs[0]}).status_code == 200
        assert client.get("/api/persona", params={"ref": "builtin:analyst"}).json()["text"] == text
        assert client.get("/api/persona", params={"ref": "../../outside.md"}).status_code == 422
        assert (
            client.post(
                "/api/configs", json={"config": config}, headers={"origin": "https://evil.example"}
            ).status_code
            == 403
        )
        config["defaults"]["api_key"] = "DO-NOT-REFLECT-THIS"
        response = client.post("/api/validate", json=config)
        assert response.status_code == 422 and "DO-NOT-REFLECT-THIS" not in response.text


def test_restart_marks_run_interrupted(tmp_path):
    app = create_app(tmp_path)
    app.state.store.write("runs", "crashed", {"status": "running", "events": [], "config": {"name": "Crash"}})
    with TestClient(app) as client:
        run = client.get("/api/runs").json()[0]
        assert run["status"] == "interrupted" and run["result"]["winner"] is None


def test_web_configuration_runs_with_normal_cli_and_reopens(tmp_path):
    import json
    import subprocess
    import sys

    app = create_app(tmp_path)
    with TestClient(app) as client:
        saved = client.post("/api/configs", json={"config": demo_config(5).model_dump()}).json()
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "clocktower.cli",
            "--data",
            str(tmp_path),
            "run",
            str(tmp_path / "configs" / (saved["id"] + ".json")),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert '"status": "completed"' in result.stdout
    record = json.loads(next((tmp_path / "runs").glob("*.json")).read_text())
    with TestClient(create_app(tmp_path)) as client:
        listing = client.get("/api/runs").json()
        assert len(listing) == 1 and listing[0]["status"] == "completed"
        public = client.get("/api/runs/" + record["id"]).json()
        assert public["events"][-1]["kind"] == "result"
        individual = client.get("/api/runs/" + record["id"], params={"view": "p1"}).json()
        assert any(e["kind"] == "role" for e in individual["events"])
        assert all(e["data"]["player"] == "p1" for e in individual["events"] if e["kind"] == "role")


def test_reserved_view_names_cannot_be_player_ids():
    import pytest

    from clocktower.config import GameConfig

    for name in ("public", "omniscient"):
        config = demo_config().model_dump()
        config["players"][0]["id"] = name
        with pytest.raises(ValueError):
            GameConfig.model_validate(config)
