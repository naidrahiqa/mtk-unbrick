#!/usr/bin/env python3
"""
MTK Unbrick - Standalone script
Flash Xiaomi MTK devices via BROM mode without installation.

Usage:
    python mtk_unbrick.py flash ./firmware/
    python mtk_unbrick.py info
"""
import os
import sys
import struct
import time
import re
import logging
import argparse
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Dict

try:
    import usb.core
    import usb.util
    HAS_USB = True
except ImportError:
    HAS_USB = False
    print("WARNING: pyusb not installed. Run: pip install pyusb")

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

BANNER = """
  __  __ _ __  __        ____  _             _
 |  \\/  (_)  \\/  |  ___ | __ )(_) _ __   __| | ___ _ __
 | |\\/| | | |\\/| | / _ \\|  _ \\| || '_ \\ / _` |/ _ \\ '__|
 | |  | | | |  | ||  __/| |_) | || | | | (_| |  __/ |
 |_|  |_|_|_|  |_| \\___||____/|_||_| |_|\\__,_|\\___|_|
                    v0.1.0 - BROM Unbrick Tool
"""

MTK_VID = 0x0E8D
BROM_PIDS = [0x0003, 0x0023, 0x0033, 0x0043, 0x0053, 0x0135, 0x0136]
PRELOADER_PIDS = [0x0001, 0x0021, 0x0031, 0x0041, 0x0051, 0x0133, 0x0134]
SKIP_PARTITIONS = {"preloader", "pgpt", "sgpt", "proinfo", "nvram", "nvdata"}


@dataclass
class PartitionEntry:
    name: str
    start_addr: int
    size: int
    file_name: Optional[str] = None


def parse_scatter(scatter_path):
    partitions = {}
    with open(scatter_path, 'r') as f:
        content = f.read()

    blocks = re.split(r'(\w+\s*\{)', content)
    i = 0
    while i < len(blocks):
        match = re.match(r'(\w+)\s*\{', blocks[i])
        if match and i + 1 < len(blocks):
            name = match.group(1)
            body = re.split(r'\n\s*\w+\s*\{', blocks[i + 1])[0]
            start_m = re.search(r'linear_start_addr\s*:\s*(\S+)', body)
            size_m = re.search(r'partition_size\s*:\s*(\S+)', body)
            file_m = re.search(r'file_name\s*:\s*(\S+)', body)
            if start_m and size_m:
                partitions[name] = PartitionEntry(
                    name=name,
                    start_addr=int(start_m.group(1), 16),
                    size=int(size_m.group(1), 16),
                    file_name=file_m.group(1) if file_m else None,
                )
            i += 2
        else:
            i += 1
    return partitions


def find_scatter(rom_dir):
    rom_path = Path(rom_dir)
    for pattern in ['*_Android_scatter.txt', '*scatter*.txt']:
        for f in rom_path.rglob(pattern):
            if f.is_file():
                return str(f)
    return None


def detect_device():
    if not HAS_USB:
        return None
    for pid in BROM_PIDS + PRELOADER_PIDS:
        dev = usb.core.find(idVendor=MTK_VID, idProduct=pid)
        if dev:
            try:
                if dev.is_kernel_driver_active(0):
                    dev.detach_kernel_driver(0)
            except Exception:
                pass
            try:
                usb.util.claim_interface(dev, 0)
            except Exception:
                pass
            return dev
    return None


def wait_for_device(timeout=30.0):
    logger.info("Waiting for MTK device... (Vol+ + Vol- and plug USB)")
    start = time.time()
    while time.time() - start < timeout:
        dev = detect_device()
        if dev:
            return dev
        time.sleep(0.5)
    return None


