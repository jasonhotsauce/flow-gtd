from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SETUP_SCRIPT = REPO_ROOT / "scripts" / "setup_worktree_env.sh"


def _write_fake_python_launcher(bin_dir: Path, log_path: Path) -> None:
    python_stub = f"""#!/bin/sh
set -eu

LOG_PATH="{log_path}"

if [ "$#" -eq 3 ] && [ "$1" = "-m" ] && [ "$2" = "venv" ]; then
  venv_dir="$3"
  mkdir -p "$venv_dir/bin"
  cat >"$venv_dir/bin/pip3" <<'EOF'
#!/bin/sh
set -eu
LOG_PATH="{log_path}"
printf 'PIP %s\\n' "$*" >> "$LOG_PATH"
if [ "$#" -eq 2 ] && [ "$1" = "install" ] && [ "$2" = "poetry" ]; then
  cat >"$(dirname "$0")/poetry" <<'EOPOETRY'
#!/bin/sh
set -eu
LOG_PATH="{log_path}"
printf 'POETRY %s\\n' "$*" >> "$LOG_PATH"
EOPOETRY
  chmod +x "$(dirname "$0")/poetry"
fi
EOF
  chmod +x "$venv_dir/bin/pip3"
  cat >"$venv_dir/bin/python" <<'EOFPY'
#!/bin/sh
exit 0
EOFPY
  chmod +x "$venv_dir/bin/python"
  printf 'VENV %s\\n' "$venv_dir" >> "$LOG_PATH"
  exit 0
fi

printf 'PYTHON %s\\n' "$*" >> "$LOG_PATH"
exit 0
"""
    launcher = bin_dir / "python3.11"
    launcher.write_text(python_stub)
    launcher.chmod(launcher.stat().st_mode | stat.S_IXUSR)


def _install_repo_script(parent_dir: Path) -> Path:
    assert SETUP_SCRIPT.exists(), f"expected setup script at {SETUP_SCRIPT}"
    target_script = parent_dir / "main" / "scripts" / "setup_worktree_env.sh"
    target_script.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SETUP_SCRIPT, target_script)
    target_script.chmod(target_script.stat().st_mode | stat.S_IXUSR)
    return target_script


def _make_checkout(parent_dir: Path, name: str) -> Path:
    checkout_dir = parent_dir / name
    checkout_dir.mkdir(parents=True, exist_ok=True)
    return checkout_dir


def _make_shared_codex(parent_dir: Path) -> Path:
    codex_dir = parent_dir / ".codex"
    (codex_dir / "docs").mkdir(parents=True, exist_ok=True)
    (codex_dir / "hooks").mkdir(parents=True, exist_ok=True)
    (codex_dir / "docs" / "agent-workflow.md").write_text("# Agent Workflow\n")
    (codex_dir / "hooks.json").write_text('{"hooks":{}}\n')
    return codex_dir


def _run_setup(script_path: Path, parent_dir: Path, worktree: str, log_path: Path) -> subprocess.CompletedProcess[str]:
    fake_bin = parent_dir / "fake-bin"
    fake_bin.mkdir()
    _write_fake_python_launcher(fake_bin, log_path)
    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    return subprocess.run(
        [str(script_path), worktree],
        cwd=parent_dir,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_setup_worktree_uses_main_dependencies_for_sibling_target(tmp_path: Path) -> None:
    parent_dir = tmp_path / "flow-gtd"
    main_dir = _make_checkout(parent_dir, "main")
    worktree_dir = _make_checkout(parent_dir, "feature-x")
    _make_shared_codex(parent_dir)
    (main_dir / "pyproject.toml").write_text("[tool.poetry]\nname = 'flow-gtd'\nversion = '0.0.0'\n")
    (main_dir / "poetry.lock").write_text("lock-version = '2.0'\n")
    script_path = _install_repo_script(parent_dir)
    log_path = tmp_path / "setup.log"

    result = _run_setup(script_path, parent_dir, "feature-x", log_path)

    assert result.returncode == 0, result.stderr
    assert (worktree_dir / ".venv").is_dir()
    log_lines = log_path.read_text().splitlines()
    assert f"VENV {worktree_dir / '.venv'}" in log_lines
    assert "PIP install poetry" in log_lines
    assert f"POETRY install --directory {main_dir} --no-root" in log_lines
    assert f"PIP install --editable {worktree_dir} --no-deps" in log_lines
    assert (worktree_dir / ".codex" / "docs" / "agent-workflow.md").read_text() == "# Agent Workflow\n"
    assert (worktree_dir / ".codex" / "hooks.json").read_text() == '{"hooks":{}}\n'


def test_setup_worktree_supports_main_as_target(tmp_path: Path) -> None:
    parent_dir = tmp_path / "flow-gtd"
    main_dir = _make_checkout(parent_dir, "main")
    (main_dir / "pyproject.toml").write_text("[tool.poetry]\nname = 'flow-gtd'\nversion = '0.0.0'\n")
    (main_dir / "poetry.lock").write_text("lock-version = '2.0'\n")
    script_path = _install_repo_script(parent_dir)
    log_path = tmp_path / "main.log"

    result = _run_setup(script_path, parent_dir, "main", log_path)

    assert result.returncode == 0, result.stderr
    assert (main_dir / ".venv").is_dir()
    log_lines = log_path.read_text().splitlines()
    assert f"VENV {main_dir / '.venv'}" in log_lines
    assert f"POETRY install --directory {main_dir} --no-root" in log_lines
    assert f"PIP install --editable {main_dir} --no-deps" in log_lines


def test_setup_worktree_fails_for_missing_target(tmp_path: Path) -> None:
    parent_dir = tmp_path / "flow-gtd"
    main_dir = _make_checkout(parent_dir, "main")
    (main_dir / "pyproject.toml").write_text("[tool.poetry]\nname = 'flow-gtd'\nversion = '0.0.0'\n")
    (main_dir / "poetry.lock").write_text("lock-version = '2.0'\n")
    script_path = _install_repo_script(parent_dir)
    log_path = tmp_path / "missing.log"

    result = _run_setup(script_path, parent_dir, "missing-worktree", log_path)

    assert result.returncode != 0
    assert "missing-worktree" in result.stderr
