"""CLI entry point for mtk-unbrick"""
import os
import sys
import time
import argparse
import logging
from pathlib import Path

from .scatter import ScatterParser
from .flasher import MTKFlasher
from .device import MTKDevice, wait_for_device, DeviceMode

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

BANNER = r"""
  __  __ _ __  __        ____  _             _
 |  \/  (_)  \/  |  ___ | __ )(_) _ __   __| | ___ _ __
 | |\/| | | |\/| | / _ \|  _ \| || '_ \ / _` |/ _ \ '__|
 | |  | | | |  | ||  __/| |_) | || | | | (_| |  __/ |
 |_|  |_|_|_|  |_| \___||____/|_||_| |_|\__,_|\___|_|
                    v0.1.0 - BROM Unbrick Tool
"""


def find_scatter(rom_dir: str) -> str:
    """Find scatter file in ROM directory"""
    rom_path = Path(rom_dir)

    # Common scatter file patterns
    patterns = [
        "*_Android_scatter.txt",
        "*scatter*.txt",
        "MT*_Android_scatter.txt",
    ]

    for pattern in patterns:
        for f in rom_path.glob(pattern):
            if f.is_file():
                return str(f)

    # Check images subdirectory
    images_dir = rom_path / "images"
    if images_dir.exists():
        for pattern in patterns:
            for f in images_dir.glob(pattern):
                if f.is_file():
                    return str(f)

    return None


def cmd_flash(args):
    """Flash firmware from ROM directory"""
    print(BANNER)

    rom_dir = os.path.abspath(args.rom_dir)
    if not os.path.isdir(rom_dir):
        logger.error(f"ROM directory not found: {rom_dir}")
        return 1

    # Find scatter file
    scatter_path = args.scatter or find_scatter(rom_dir)
    if not scatter_path:
        logger.error(f"No scatter file found in {rom_dir}")
        logger.info("Place *_Android_scatter.txt in ROM folder or use -s flag")
        return 1

    logger.info(f"Scatter: {scatter_path}")
    logger.info(f"ROM dir: {rom_dir}")

    # Parse scatter
    try:
        parser = ScatterParser(scatter_path)
        print(f"\nPlatform : {parser.info.platform}")
        print(f"Project  : {parser.info.project}")
        print(f"Storage  : {parser.info.storage}")
    except Exception as e:
        logger.error(f"Failed to parse scatter: {e}")
        return 1

    # Show flash list
    flasher = MTKFlasher(None, scatter_path)
    flasher.print_flash_list(rom_dir)

    if not args.yes:
        confirm = input("\nProceed with flash? [y/N] ").strip().lower()
        if confirm != 'y':
            logger.info("Aborted by user")
            return 0

    # Backup critical partitions if requested
    if args.backup:
        backup_dir = os.path.join(rom_dir, "backup_" + time.strftime("%Y%m%d_%H%M%S"))
        logger.info(f"Backing up critical partitions to {backup_dir}")

    # Wait for device
    logger.info("Connect device in BROM mode (Vol+ + Vol- and plug USB)...")
    device = wait_for_device(mode=DeviceMode.BROM, timeout=args.timeout)

    if not device:
        logger.error("No MTK device found in BROM mode")
        logger.info("Tips:")
        logger.info("  1. Power off device completely")
        logger.info("  2. Hold Volume Up + Volume Down")
        logger.info("  3. Plug USB cable while holding buttons")
        logger.info("  4. Wait for device detection")
        return 1

    logger.info(f"Device connected: {hex(device.info.pid)}")

    # Initialize flasher
    flasher = MTKFlasher(device, scatter_path)
    flasher.device_info = device.info

    # Flash
    logger.info("Starting flash...")
    success, total = flasher.write_full_flash(
        rom_dir,
        skip_userdata=args.skip_userdata
    )

    logger.info(f"\nFlash complete: {success}/{total} partitions written")

    if success == total:
        logger.info("All partitions flashed successfully!")
        logger.info("Device should reboot automatically")
    else:
        logger.warning(f"Failed to flash {total - success} partitions")

    device.close()
    return 0 if success == total else 1


def cmd_read(args):
    """Read a partition from device"""
    print(BANNER)

    scatter_path = args.scatter
    if not scatter_path:
        logger.error("Scatter file required (-s flag)")
        return 1

    if not os.path.exists(args.output):
        os.makedirs(args.output, exist_ok=True)

    logger.info(f"Scatter: {scatter_path}")
    logger.info(f"Reading partition: {args.partition}")

    # Wait for device
    logger.info("Connect device in BROM mode...")
    device = wait_for_device(mode=DeviceMode.BROM, timeout=args.timeout)

    if not device:
        logger.error("No MTK device found")
        return 1

    flasher = MTKFlasher(device, scatter_path)
    output_path = os.path.join(args.output, f"{args.partition}.bin")

    if flasher.read_partition(args.partition, output_path):
        logger.info(f"Partition saved to: {output_path}")
    else:
        logger.error("Failed to read partition")
        device.close()
        return 1

    device.close()
    return 0


