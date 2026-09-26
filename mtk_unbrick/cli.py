"""CLI entry point — thin layer on top of the mtkclient backend."""
import argparse
import logging
import os
import sys
import time

from .backend import (
    BackendError, build_flash_list, find_mtkclient, find_preloader,
    get_gpt, resolve_targets, run, run_capture, DANGEROUS,
)
from .utils import format_size

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

CYAN = "\033[0;36m"
NC = "\033[0m"

BANNER = r"""
  __  __ _ __  __        ____  _             _
 |  \/  (_)  \/  |  ___ | __ )(_) _ __   __| | ___ _ __
 | |\/| | | |\/| | / _ \|  _ \| || '_ \ / _` |/ _ \ '__|
 | |  | | | |  | ||  __/| |_) | || | | | (_| |  __/ |
 |_|  |_|_|_|  |_| \___||____/|_||_| |_|\__,_|\___|_|
                    v0.2.0 - BROM Unbrick Tool (mtkclient backend)
"""

BACKUP_PARTITIONS = [
    "lk_a", "lk_b", "seccfg", "nvram", "nvdata", "nvcfg",
    "protect1", "protect2", "persist", "para", "expdb",
]


def _ctx(args):
    """Resolve mtkclient path + preloader once per invocation."""
    mtk = find_mtkclient(args.mtkclient)
    preloader = args.preloader
    if not preloader and args.rom_dir:
        preloader = find_preloader(args.rom_dir)
        if preloader:
            logger.info(f"Auto preloader: {preloader}")
    if not preloader:
        logger.warning(
            "No preloader given — DRAM setup may fail with "
            "'unpack requires a buffer of 12 bytes'. Pass --preloader."
        )
    return mtk, preloader


def cmd_flash(args):
    print(BANNER)
    rom_dir = os.path.abspath(args.rom_dir)
    if not os.path.isdir(rom_dir):
        logger.error(f"ROM directory not found: {rom_dir}")
        return 1

    mtk, preloader = _ctx(args)

    print("\nConnect device: power off, hold Vol+ + Vol-, plug USB...\n")
    try:
        gpt = get_gpt(mtk, preloader, args.python)
    except BackendError as e:
        logger.error(str(e))
        return 1

    items, skipped = build_flash_list(
        rom_dir, gpt, slot=args.slot,
        skip_userdata=args.skip_userdata, force=args.force,
    )

    print(f"\n{'Partition':<22} {'File':<32} {'Size'}")
    print("-" * 70)
    for part, f in items:
        print(f"{part:<22} {os.path.basename(f):<32} {format_size(os.path.getsize(f))}")
    print(f"\nTotal: {len(items)} partitions to flash")
    if skipped:
        print("\nSkipped:")
        for name, why in skipped:
            print(f"  - {name}: {why}")

    if not items:
        logger.error("Nothing to flash.")
        return 1

    if not args.yes:
        if input("\nProceed? [y/N] ").strip().lower() != "y":
            print("Aborted.")
            return 0

    failures = []
    for part, f in items:
        print(f"\n=== Flashing {part} <- {os.path.basename(f)} ===")
        if run(mtk, ["w", part, f], preloader, args.python) != 0:
            failures.append(part)

    print(f"\nDone: {len(items) - len(failures)}/{len(items)} partitions flashed")
    if failures:
        print("Failed: " + ", ".join(failures))
        print("(Device may need a replug between attempts — unplug, hold")
        print(" Vol+ + Vol-, plug again, then retry the failed partition.)")
        return 1

    if not args.no_reset:
        print("\nResetting device...")
        run(mtk, ["reset"], preloader, args.python)
    return 0


def cmd_info(args):
    print(BANNER)
    try:
        mtk = find_mtkclient(args.mtkclient)
    except BackendError as e:
        logger.error(str(e))
        return 1
    print("\nConnect device: power off, hold Vol+ + Vol-, plug USB...\n")
    rc, out = run_capture(mtk, ["printgpt"], args.preloader, args.python)
    if rc != 0:
        logger.error("Device not found or GPT read failed.")
        return 1
    return 0


