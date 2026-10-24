#!/usr/bin/env bash
# Serve Strands Decider 2B locally on :8099 (downloads the weights from Hugging Face on first run).
# Needs `pip install strands-decider`. Device is auto-detected (cuda > mps > cpu); override with DEVICE=cpu.
set -euo pipefail
exec strands-decider serve "${CHECKPOINT:-StrandsAgents/strands-decider-2B-hobson-v19}" \
  --port "${PORT:-8099}" ${DEVICE:+--device "$DEVICE"}
