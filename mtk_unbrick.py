#!/usr/bin/env python3
"""
MTK Unbrick - Standalone script
Flash Xiaomi MTK devices via BROM mode without installation.

Usage:
    python mtk_unbrick.py flash ./firmware/
    python mtk_unbrick.py info
    python mtk_unbrick.py backup ./backup
"""
import sys

from mtk_unbrick.cli import main

if __name__ == "__main__":
    sys.exit(main())
