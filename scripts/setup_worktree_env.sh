#!/bin/bash

set -euo pipefail

log() {
  printf '%s\n' "$1"
}

fail() {
  printf '%s\n' "$1" >&2
  exit 1
}

sync_codex_assets() {
  local shared_codex
  local target_codex

  shared_codex="${PARENT_DIR}/.codex"
  target_codex="${TARGET_DIR}/.codex"

  if [ ! -d "${shared_codex}" ]; then
    log "Shared Codex assets not found at ${shared_codex}; skipping .codex sync"
    return
  fi

  rm -rf "${target_codex}"
  mkdir -p "${TARGET_DIR}"
  cp -R "${shared_codex}" "${target_codex}"
  log "Copied shared Codex assets into ${target_codex}"
}

choose_python() {
  if command -v python3.11 >/dev/null 2>&1; then
    printf '%s\n' "python3.11"
    return
  fi

  if command -v python3 >/dev/null 2>&1 && python3 -c 'import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 11) else 1)'; then
    printf '%s\n' "python3"
    return
  fi

  fail "Python 3.11 is required to create the worktree virtual environment."
}

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
MAIN_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
PARENT_DIR="$(cd -- "${MAIN_DIR}/.." && pwd)"
TARGET_NAME="${1:-${WORKTREE:-}}"

[ -n "${TARGET_NAME}" ] || fail "Usage: $(basename "$0") <worktree-name>"
[ -d "${MAIN_DIR}" ] || fail "Expected main checkout at ${MAIN_DIR}"
[ -f "${MAIN_DIR}/pyproject.toml" ] || fail "Missing dependency source file: ${MAIN_DIR}/pyproject.toml"
[ -f "${MAIN_DIR}/poetry.lock" ] || fail "Missing dependency source file: ${MAIN_DIR}/poetry.lock"

TARGET_DIR="${PARENT_DIR}/${TARGET_NAME}"
[ -d "${TARGET_DIR}" ] || fail "Target checkout does not exist: ${TARGET_DIR}"

PYTHON_BIN="$(choose_python)"
TARGET_VENV="${TARGET_DIR}/.venv"
TARGET_PIP="${TARGET_VENV}/bin/pip3"
TARGET_POETRY="${TARGET_VENV}/bin/poetry"

log "Initializing checkout: ${TARGET_DIR}"
log "Dependency source: ${MAIN_DIR}"

if [ ! -d "${TARGET_VENV}" ]; then
  log "Creating virtual environment: ${TARGET_VENV}"
  "${PYTHON_BIN}" -m venv "${TARGET_VENV}"
else
  log "Reusing virtual environment: ${TARGET_VENV}"
fi

[ -x "${TARGET_PIP}" ] || fail "Expected pip at ${TARGET_PIP}"

if [ ! -x "${TARGET_POETRY}" ]; then
  log "Installing poetry into ${TARGET_VENV}"
  "${TARGET_PIP}" install poetry
fi

log "Installing dependencies from ${MAIN_DIR}"
POETRY_VIRTUALENVS_CREATE=false VIRTUAL_ENV="${TARGET_VENV}" "${TARGET_POETRY}" install --directory "${MAIN_DIR}" --no-root

log "Installing editable package from ${TARGET_DIR}"
"${TARGET_PIP}" install --editable "${TARGET_DIR}" --no-deps

sync_codex_assets