def cmd_read(args):
    print(BANNER)
    try:
        mtk = find_mtkclient(args.mtkclient)
    except BackendError as e:
        logger.error(str(e))
        return 1
    print("\nConnect device...\n")
    rc, out = run_capture(mtk, ["printgpt"], args.preloader, args.python)
    if rc != 0:
        logger.error("Device not found.")
        return 1

    gpt = {}
    from .backend import GPT_LINE
    for line in out.splitlines():
        m = GPT_LINE.match(line.strip())
        if m:
            gpt[m.group(1)] = (int(m.group(2), 16), int(m.group(3), 16))

    targets = resolve_targets(args.partition, gpt, args.slot)
    if not targets:
        logger.error(f"Partition '{args.partition}' not in GPT.")
        return 1

    os.makedirs(os.path.dirname(os.path.abspath(args.output)) or ".", exist_ok=True)
    rc = run(mtk, ["r", targets[0], args.output], args.preloader, args.python)
    if rc == 0:
        logger.info(f"Saved: {args.output}")
    return rc


def cmd_erase(args):
    print(BANNER)
    if args.partition in DANGEROUS and not args.force:
        logger.error(
            f"'{args.partition}' is a dangerous partition (IMEI/security data). "
            "Use --force if you really mean it."
        )
        return 1
    if not args.yes:
        if input(f"Erase '{args.partition}'? This is irreversible. [y/N] ").strip().lower() != "y":
            print("Aborted.")
            return 0
    try:
        mtk = find_mtkclient(args.mtkclient)
    except BackendError as e:
        logger.error(str(e))
        return 1
    return run(mtk, ["e", args.partition], args.preloader, args.python)


def cmd_backup(args):
    print(BANNER)
    out_dir = os.path.abspath(args.output)
    os.makedirs(out_dir, exist_ok=True)
    try:
        mtk = find_mtkclient(args.mtkclient)
    except BackendError as e:
        logger.error(str(e))
        return 1

    print("\nConnect device...\n")
    try:
        gpt = get_gpt(mtk, args.preloader, args.python)
    except BackendError as e:
        logger.error(str(e))
        return 1

    saved, failed = [], []
    for part in BACKUP_PARTITIONS:
        if part not in gpt:
            continue
        dest = os.path.join(out_dir, f"{part}.img")
        print(f"\n=== Backing up {part} ({format_size(gpt[part][1])}) ===")
        if run(mtk, ["r", part, dest], args.preloader, args.python) == 0:
            saved.append(part)
        else:
            failed.append(part)

    print(f"\nBackup done: {len(saved)} ok, {len(failed)} failed -> {out_dir}")
    if failed:
        print("Failed: " + ", ".join(failed))
        return 1
    return 0


def cmd_reset(args):
    try:
        mtk = find_mtkclient(args.mtkclient)
    except BackendError as e:
        logger.error(str(e))
        return 1
    return run(mtk, ["reset"], args.preloader, args.python)


def _ask(prompt, default=""):
    try:
        val = input(prompt).strip()
    except EOFError:
        return default
    return val or default


