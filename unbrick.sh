#!/usr/bin/env bash
#
# MTK Unbrick - One-click unbrick tool for Xiaomi MTK devices
#
# Usage:
#   ./unbrick.sh                    # Interactive mode
#   ./unbrick.sh flash <rom_dir>    # Direct flash
#   ./unbrick.sh info               # Show device info
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="$SCRIPT_DIR/mtk_unbrick.py"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

print_banner() {
    echo -e "${CYAN}"
    cat << 'EOF'
  __  __ _ __  __        ____  _             _
 |  \/  (_)  \/  |  ___ | __ )(_) _ __   __| | ___ _ __
 | |\/| | | |\/| | / _ \|  _ \| || '_ \ / _` |/ _ \ '__|
 | |  | | | |  | ||  __/| |_) | || | | | (_| |  __/ |
 |_|  |_|_|_|  |_| \___||____/|_||_| |_|\__,_|\___|_|
                    v0.1.0 - BROM Unbrick Tool
EOF
    echo -e "${NC}"
}

check_deps() {
    echo -e "${YELLOW}[*] Checking dependencies...${NC}"

    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}[!] python3 not found. Install python3 first.${NC}"
        exit 1
    fi

    if ! python3 -c "import usb.core" 2>/dev/null; then
        echo -e "${YELLOW}[!] pyusb not installed. Installing...${NC}"
        pip3 install pyusb 2>/dev/null || pip install pyusb 2>/dev/null || {
            echo -e "${RED}[!] Failed to install pyusb. Run manually: pip3 install pyusb${NC}"
            exit 1
        }
    fi

    echo -e "${GREEN}[+] All dependencies OK${NC}"
}

pick_folder() {
    echo -e "${CYAN}"
    echo "=========================================="
    echo "  Select ROM Folder"
    echo "=========================================="
    echo -e "${NC}"
    echo -e "${YELLOW}Enter the path to extracted fastboot ROM folder:${NC}"
    echo -e "${GRAY}(Drag & drop folder here, then press Enter)${NC}"
    echo ""
    read -rp "ROM Folder: " rom_path

    # Remove surrounding quotes if present
    rom_path="${rom_path%\"}"
    rom_path="${rom_path#\"}"
    rom_path="${rom_path%\'}"
    rom_path="${rom_path#\'}"

    # Trim whitespace
    rom_path=$(echo "$rom_path" | xargs)

    if [ -z "$rom_path" ]; then
        echo -e "${RED}[!] No path provided${NC}"
        exit 1
    fi

    if [ ! -d "$rom_path" ]; then
        echo -e "${RED}[!] Folder not found: $rom_path${NC}"
        exit 1
    fi

    echo -e "${GREEN}[+] ROM folder: $rom_path${NC}"
    echo "$rom_path"
}

pick_scatter() {
    local rom_dir="$1"

    echo ""
    echo -e "${YELLOW}Scatter file detection:${NC}"

    # Auto-detect scatter file
    local scatter=$(find "$rom_dir" -maxdepth 3 -name "*_Android_scatter.txt" -o -name "*scatter*.txt" 2>/dev/null | head -1)

    if [ -n "$scatter" ]; then
        echo -e "${GREEN}[+] Auto-detected: $(basename "$scatter")${NC}"
        read -rp "Use this scatter? [Y/n] " use_auto
        if [ "$use_auto" = "n" ] || [ "$use_auto" = "N" ]; then
            scatter=""
        fi
    fi

    if [ -z "$scatter" ]; then
        echo -e "${YELLOW}Enter scatter file path (or press Enter for auto-detect):${NC}"
        read -rp "Scatter: " manual_scatter

        manual_scatter="${manual_scatter%\"}"
        manual_scatter="${manual_scatter#\"}"
        manual_scatter="${manual_scatter%\'}"
        manual_scatter="${manual_scatter#\'}"
        manual_scatter=$(echo "$manual_scatter" | xargs)

        if [ -n "$manual_scatter" ] && [ -f "$manual_scatter" ]; then
            scatter="$manual_scatter"
        fi
    fi

    echo "$scatter"
}

show_menu() {
    echo -e "${CYAN}"
    echo "=========================================="
    echo "  MTK Unbrick - Main Menu"
    echo "=========================================="
    echo -e "${NC}"
    echo "  1) Flash firmware"
    echo "  2) Flash (skip confirmation)"
    echo "  3) Flash (skip userdata)"
    echo "  4) Show device info"
    echo "  5) Exit"
    echo ""
    read -rp "Select option [1-5]: " choice
    echo "$choice"
}

interactive_mode() {
    print_banner
    check_deps

    local choice=$(show_menu)

    case $choice in
        1|2|3)
            local rom_path=$(pick_folder)
            local scatter=$(pick_scatter "$rom_path")

            local args="flash $rom_path"

            if [ -n "$scatter" ]; then
                args="$args -s $scatter"
            fi

            if [ "$choice" = "2" ]; then
                args="$args -y"
            fi

            if [ "$choice" = "3" ]; then
                args="$args --skip-userdata"
            fi

            echo ""
            echo -e "${GREEN}[*] Starting flash...${NC}"
            python3 "$PYTHON_SCRIPT" $args
            ;;
        4)
            python3 "$PYTHON_SCRIPT" info
            ;;
        5|*)
            echo -e "${YELLOW}Bye!${NC}"
            exit 0
            ;;
    esac
}

# Main
if [ $# -eq 0 ]; then
    interactive_mode
else
    check_deps
    python3 "$PYTHON_SCRIPT" "$@"
fi