def flash_partition(dev, entry, file_path):
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return False

    with open(file_path, 'rb') as f:
        data = f.read()

    logger.info(f"Writing {entry.name} ({len(data)} bytes) to {hex(entry.start_addr)}")

    try:
        cfg = dev.get_active_configuration()
        intf = cfg[(0, 0)]
        ep_out = usb.util.find_descriptor(
            intf, custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT
        )
        ep_in = usb.util.find_descriptor(
            intf, custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN
        )

        if not ep_out:
            logger.error("No USB OUT endpoint")
            return False

        cmd = struct.pack("<III", 0xD1, entry.start_addr, len(data))
        ep_out.write(cmd, timeout=1000)

        for i in range(0, len(data), 4096):
            chunk = data[i:i + 4096]
            ep_out.write(chunk, timeout=10000)
            time.sleep(0.001)

        time.sleep(0.1)
        if ep_in:
            try:
                ack = ep_in.read(4, timeout=5000)
                status = struct.unpack("<I", bytes(ack[:4]))[0]
                if status == 0:
                    logger.info(f"  {entry.name} OK")
                    return True
                else:
                    logger.warning(f"  {entry.name} status: {hex(status)}")
                    return True
            except Exception:
                pass

        logger.info(f"  {entry.name} written")
        return True

    except Exception as e:
        logger.error(f"  {entry.name} FAILED: {e}")
        return False


def cmd_flash(args):
    print(BANNER)
    rom_dir = os.path.abspath(args.rom_dir)
    if not os.path.isdir(rom_dir):
        logger.error(f"ROM directory not found: {rom_dir}")
        return 1

    scatter_path = args.scatter or find_scatter(rom_dir)
    if not scatter_path:
        logger.error(f"No scatter file found in {rom_dir}")
        return 1

    logger.info(f"Scatter: {scatter_path}")
    partitions = parse_scatter(scatter_path)

    skip_set = SKIP_PARTITIONS.copy()
    if getattr(args, 'skip_userdata', False):
        skip_set.update({"userdata", "Userdata", "metadata"})

    flash_items = []
    for name, entry in partitions.items():
        if entry.file_name and name not in skip_set:
            fpath = os.path.join(rom_dir, entry.file_name)
            if os.path.exists(fpath):
                flash_items.append((name, entry, fpath))

    print(f"\n{'Partition':<20} {'Size':<15} {'File'}")
    print("-" * 60)
    for name, entry, fpath in flash_items:
        sz = entry.size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if sz < 1024:
                sz_str = f"{sz:.1f}{unit}"
                break
            sz /= 1024
        print(f"{name:<20} {sz_str:<15} {os.path.basename(fpath)}")
    print(f"\nTotal: {len(flash_items)} partitions")

    if not args.yes:
        confirm = input("\nProceed? [y/N] ").strip().lower()
        if confirm != 'y':
            return 0

    logger.info("Connect device in BROM mode...")
    dev = wait_for_device(timeout=args.timeout)
    if not dev:
        logger.error("No MTK device found")
        return 1

    success = 0
    for name, entry, fpath in flash_items:
        if flash_partition(dev, entry, fpath):
            success += 1

    logger.info(f"\nDone: {success}/{len(flash_items)} partitions flashed")

    try:
        usb.util.dispose_resources(dev)
    except Exception:
        pass

    return 0 if success == len(flash_items) else 1


def cmd_info(args):
    print(BANNER)
    logger.info("Connecting to device...")
    dev = wait_for_device(timeout=args.timeout)
    if not dev:
        logger.error("No MTK device found")
        return 1

    print(f"\nDevice detected:")
    print(f"  VID: {hex(MTK_VID)}")
    try:
        print(f"  PID: {hex(dev.idProduct)}")
    except Exception:
        print(f"  PID: unknown")

    try:
        usb.util.dispose_resources(dev)
    except Exception:
        pass
    return 0


def input_path(prompt, is_dir=True):
    """Interactive path input with tab completion and cleanup"""
    try:
        import readline
        completer = PathCompleter(is_dir=is_dir)
        readline.set_completer(completer.complete)
        readline.parse_and_bind("tab: complete")
    except ImportError:
        pass

    raw = input(prompt).strip()
    # Clean path: remove surrounding quotes and whitespace
    raw = raw.strip("'\" \t\n")
    return raw


