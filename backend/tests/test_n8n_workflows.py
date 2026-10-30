import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "check_n8n_workflows.py"
WORKFLOWS = REPO_ROOT / "infra" / "n8n" / "workflows"


def run(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(path)], capture_output=True, text=True, check=False
    )


def test_repository_workflows_pass() -> None:
    assert run(WORKFLOWS).returncode == 0


def test_workflows_call_only_existing_api_routes() -> None:
    from aicfo.main import create_app

    routes = set(create_app().openapi()["paths"])
    for f in WORKFLOWS.glob("*.json"):
        for n in json.loads(f.read_text())["nodes"]:
            url = n["parameters"].get("url", "")
            if "AICFO_API_URL" in url:
                path = url.split("}}", 1)[1].replace("{{ $json.id }}", "{client_ref}")
                assert path in routes, f"{f.name}: {n['name']} calls unknown route {path}"


def test_guard_catches_hardcoded_host_and_missing_token(tmp_path: Path) -> None:
    wf = json.loads((WORKFLOWS / "weekly-review-sweep.json").read_text())
    for n in wf["nodes"]:
        if n["name"] == "List clients":
            n["parameters"]["url"] = "https://api.example.test/v1/clients"
        if n["name"] == "Run review":
            n["parameters"]["headerParameters"] = {"parameters": []}
    (tmp_path / "bad.json").write_text(json.dumps(wf))
    out = run(tmp_path).stdout
    assert "List clients URL must come from $env" in out
    assert "Run review calls the API without the automation token" in out


def test_guard_catches_secrets_and_dangling_connections(tmp_path: Path) -> None:
    text = (WORKFLOWS / "review-events.json").read_text()
    wf = json.loads(text.replace('"Compose message"', '"Gone"', 1))  # rename the node only
    wf["notes"] = "key gsk_" + "x" * 26  # built at runtime so secret scanners stay quiet
    (tmp_path / "x.json").write_text(json.dumps(wf))
    out = run(tmp_path).stdout
    assert "unknown node" in out and "secret-looking" in out
