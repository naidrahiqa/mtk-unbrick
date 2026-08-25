"""Parse MTK scatter files (MT6768_MT6765_Android_scatter.txt format)"""
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class PartitionEntry:
    name: str
    partition_index: int
    linear_start_addr: str
    partition_size: str
    region: str
    storage: str
    file_name: Optional[str] = None
    download_size: Optional[int] = None
    type: Optional[str] = None

    @property
    def start_addr(self) -> int:
        return int(self.linear_start_addr, 16)

    @property
    def size(self) -> int:
        return int(self.partition_size, 16)


@dataclass
class ScatterInfo:
    platform: str
    project: str
    storage: str
    boot_style: str
    partitions: Dict[str, PartitionEntry] = field(default_factory=dict)

    @property
    def scatter_dir(self) -> str:
        return ""


class ScatterParser:
    """Parser for MTK scatter files"""

    def __init__(self, scatter_path: str):
        self.scatter_path = scatter_path
        self.info: Optional[ScatterInfo] = None
        self._parse()

    def _parse(self):
        with open(self.scatter_path, "r") as f:
            content = f.read()

        # Parse general info
        platform = self._extract(r"platform\s*:\s*(\S+)", content)
        project = self._extract(r"project\s*:\s*(\S+)", content)
        storage = self._extract(r"storage_type\s*:\s*(\S+)", content)
        boot_style = self._extract(r"boot_style\s*:\s*(.+)", content)

        self.info = ScatterInfo(
            platform=platform or "unknown",
            project=project or "unknown",
            storage=storage or "emmc",
            boot_style=boot_style or "unknown",
        )

        # Parse partitions
        partition_blocks = re.split(r"(\w+\s*\{$)", content)
        i = 0
        while i < len(partition_blocks):
            block = partition_blocks[i]
            match = re.match(r"(\w+)\s*\{", block)
            if match:
                partition_name = match.group(1)
                if i + 1 < len(partition_blocks):
                    body = partition_blocks[i + 1]
                    entry = self._parse_partition_block(partition_name, body)
                    if entry:
                        self.info.partitions[partition_name] = entry
                i += 2
            else:
                i += 1

    def _extract(self, pattern: str, text: str) -> Optional[str]:
        match = re.search(pattern, text, re.IGNORECASE)
        return match.group(1).strip() if match else None

    def _parse_partition_block(self, name: str, body: str) -> Optional[PartitionEntry]:
        # Stop at next partition block
        body = re.split(r"\n\s*\w+\s*\{", body)[0]

        partition_index = self._extract_int(r"partition_index\s*:\s*(\S+)", body)
        linear_start = self._extract(r"linear_start_addr\s*:\s*(\S+)", body)
        part_size = self._extract(r"partition_size\s*:\s*(\S+)", body)
        region = self._extract(r"region\s*:\s*(\S+)", body)
        storage = self._extract(r"storage\s*:\s*(\S+)", body)
        file_name = self._extract(r"file_name\s*:\s*(\S+)", body)
        download_size = self._extract(r"download_size\s*:\s*(\S+)", body)
        part_type = self._extract(r"type\s*:\s*(\S+)", body)

        if not all([linear_start, part_size]):
            return None

        return PartitionEntry(
            name=name,
            partition_index=partition_index or 0,
            linear_start_addr=linear_start,
            partition_size=part_size,
            region=region or "USERDATA",
            storage=storage or "EMMC",
            file_name=file_name,
            download_size=int(download_size, 16) if download_size else None,
            type=part_type,
        )

    def _extract_int(self, pattern: str, text: str) -> Optional[int]:
        val = self._extract(pattern, text)
        if val:
            try:
                return int(val, 0)
            except ValueError:
                return None
        return None

    def get_flash_list(self, rom_dir: str) -> List[tuple]:
        """Return list of (partition_name, file_path) for files that exist"""
        result = []
        for name, entry in self.info.partitions.items():
            if entry.file_name:
                file_path = os.path.join(rom_dir, entry.file_name)
                if os.path.exists(file_path):
                    result.append((name, file_path))
        return result

    def get_partition_info(self, name: str) -> Optional[PartitionEntry]:
        return self.info.partitions.get(name)