class PathCompleter:
    """Tab completion for file paths"""
    def __init__(self, is_dir=True):
        self.is_dir = is_dir

    def complete(self, text, state):
        if not text:
            text = "./"
        matches = []
        expanded = os.path.expanduser(text)
        parent = os.path.dirname(expanded) or "."
        prefix = os.path.basename(expanded)

        try:
            for name in os.listdir(parent):
                if name.startswith(prefix):
                    full = os.path.join(parent, name)
                    if self.is_dir and os.path.isdir(full):
                        matches.append(full + "/")
                    elif not self.is_dir:
                        matches.append(full)
        except OSError:
            pass

        if state < len(matches):
            return matches[state]
        return None


def cmd_interactive(args):
    """Interactive mode - ask user for paths"""
    print(BANNER)

    # Menu
    print("=" * 50)
    print("  MTK Unbrick - Interactive Mode")
    print("=" * 50)
    print("  1) Flash firmware")
    print("  2) Flash (skip confirmation)")
    print("  3) Flash (skip userdata)")
    print("  4) Show device info")
    print("  5) Exit")
    print("=" * 50)

    choice = input("\nSelect [1-5]: ").strip()

    if choice in ("1", "2", "3"):
        # Pick ROM folder
        print(f"\n{'=' * 50}")
        print("  Enter ROM folder path")
        print("  (drag & drop folder here, then press Enter)")
        print("=" * 50)
        rom_dir = input_path("ROM Folder: ")

        if not rom_dir or not os.path.isdir(rom_dir):
            print(f"Folder not found: {rom_dir}")
            return 1

        print(f"  -> {rom_dir}")

        # Pick scatter
        scatter = find_scatter(rom_dir)
        if scatter:
            print(f"\n  Auto-detected scatter: {scatter}")
            use = input("  Use this? [Y/n] ").strip().lower()
            if use == "n":
                scatter = ""

        if not scatter:
            print("\nEnter scatter file path (tab for completion):")
            scatter = input_path("Scatter: ", is_dir=False)
            if scatter and not os.path.exists(scatter):
                print(f"  File not found: {scatter}")
                scatter = ""

        # Build args
        class FlashArgs:
            pass

        fa = FlashArgs()
        fa.rom_dir = rom_dir
        fa.scatter = scatter if scatter else None
        fa.yes = choice == "2"
        fa.skip_userdata = choice == "3"
        fa.timeout = 30.0

        # Simulate args for cmd_flash
        if fa.skip_userdata:
            sys.argv = ["mtk_unbrick", "flash", rom_dir, "--skip-userdata"]
        elif fa.yes:
            sys.argv = ["mtk_unbrick", "flash", rom_dir, "-y"]
        else:
            sys.argv = ["mtk_unbrick", "flash", rom_dir]

        if fa.scatter:
            sys.argv.extend(["-s", fa.scatter])

        parser = build_parser()
        pargs = parser.parse_args()
        return pargs.func(pargs)

    elif choice == "4":
        sys.argv = ["mtk_unbrick", "info"]
        parser = build_parser()
        pargs = parser.parse_args()
        return pargs.func(pargs)

    else:
        print("Bye!")
        return 0


def build_parser():
    """Build argument parser"""
    parser = argparse.ArgumentParser(description="MTK Unbrick - Flash Xiaomi MTK via BROM")
    sub = parser.add_subparsers(dest="command")

    p_interact = sub.add_parser("interactive", help="Interactive mode")
    p_interact.set_defaults(func=cmd_interactive)

    p_flash = sub.add_parser("flash", help="Flash firmware from ROM folder")
    p_flash.add_argument("rom_dir", help="Extracted fastboot ROM folder")
    p_flash.add_argument("-s", "--scatter", help="Scatter file path")
    p_flash.add_argument("-y", "--yes", action="store_true", help="Skip confirmation")
    p_flash.add_argument("--skip-userdata", action="store_true", help="Skip userdata")
    p_flash.add_argument("-t", "--timeout", type=float, default=30.0)
    p_flash.set_defaults(func=cmd_flash)

    p_info = sub.add_parser("info", help="Show device info")
    p_info.add_argument("-t", "--timeout", type=float, default=30.0)
    p_info.set_defaults(func=cmd_info)

    return parser


def main():
    # If no args, run interactive mode
    if len(sys.argv) == 1:
        return cmd_interactive(None)

    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        return cmd_interactive(None)

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
