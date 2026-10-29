#!/bin/zsh
set -eu
cd -- "${0:A:h}"
if [[ ! -x .venv/bin/python ]]; then
  echo 'Create the virtual environment and install requirements.lock as described in README.md.'
  exit 1
fi
exec .venv/bin/python run.py
