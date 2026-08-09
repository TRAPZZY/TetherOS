#!/bin/bash
# Cached rebuild through the same reproducible entry point used by CI.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$SCRIPT_DIR/build-distro.sh"
