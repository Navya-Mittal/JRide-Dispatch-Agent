#!/usr/bin/env bash
# Keyword stand-in for the Decider (no weights, no GPU). For wiring/tests only, NOT for results.
exec python "$(dirname "$0")/../mock/mock_decider.py" --port "${PORT:-8099}"
