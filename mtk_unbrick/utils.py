"""Utility functions"""
import os
import hashlib
import struct


def calculate_md5(filepath: str) -> str:
    """Calculate MD5 hash of a file"""
    md5 = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            md5.update(chunk)
    return md5.hexdigest()


def find_files(directory: str, extensions: list) -> list:
    """Find files with given extensions in directory"""
    result = []
    for root, dirs, files in os.walk(directory):
        for f in files:
            if any(f.endswith(ext) for ext in extensions):
                result.append(os.path.join(root, f))
    return result


def format_size(size: int) -> str:
    """Format byte size to human readable"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"
