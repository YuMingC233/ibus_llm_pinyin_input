#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${INSTALL_DIR}/.venv/bin/python"

if [[ ! -x "${PYTHON}" ]]; then
  PYTHON="$(command -v python3)"
fi

exec "${PYTHON}" "${INSTALL_DIR}/engine.py"
