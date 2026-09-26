#!/usr/bin/env bash
# MTK Unbrick - Linux/macOS launcher (thin wrapper around the Python CLI)
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

if ! command -v python3 >/dev/null 2>&1; then
    echo -e "${RED}[!] python3 not found. Install python3 first.${NC}"
    exit 1
fi

# mtkclient backend check (its exact location is resolved by the tool)
if [ -z "$MTKCLIENT" ] \
    && [ ! -f "$SCRIPT_DIR/mtkclient/mtk.py" ] \
    && [ ! -f "$SCRIPT_DIR/../mtkclient/mtk.py" ] \
    && [ ! -f "$HOME/mtkclient/mtk.py" ]; then
    echo -e "${YELLOW}[!] mtkclient not found. Clone it first:${NC}"
    echo -e "${YELLOW}    git clone https://github.com/bkerler/mtkclient ~/mtkclient${NC}"
    echo -e "${YELLOW}    pip install -r ~/mtkclient/requirements.txt${NC}"
    exit 1
fi

# USB permission hint (BROM device will not open without udev rule/root)
if command -v lsusb >/dev/null 2>&1 && lsusb | grep -q "0e8d"; then
    if [ "$(id -u)" != "0" ] && [ ! -f /etc/udev/rules.d/50-mtkclient.rules ]; then
        echo -e "${YELLOW}[!] Device detected but no udev rule installed.${NC}"
        echo -e "${YELLOW}    sudo cp 50-mtkclient.rules /etc/udev/rules.d/ && sudo udevadm control --reload-rules && sudo udevadm trigger${NC}"
        echo -e "${YELLOW}    (or simply run this script with sudo)${NC}"
    fi
fi

exec python3 mtk_unbrick.py "$@"