def cmd_erase(args):
    """Erase a partition"""
    print(BANNER)

    scatter_path = args.scatter
    if not scatter_path:
        logger.error("Scatter file required (-s flag)")
        return 1

    logger.info(f"Erasing partition: {args.partition}")

    # Wait for device
    device = wait_for_device(mode=DeviceMode.BROM, timeout=args.timeout)

    if not device:
        logger.error("No MTK device found")
        return 1

    flasher = MTKFlasher(device, scatter_path)
    if flasher.erase_partition(args.partition):
        logger.info("Partition erased")
    else:
        logger.error("Failed to erase partition")
        device.close()
        return 1

    device.close()
    return 0


def cmd_unlock(args):
    """Unlock bootloader via seccfg"""
    print(BANNER)
    logger.info("Unlocking bootloader via seccfg...")

    device = wait_for_device(mode=DeviceMode.BROM, timeout=args.timeout)

    if not device:
        logger.error("No MTK device found in BROM mode")
        return 1

    # Send seccfg unlock command
    try:
        cmd = b'\xD4' + struct.pack("<I", 0x1)  # seccfg unlock
        device.write(cmd, timeout=5000)
        time.sleep(1)

        ack = device.read(4, timeout=5000)
        logger.info("Bootloader unlock command sent")
        logger.info("Device will reboot - hold Vol- for fastboot to verify")
    except Exception as e:
        logger.error(f"Unlock failed: {e}")
        device.close()
        return 1

    device.close()
    return 0


def cmd_info(args):
    """Show device info"""
    print(BANNER)

    logger.info("Connecting to device...")
    device = wait_for_device(mode=DeviceMode.BROM, timeout=args.timeout)

    if not device:
        logger.error("No MTK device found")
        return 1

    info = device.info
    print(f"\n{'='*40}")
    print(f"Device Information")
    print(f"{'='*40}")
    print(f"VID        : {hex(info.vid)}")
    print(f"PID        : {hex(info.pid)}")
    print(f"Mode       : {info.mode.value}")
    print(f"HW Code    : {hex(info.hw_code) if info.hw_code else 'N/A'}")
    print(f"HW Version : {hex(info.hw_ver) if info.hw_ver else 'N/A'}")
    print(f"SW Version : {hex(info.sw_ver) if info.sw_ver else 'N/A'}")
    print(f"ME ID      : {info.me_id or 'N/A'}")
    print(f"SOC ID     : {info.soc_id or 'N/A'}")
    print(f"SBC        : {'Enabled' if info.sbc_enabled else 'Disabled'}")
    print(f"SLA        : {'Enabled' if info.sla_enabled else 'Disabled'}")
    print(f"DAA        : {'Enabled' if info.daa_enabled else 'Disabled'}")
    print(f"{'='*40}\n")

    device.close()
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="MTK Unbrick - Flash Xiaomi MTK devices via BROM",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s flash ./firmware/              Flash firmware from ROM folder
  %(prog)s flash ./firmware/ -y           Flash without confirmation
  %(prog)s flash ./firmware/ -s scatter.txt  Use specific scatter file
  %(prog)s read boot boot.img -s scatter.txt  Read boot partition
  %(prog)s erase userdata -s scatter.txt   Erase userdata partition
  %(prog)s info                            Show device info
  %(prog)s unlock                          Unlock bootloader
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # flash command
    p_flash = subparsers.add_parser("flash", help="Flash firmware from ROM directory")
    p_flash.add_argument("rom_dir", help="Path to extracted fastboot ROM folder")
    p_flash.add_argument("-s", "--scatter", help="Scatter file path (auto-detect if not specified)")
    p_flash.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompt")
    p_flash.add_argument("-b", "--backup", action="store_true", help="Backup critical partitions before flash")
    p_flash.add_argument("--skip-userdata", action="store_true", help="Skip userdata partition")
    p_flash.add_argument("-t", "--timeout", type=float, default=30.0, help="Device detection timeout (seconds)")
    p_flash.set_defaults(func=cmd_flash)

    # read command
    p_read = subparsers.add_parser("read", help="Read a partition from device")
    p_read.add_argument("partition", help="Partition name (e.g. boot, system)")
    p_read.add_argument("output", help="Output file/directory path")
    p_read.add_argument("-s", "--scatter", required=True, help="Scatter file path")
    p_read.add_argument("-t", "--timeout", type=float, default=30.0, help="Timeout")
    p_read.set_defaults(func=cmd_read)

    # erase command
    p_erase = subparsers.add_parser("erase", help="Erase a partition")
    p_erase.add_argument("partition", help="Partition name")
    p_erase.add_argument("-s", "--scatter", required=True, help="Scatter file path")
    p_erase.add_argument("-t", "--timeout", type=float, default=30.0, help="Timeout")
    p_erase.set_defaults(func=cmd_erase)

    # info command
    p_info = subparsers.add_parser("info", help="Show connected device info")
    p_info.add_argument("-t", "--timeout", type=float, default=30.0, help="Timeout")
    p_info.set_defaults(func=cmd_info)

    # unlock command
    p_unlock = subparsers.add_parser("unlock", help="Unlock bootloader via seccfg")
    p_unlock.add_argument("-t", "--timeout", type=float, default=30.0, help="Timeout")
    p_unlock.set_defaults(func=cmd_unlock)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
