"""Portable archive round trips use real projections and never resume imported runs."""

import copy
import json

import pytest
from fastapi.testclient import TestClient

from clocktower.api import create_app
from clocktower.archives import export_archive, import_archive
from clocktower.config import demo_config
from clocktower.runner import Runner
from clocktower.storage import Store, project_run


@pytest.fixture
def record(tmp_path):
    runner = Runner(demo_config(), Store(tmp_path / "source"))
    runner.engine.emit("message", {"player": "p1", "target": "p2", "text": "private clue"}, ["p1", "p2"])
    return json.loads(json.dumps(runner.record()))


def test_running_archive_preserves_private_snapshots_and_becomes_replay(record):
    original = copy.deepcopy(record)
    archive = export_archive(record)
    assert "process_id" not in archive["run"]
    imported = import_archive(archive)
    assert imported["id"] != record["id"]
    assert import_archive(archive)["id"] != imported["id"]
    assert imported["status"] == "interrupted" and imported["result"]["winner"] is None
    assert imported["events"][:-1] == record["events"]
    for key in ("personas", "models", "usage", "config"):
        assert imported[key] == record[key]
    assert "process_id" not in imported
    assert record == original
    assert not any(e["kind"] == "message" for e in project_run(imported, "public")["events"])
    assert any(e["kind"] == "message" for e in project_run(imported, "p2")["events"])
    assert not any(e["kind"] == "message" for e in project_run(imported, "p3")["events"])


def test_api_import_export_no_overwrite_no_requests_or_files(record, tmp_path, monkeypatch):
    async def forbidden(*args, **kwargs):
        raise AssertionError("Import must never start a runner")

    monkeypatch.setattr(Runner, "run", forbidden)
    app = create_app(tmp_path / "destination")
    original_id = record["id"]
    with TestClient(app) as client:
        archive = export_archive(record)
        # References in config are metadata, not a request to restore arbitrary files.
        archive["run"]["config"]["players"][0]["persona"] = "../../outside.md"
        first = client.post("/api/runs/import", json=archive)
        assert first.status_code == 200, first.text
        second = client.post("/api/runs/import", json=archive)
        assert second.status_code == 200
        ids = {first.json()["id"], second.json()["id"]}
        assert len(ids) == 2 and original_id not in ids
        assert all(client.get("/api/runs/" + key).json()["status"] == "interrupted" for key in ids)
        exported = client.get("/api/runs/" + first.json()["id"] + "/export").json()
        assert exported["run"]["events"][:-1] == record["events"]
        assert exported["run"]["personas"] == record["personas"]
        assert "process_id" not in exported["run"]
    assert not (tmp_path / "outside.md").exists()
    assert sorted(p.name for p in (tmp_path / "destination" / "runs").glob("*.json")) == sorted(
        key + ".json" for key in ids
    )


@pytest.mark.parametrize(
    "kind,data",
    [
        ("role", {"player": "p1", "role": {}, "alignment": "good"}),
        ("message", {"player": [], "text": "bad"}),
        ("message", {"player": "p1", "target": {}, "text": "bad"}),
        ("dawn", {"deaths": [{}]}),
        ("vote", {"votes": {"p1": "false"}, "nominee": "p2", "tally": 0, "threshold": 4}),
        ("grimoire", {"players": [{"id": [], "role": "imp", "alive": True}]}),
        ("grimoire", {"players": [{"id": "p1", "role": "imp", "alive": "yes"}]}),
        ("setup", {"players": [{"id": "p1"}]}),
        ("result", {"winner": [], "status": "completed", "reason": "bad"}),
        ("information", {"player": "p1", "ability": {}, "value": 1}),
    ],
)
def test_malformed_events_return_validation_error(record, kind, data):
    archive = export_archive(record)
    archive["run"]["events"].append(
        {
            "seq": len(record["events"]) + 1,
            "day": 0,
            "phase": "setup",
            "kind": kind,
            "data": data,
            "audience": None,
        }
    )
    with pytest.raises(ValueError):
        import_archive(archive)


