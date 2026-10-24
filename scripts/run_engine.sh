#!/usr/bin/env bash
# Compile (pure JDK 21, no Maven needed) and run the JRide REST engine.
# Usage: scripts/run_engine.sh [--port 8080] [--drivers 150]
set -euo pipefail
cd "$(dirname "$0")/../engine"
mkdir -p target/classes
javac -d target/classes $(find src/main -name '*.java')
exec java -cp target/classes com.navya.dispatchengine.sim.Main --server "$@"
