import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "check_no_order_apis.py"


def run(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(path)], capture_output=True, text=True, check=False
    )


def test_repository_has_no_order_apis() -> None:
    assert run(REPO_ROOT / "backend" / "src").returncode == 0


def test_guard_catches_order_call(tmp_path: Path) -> None:
    (tmp_path / "bad.py").write_text('client.post("/v2/orders", json=payload)\n')
    result = run(tmp_path)
    assert result.returncode == 1
    assert "bad.py" in result.stdout