def test_reject_projected_oversize_deep_and_invalid_audiences(record, monkeypatch):
    with pytest.raises(ValueError):
        import_archive(
            {"format": "clocktower-run", "archive_version": 1, "run": project_run(record, "public")}
        )
    archive = export_archive(record)
    archive["run"]["events"][0]["audience"] = ["unknown"]
    with pytest.raises(ValueError):
        import_archive(archive)
    monkeypatch.setattr("clocktower.archives.MAX_ARCHIVE_BYTES", 10)
    with pytest.raises(ValueError, match="50 MiB"):
        import_archive(export_archive(record))
    nested = {}
    for _ in range(40):
        nested = {"x": nested}
    with pytest.raises(ValueError, match="nested"):
        import_archive(nested)


def test_api_rejects_bad_json_and_enforces_body_limit(tmp_path, monkeypatch):
    with TestClient(create_app(tmp_path)) as client:
        assert (
            client.post(
                "/api/runs/import", content=b"not json", headers={"content-type": "application/json"}
            ).status_code
            == 422
        )
        assert client.post("/api/runs/import", json=[]).status_code == 422
        monkeypatch.setattr("clocktower.api.MAX_ARCHIVE_BYTES", 10)
        assert (
            client.post(
                "/api/runs/import", content=b"x" * 11, headers={"content-type": "application/json"}
            ).status_code
            == 413
        )
    assert not list((tmp_path / "runs").glob("*.json"))


@pytest.mark.parametrize("kind", ["gossip", "moonchild", "future_ability"])
def test_future_script_events_remain_portable(record, kind):
    archive = export_archive(record)
    archive["run"]["events"].append(
        {
            "seq": len(record["events"]) + 1,
            "day": 1,
            "phase": "day",
            "kind": kind,
            "data": {
                "player": "p1",
                "target": "p2",
                "text": "A statement",
                "value": {"new": [1, True, None]},
            },
            "audience": ["p1"],
        }
    )
    imported = import_archive(archive)
    assert imported["events"][-2]["kind"] == kind


def test_completed_archive_is_preserved_without_synthetic_result(record):
    record["status"] = "completed"
    record["result"] = {"status": "completed", "winner": "good", "reason": "Demon eliminated"}
    record["events"].append(
        {
            "seq": len(record["events"]) + 1,
            "day": 1,
            "phase": "day",
            "kind": "result",
            "data": record["result"],
            "audience": None,
        }
    )
    imported = import_archive(export_archive(record))
    assert imported["status"] == "completed"
    assert imported["result"] == record["result"]
    assert imported["events"] == record["events"]


def test_interruption_cannot_award_victory(record):
    record["status"] = "interrupted"
    record["result"] = {"status": "interrupted", "winner": "evil", "reason": "Limit"}
    with pytest.raises(ValueError):
        export_archive(record)


@pytest.mark.parametrize(
    "kind,data",
    [
        ("dawn", {"deaths": [], "resurrected": "p1"}),
        ("dawn", {"deaths": [], "resurrected": [{}]}),
        ("gossip", {"player": "p1", "text": []}),
        ("moonchild", {"player": "p1"}),
        ("moonchild", {"player": "p1", "target": "missing"}),
    ],
)
def test_malformed_bmr_events_rejected(record, kind, data):
    archive = export_archive(record)
    archive["run"]["events"].append(
        {
            "seq": len(record["events"]) + 1,
            "day": 1,
            "phase": "day",
            "kind": kind,
            "data": data,
            "audience": None,
        }
    )
    with pytest.raises(ValueError):
        import_archive(archive)


def test_cli_archive_roundtrip(record, tmp_path, monkeypatch, capsys):
    from clocktower.cli import main

    source = Store(tmp_path / "source-cli")
    source.write("runs", record["id"], record)
    archive_path = tmp_path / "portable.json"
    monkeypatch.setattr(
        "sys.argv", ["clocktower", "--data", str(source.root), "export-run", record["id"], str(archive_path)]
    )
    main()
    exported = json.loads(archive_path.read_text())
    assert exported["run"]["events"] == record["events"]
    destination = tmp_path / "destination-cli"
    monkeypatch.setattr(
        "sys.argv", ["clocktower", "--data", str(destination), "import-run", str(archive_path)]
    )
    main()
    imported_files = list((destination / "runs").glob("*.json"))
    assert len(imported_files) == 1
    imported = json.loads(imported_files[0].read_text())
    assert imported["id"] != record["id"] and imported["status"] == "interrupted"
    assert imported["events"][:-1] == record["events"]
    assert "process_id" not in imported
