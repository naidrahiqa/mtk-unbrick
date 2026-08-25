"""Flash engine - write partitions to MTK device"""
import os
import struct
import logging
import time
from typing import List, Tuple, Optional
from .scatter import ScatterParser, PartitionEntry

logger = logging.getLogger(__name__)


class MTKFlasher:
    """Flash partitions to MTK device via BROM/DA"""

    # Partition types that should be skipped or handled specially
    SKIP_PARTITIONS = {"preloader", "pgpt", "sgpt", "proinfo", "nvram", "nvdata"}

    # Critical partitions that should be backed up first
    CRITICAL_PARTITIONS = {"nvram", "nvdata", "nvcfg", "persist", "protect1", "protect2", "seccfg"}

    def __init__(self, device, scatter_path: str):
        self.device = device
        self.parser = ScatterParser(scatter_path)
        self.device_info = None
        self._partitions_written = []

    def read_partition(self, name: str, output_path: str) -> bool:
        """Read a single partition from device"""
        entry = self.parser.get_partition_info(name)
        if not entry:
            logger.error(f"Partition '{name}' not found in scatter")
            return False

        logger.info(f"Reading partition '{name}' ({entry.size} bytes)...")
        try:
            # Send read command
            cmd = struct.pack("<III", 0xD2, entry.start_addr, entry.size)
            self.device.write(cmd, timeout=1000)

            # Read data
            data = b''
            remaining = entry.size
            while remaining > 0:
                chunk = self.device.read(min(remaining, 4096), timeout=10000)
                data += chunk
                remaining -= len(chunk)

            with open(output_path, 'wb') as f:
                f.write(data)

            logger.info(f"Partition '{name}' saved to {output_path}")
            return True

        except Exception as e:
            logger.error(f"Read partition failed: {e}")
            return False

    def write_partition(self, name: str, file_path: str) -> bool:
        """Write a single partition to device"""
        entry = self.parser.get_partition_info(name)
        if not entry:
            logger.error(f"Partition '{name}' not found in scatter")
            return False

        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return False

        file_size = os.path.getsize(file_path)
        logger.info(f"Writing partition '{name}' ({file_size} bytes) to addr {hex(entry.start_addr)}...")

        try:
            with open(file_path, 'rb') as f:
                data = f.read()

            # Send write command
            cmd = struct.pack("<III", 0xD1, entry.start_addr, len(data))
            self.device.write(cmd, timeout=1000)

            # Send data in chunks
            chunk_size = 4096
            for i in range(0, len(data), chunk_size):
                chunk = data[i:i + chunk_size]
                self.device.write(chunk, timeout=10000)
                time.sleep(0.001)

            # Wait for ACK
            time.sleep(0.1)
            try:
                ack = self.device.read(4, timeout=5000)
                if len(ack) >= 4:
                    status = struct.unpack("<I", ack[:4])[0]
                    if status == 0:
                        logger.info(f"Partition '{name}' written successfully")
                        self._partitions_written.append(name)
                        return True
                    else:
                        logger.error(f"Write error status: {hex(status)}")
                        return False
            except Exception:
                # Some devices don't send ACK
                logger.info(f"Partition '{name}' written (no ACK)")
                self._partitions_written.append(name)
                return True

        except Exception as e:
            logger.error(f"Write partition failed: {e}")
            return False

    def write_full_flash(self, rom_dir: str, skip_userdata: bool = False) -> Tuple[int, int]:
        """Write all partitions from ROM directory. Returns (success_count, total_count)"""
        flash_list = self.parser.get_flash_list(rom_dir)
        total = len(flash_list)
        success = 0

        logger.info(f"Flash list: {total} partitions found")

        for name, file_path in flash_list:
            if skip_userdata and name in ("userdata", "Userdata"):
                logger.info(f"Skipping userdata partition")
                continue

            if name in self.SKIP_PARTITIONS:
                logger.info(f"Skipping system partition: {name}")
                continue

            if self.write_partition(name, file_path):
                success += 1

        return success, total

    def erase_partition(self, name: str) -> bool:
        """Erase a partition"""
        entry = self.parser.get_partition_info(name)
        if not entry:
            logger.error(f"Partition '{name}' not found")
            return False

        logger.info(f"Erasing partition '{name}'...")
        try:
            cmd = struct.pack("<III", 0xD3, entry.start_addr, entry.size)
            self.device.write(cmd, timeout=1000)
            time.sleep(0.1)
            logger.info(f"Partition '{name}' erased")
            return True
        except Exception as e:
            logger.error(f"Erase failed: {e}")
            return False

    def print_flash_list(self, rom_dir: str):
        """Print partitions that will be flashed"""
        flash_list = self.parser.get_flash_list(rom_dir)
        print(f"\n{'Partition':<20} {'Size':<15} {'File'}")
        print("-" * 60)
        for name, file_path in flash_list:
            entry = self.parser.get_partition_info(name)
            size_str = self._format_size(entry.size) if entry else "?"
            print(f"{name:<20} {size_str:<15} {os.path.basename(file_path)}")
        print(f"\nTotal: {len(flash_list)} partitions")

    def backup_critical(self, backup_dir: str) -> bool:
        """Backup critical partitions before flashing"""
        os.makedirs(backup_dir, exist_ok=True)

        for name in self.CRITICAL_PARTITIONS:
            entry = self.parser.get_partition_info(name)
            if entry:
                backup_path = os.path.join(backup_dir, f"{name}.bin")
                self.read_partition(name, backup_path)

        return True

    def _format_size(self, size: int) -> str:
        """Format size to human readable"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}TB"