def cmd_interactive(args):
    """Menu-driven mode (default when run with no args). Cross-platform."""
    print(BANNER)
    try:
        mtk = find_mtkclient(args.mtkclient)
    except BackendError as e:
        logger.error(str(e))
        print("\nTip: git clone https://github.com/bkerler/mtkclient ~/mtkclient"
              "\n     pip install -r ~/mtkclient/requirements.txt")
        return 1

    preloader = args.preloader
    if not preloader:
        probe = _ask("ROM folder (for auto preloader, Enter to skip): ")
        if probe and os.path.isdir(probe):
            preloader = find_preloader(probe)
            if preloader:
                logger.info(f"Auto preloader: {preloader}")
        elif probe:
            logger.warning(f"Not a directory: {probe}")
    if not preloader:
        logger.warning("No preloader — if DRAM setup fails, pass --preloader.")

    while True:
        print(f"""
{CYAN}==========================================
  1) Flash ROM folder
  2) Show device info (GPT)
  3) Backup critical partitions
  4) Read partition to file
  5) Erase partition
  6) Reboot device
  7) Exit
=========================================={NC}""")
        choice = _ask("Select [1-7]: ", "7")
        try:
            if choice == "1":
                rom = _ask("ROM folder: ")
                if not rom:
                    continue
                a = argparse.Namespace(
                    mtkclient=args.mtkclient, preloader=preloader,
                    python=args.python, rom_dir=rom, yes=False,
                    slot="both", skip_userdata=False, force=False,
                    no_reset=False,
                )
                cmd_flash(a)
            elif choice == "2":
                cmd_info(args)
            elif choice == "3":
                out = _ask("Backup directory: ", "./backup")
                cmd_backup(argparse.Namespace(**vars(args), output=out))
            elif choice == "4":
                part = _ask("Partition (e.g. lk_a): ")
                if not part:
                    continue
                out = _ask("Output file: ", f"./{part}.img")
                cmd_read(argparse.Namespace(
                    mtkclient=args.mtkclient, preloader=args.preloader,
                    python=args.python, partition=part, output=out, slot="a"))
            elif choice == "5":
                part = _ask("Partition to erase: ")
                if part and _ask(f"Really erase '{part}'? [y/N]: ").lower() == "y":
                    cmd_erase(argparse.Namespace(
                        mtkclient=args.mtkclient, preloader=args.preloader,
                        python=args.python, partition=part, yes=True, force=False))
            elif choice == "6":
                cmd_reset(args)
            elif choice == "7":
                return 0
            else:
                print("Invalid option.")
        except BackendError as e:
            logger.error(str(e))


def build_parser():
    parser = argparse.ArgumentParser(
        description="MTK Unbrick - flash Xiaomi MTK devices via BROM (mtkclient backend)",
    )
    parser.add_argument("--version", action="version",
                        version=f"mtk-unbrick {__import__('mtk_unbrick').__version__}")
    parser.add_argument("--mtkclient", help="Path to mtkclient's mtk.py")
    parser.add_argument("--preloader", help="Preloader image (DRAM/EMI config)")
    parser.add_argument("--python", help="Python interpreter to run mtkclient with")

    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("flash", help="Flash images from a ROM folder")
    p.add_argument("rom_dir", help="Folder with *.img files (extracted ROM / dump)")
    p.add_argument("-y", "--yes", action="store_true", help="Skip confirmation")
    p.add_argument("--slot", choices=["a", "b", "both"], default="both",
                   help="Target slot(s) for A/B partitions (default: both)")
    p.add_argument("--skip-userdata", action="store_true", help="Do not flash userdata")
    p.add_argument("--force", action="store_true",
                   help="Allow dangerous partitions (nvram, seccfg, ...)")
    p.add_argument("--no-reset", action="store_true", help="Do not reset after flash")
    p.set_defaults(func=cmd_flash)

    p = sub.add_parser("info", help="Show device info + GPT")
    p.set_defaults(func=cmd_info)

    p = sub.add_parser("read", help="Read a partition to a file")
    p.add_argument("partition", help="Partition name (e.g. lk_a, boot)")
    p.add_argument("output", help="Output file path")
    p.add_argument("--slot", choices=["a", "b", "both"], default="a")
    p.set_defaults(func=cmd_read)

    p = sub.add_parser("erase", help="Erase a partition")
    p.add_argument("partition")
    p.add_argument("-y", "--yes", action="store_true")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_erase)

    p = sub.add_parser("backup", help="Backup critical partitions")
    p.add_argument("output", nargs="?", default="./backup",
                   help="Output directory (default: ./backup)")
    p.set_defaults(func=cmd_backup)

    p = sub.add_parser("reset", help="Reboot device")
    p.set_defaults(func=cmd_reset)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        # No subcommand: interactive menu when on a terminal
        # (double-click unbrick.bat / run ./unbrick.sh / python mtk_unbrick.py)
        if sys.stdin.isatty():
            return cmd_interactive(args)
        parser.print_help()
        return 1
    try:
        return args.func(args)
    except BackendError as e:
        logger.error(str(e))
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
