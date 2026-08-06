#!/usr/bin/env bash
# Tether OS Installer -- Unix (Linux / macOS)
# Usage: curl -fsSL https://raw.githubusercontent.com/trapzzy/tether-os/main/scripts/install.sh | bash

set -euo pipefail

TETHER_ROOT="${TETHER_ROOT:-$HOME/.tether}"
BIN_DIR="${TETHER_ROOT}/bin"
REQUIRE_DIRS=("${TETHER_ROOT}" "${BIN_DIR}" "${TETHER_ROOT}/etc" "${TETHER_ROOT}/log")

echo "[TETHER] Installing Tether OS by Trapzzy..."

# 1. Create directory structure
for dir in "${REQUIRE_DIRS[@]}"; do
    mkdir -p "$dir"
done

# 2. Install Tor if missing
if ! command -v tor &>/dev/null; then
    echo "[TETHER] Installing Tor..."
    if [[ "$(uname)" == "Darwin" ]]; then
        brew install tor
    elif command -v apt &>/dev/null; then
        sudo apt update && sudo apt install -y tor
    elif command -v dnf &>/dev/null; then
        sudo dnf install -y tor
    else
        echo "[WARN] Please install Tor manually: https://torproject.org"
    fi
fi

# 3. Configure Tor for Tether
if [[ -f /etc/tor/torrc ]]; then
    if ! grep -q "ControlPort 9051" /etc/tor/torrc; then
        echo "ControlPort 9051" | sudo tee -a /etc/tor/torrc
        echo "SOCKSPort 127.0.0.1:9050" | sudo tee -a /etc/tor/torrc
    fi
fi

# 4. Install Tether OS via pip
pip3 install --user -e "$(dirname "$(dirname "$0")")" 2>/dev/null || \
    pip3 install --user tether-os

echo "[TETHER] Install complete!"
echo "[TETHER] Console scripts were installed to your Python user bin directory."
echo "[TETHER] Run 'tether check' to verify, then 'tetherd' to start."
