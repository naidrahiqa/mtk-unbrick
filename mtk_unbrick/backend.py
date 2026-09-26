"""Subprocess backend around bkerler/mtkclient.

mtkclient owns everything USB/BROM/DA (auth bypass, exploits, DRAM setup).
This module only locates it, builds commands, streams output and parses
the GPT so the CLI can map ROM files to partitions.
"""
import glob
import os
import re
import shutil
import subprocess
import sys

from .utils import format_size

GPT_LINE = re.compile(
    r"^(\S+):\s+Offset (0x[0-9a-fA-F]+), Length (0x[0-9a-fA-F]+)"
)

# Never auto-flash these: IMEI/serials/security/bootloader live here.
# Includes lk — flashing a bad bootloader is a hard-brick vector; use
# --force deliberately (e.g. restoring a verified stock LK during unbrick).
DANGEROUS = {
    "preloader", "pgpt", "sgpt", "gpt", "primary_gpt", "secondary_gpt",
    "nvram", "nvdata", "nvcfg", "proinfo", "protect1", "protect2",
    "persist", "persistbak", "seccfg", "otp", "flashinfo", "efuse",
    "sec1", "expdb", "lk",
}


class BackendError(Exception):
    pass


def find_mtkclient(explicit=None):
    """Locate mtkclient's mtk.py."""
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.dirname(here)
    candidates = [
        explicit,
        os.environ.get("MTKCLIENT"),
        os.path.join(repo, "mtkclient", "mtk.py"),
        os.path.join(repo, "..", "mtkclient", "mtk.py"),
        os.path.expanduser("~/mtkclient/mtk.py"),
        shutil.which("mtk.py"),
    ]
    for c in candidates:
        if c and os.path.isfile(os.path.expanduser(c)):
            return os.path.abspath(os.path.expanduser(c))
    raise BackendError(
        "mtkclient not found. Clone it first:\n"
        "  git clone https://github.com/bkerler/mtkclient ~/mtkclient\n"
        "or point at it with --mtkclient /path/to/mtk.py (or $MTKCLIENT)."
    )


def find_preloader(rom_dir):
    """Find a preloader image in a ROM folder (needed for DRAM/EMI setup)."""
    patterns = ["preloader*.img", "preloader*.bin", "*preloader*.bin"]
    seen = set()
    for pat in patterns:
        for f in sorted(glob.glob(os.path.join(rom_dir, "**", pat), recursive=True)):
            if f not in seen and os.path.isfile(f):
                seen.add(f)
                # Prefer plain preloader.img over preloader_raw/signed variants
                base = os.path.basename(f).lower()
                if "raw" not in base and "signed" not in base:
                    return f
    return sorted(seen)[0] if seen else None


def _build_cmd(mtk_path, args, preloader=None, python=None):
    cmd = [python or sys.executable, mtk_path]
    if preloader:
        cmd += ["--preloader", preloader]
    return cmd + list(args)


def run(mtk_path, args, preloader=None, python=None):
    """Run mtkclient with live output. Returns exit code."""
    cmd = _build_cmd(mtk_path, args, preloader, python)
    print("$ " + " ".join(cmd), flush=True)
    try:
        return subprocess.call(cmd)
    except FileNotFoundError as e:
        raise BackendError(f"Cannot run mtkclient: {e}")


def run_capture(mtk_path, args, preloader=None, python=None):
    """Run mtkclient, echo output AND collect it. Returns (rc, text)."""
    cmd = _build_cmd(mtk_path, args, preloader, python)
    print("$ " + " ".join(cmd), flush=True)
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        bufsize=1,
    )
    lines = []
    for line in proc.stdout:
        print(line, end="", flush=True)
        lines.append(line)
    proc.wait()
    return proc.returncode, "".join(lines)


def get_gpt(mtk_path, preloader=None, python=None):
    """Return {partition: (offset, length)} from printgpt."""
    rc, out = run_capture(mtk_path, ["printgpt"], preloader, python)
    gpt = {}
    for line in out.splitlines():
        m = GPT_LINE.match(line.strip())
        if m:
            gpt[m.group(1)] = (int(m.group(2), 16), int(m.group(3), 16))
    if rc != 0 or not gpt:
        raise BackendError(
            "Could not read GPT — is the device connected in BROM mode?\n"
            "Hold Vol+ + Vol- and plug USB while mtkclient waits."
        )
    return gpt


def resolve_targets(part_name, gpt, slot="both"):
    """Map a logical partition name to real GPT names (handles A/B)."""
    if part_name in gpt:
        return [part_name]
    a, b = part_name + "_a", part_name + "_b"
    has_a, has_b = a in gpt, b in gpt
    if has_a and has_b:
        if slot == "a":
            return [a]
        if slot == "b":
            return [b]
        return [a, b]
    if has_a:
        return [a]
    if has_b:
        return [b]
    return []


def build_flash_list(rom_dir, gpt, slot="both", skip_userdata=False, force=False):
    """Map ROM files to (partition, file) pairs.

    Skips dangerous partitions unless --force. preloader files are never
    flashed — they are used as --preloader helper only.
    """
    items = []
    skipped = []
    files = sorted(
        f for ext in ("*.img", "*.bin")
        for f in glob.glob(os.path.join(rom_dir, "**", ext), recursive=True)
    )
    for f in files:
        base = os.path.basename(f)
        stem = os.path.splitext(base)[0]
        lower = stem.lower()

        if lower.startswith("preloader"):
            skipped.append((base, "preloader (used as --preloader helper only)"))
            continue
        if lower in ("userdata", "user_data") and skip_userdata:
            skipped.append((base, "userdata skipped"))
            continue
        # Normalize A/B suffix: lk_a.img -> lk (dangerous check)
        key = lower[:-2] if lower.endswith(("_a", "_b")) else lower
        if key in DANGEROUS and not force:
            skipped.append((base, "dangerous partition (needs --force)"))
            continue

        targets = resolve_targets(lower, gpt, slot)
        if not targets:
            skipped.append((base, "no matching partition in GPT"))
            continue

        size = os.path.getsize(f)
        too_big = [t for t in targets if size > gpt[t][1]]
        if too_big:
            skipped.append((base, f"larger than {', '.join(too_big)}"))
            continue

        for t in targets:
            items.append((t, f))
    return items, skipped
