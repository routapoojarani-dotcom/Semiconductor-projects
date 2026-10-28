#!/usr/bin/env bash
# Removes simulation build artifacts, cocotb results, and generated
# waveform files so the repository can be rebuilt from a clean state.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

rm -rf sim_build
rm -f results.xml
rm -f sim/waves/*.vcd
rm -rf .pytest_cache
find . -type d -name "__pycache__" -not -path "./.venv/*" -exec rm -rf {} + 2>/dev/null || true

echo "Cleaned simulation build artifacts and generated waveforms."
