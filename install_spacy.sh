#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_PYTHON="${SCRIPT_DIR}/../../env/bin/python"
PYTHON_BIN="${PYTHON_BIN:-${DEFAULT_PYTHON}}"
MODEL_URL="https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl#sha256=1932429db727d4bff3deed6b34cfc05df17794f4a52eeb26cf8928f7c1a0fb85"

if [[ ! -x "${PYTHON_BIN}" ]]; then
    echo "Bench Python not found: ${PYTHON_BIN}" >&2
    echo "Set PYTHON_BIN to the Python executable used by your bench." >&2
    exit 1
fi

"${PYTHON_BIN}" -m pip install "spacy>=3.8.0,<3.9.0" "${MODEL_URL}"
"${PYTHON_BIN}" -c \
    "import spacy; nlp = spacy.load('en_core_web_sm'); assert 'ner' in nlp.pipe_names; print(nlp.meta['name'], nlp.meta['version'])"
