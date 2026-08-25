<div align="center">

# MTK Unbrick

**One-click unbrick tool untuk Xiaomi MTK devices via BROM mode**

Bypass auth dongle (SLA/DAA/SBC) dan flash firmware tanpa ribet.

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Linux](https://img.shields.io/badge/platform-linux-lightgrey.svg)]()

</div>

---

## Fitur

- **Auto-detect** device di BROM/Preloader mode
- **Auth bypass** (SLA/DAA/SBC) via exploit - ga perlu dongle lagi
- **Flash** firmware dari extracted fastboot ROM folder
- **Interactive mode** dengan tab completion path
- **Read/Erase** partitions
- **Backup** critical partitions (nvram, seccfg, dll)
- **Standalone script** - ga perlu install, tinggal `python3 mtk_unbrick.py`

## Demo

```
$ ./unbrick.sh

  __  __ _ __  __        ____  _             _
 |  \/  (_)  \/  |  ___ | __ )(_) _ __   __| | ___ _ __
 | |\/| | | |\/| | / _ \|  _ \| || '_ \ / _` |/ _ \ '__|
 | |  | | | |  | ||  __/| |_) | || | | | (_| |  __/ |
 |_|  |_|_|_|  |_| \___||____/|_||_| |_|\__,_|\___|_|
                    v0.1.0 - BROM Unbrick Tool

==========================================
  MTK Unbrick - Interactive Mode
==========================================
  1) Flash firmware
  2) Flash (skip confirmation)
  3) Flash (skip userdata)
  4) Show device info
  5) Exit
==========================================
Select [1-5]: 1

==========================================
  Enter ROM folder path
  (drag & drop folder here, then press Enter)
==========================================
ROM Folder: ~/Downloads/miui_FIRE_V14.0.25.6.9.DEV
  -> /home/user/Downloads/miui_FIRE_V14.0.25.6.9.DEV

  Auto-detected scatter: MT6768_Android_scatter.txt
  Use this? [Y/n] Y

==========================================
Partition            Size            File
----------------------------------------------
preloader            256.0KB         preloader_fire.bin
partition1           128.0KB         pgpt.bin
boot                 32.0MB          boot.img
...
==========================================
Total: 25 partitions

Proceed? [y/N] y

Waiting for MTK device... (Vol+ + Vol- and plug USB)
Device connected: 0xe8d:0x3

Writing boot (33554432 bytes) to 0x10000000
  boot OK
Writing system (2147483648 bytes) to 0x1a280000
  system OK
...

Done: 25/25 partitions flashed
```

## Instalasi

### Option 1: Standalone (ga perlu install)

```bash
git clone https://github.com/naidrahiqa/mtk-unbrick.git
cd mtk-unbrick
pip install pyusb
chmod +x unbrick.sh mtk_unbrick.py
./unbrick.sh
```

### Option 2: Install sebagai package

```bash
git clone https://github.com/naidrahiqa/mtk-unbrick.git
cd mtk-unbrick
pip install -e .
mtk-unbrick flash ./firmware/
```

### Requirements

- **Python 3.8+**
- **pyusb** (`pip install pyusb`)
- **libusb** (Linux: `sudo apt install libusb-1.0-0`)
- **USB access** (Linux: `sudo usermod -aG dialout $USER` lalu relogin)

## Cara Pakai

### Interactive Mode

```bash
./unbrick.sh
# atau
python3 mtk_unbrick.py
```

Langsung masuk menu, tinggal pilih opsi dan masukin path.

### Flash Firmware

```bash
# Basic flash
./unbrick.sh flash ~/Downloads/miui_FIRE/

# Skip confirmation
./unbrick.sh flash ~/Downloads/miui_FIRE/ -y

# Skip userdata (ga wipe data)
./unbrick.sh flash ~/Downloads/miui_FIRE/ --skip-userdata

# Pakai scatter file spesifik
./unbrick.sh flash ~/Downloads/miui_FIRE/ -s MT6768_Android_scatter.txt
```

### Standalone Python Script

```bash
python3 mtk_unbrick.py flash ~/Downloads/miui_FIRE/
python3 mtk_unbrick.py flash ~/Downloads/miui_FIRE/ -y
python3 mtk_unbrick.py info
```

### Install sebagai CLI Tool

```bash
pip install -e .
mtk-unbrick flash ~/Downloads/miui_FIRE/
mtk-unbrick info
```

## Masuk BROM Mode

1. **Power off** device完全
2. Tahan **Volume Up + Volume Down** barengan
3. Colok USB kabel sambil tahan tombol
4. Tunggu device kedetect

> **Tips:** Colok kabel USB 2.0 (bukan 3.0). Pakai kabel data original.

### Troubleshooting BROM

| Masalah | Solusi |
|---------|--------|
| Device ga kedetect | Coba port USB lain, pastikan kabel data |
| Detected tapi timeout | Driver USB belum keinstall |
| BROM flash gagal | Coba `--skip-userdata`, atau backup dulu |

## Supported Devices

Tool ini works untuk semua MTK Xiaomi devices, termasuk:

| Device | Codename | Chipset |
|--------|----------|---------|
| Redmi 12 | fire | MT6768 |
| Redmi 10 | selene | MT6768 |
| Redmi 9C | - | MT6765 |
| Redmi Note 9 | - | MT6768 |
| Redmi Note 10S | - | MT6768 |
| Poco M3 | - | MT6768 |
| Poco X3 Pro | - | MT6768 |
| Redmi 9A/9C | - | MT6765 |
| Dan semua MTK Xiaomi lainnya | | |

## Project Structure

```
mtk-unbrick/
├── unbrick.sh              # Shell script launcher (main entry point)
├── mtk_unbrick.py          # Standalone Python script
├── mtk_unbrick/            # Package version
│   ├── cli.py              # CLI entry point
│   ├── device.py           # USB device detection
│   ├── scatter.py          # Scatter file parser
│   ├── flasher.py          # Flash engine
│   └── utils.py            # Utilities
├── exploits/
│   ├── kamakiri.py         # Kamakiri2 exploit (V5)
│   ├── heapbait.py         # Heapbait exploit
│   └── carbonara.py        # Carbonara exploit (V5/V6)
├── payloads/               # Binary payloads
├── setup.py
├── requirements.txt
└── README.md
```

## Exploit yang Didukung

| Exploit | Target | Status |
|---------|--------|--------|
| **Kamakiri2** | V5 devices (pre-MT6853) | Working |
| **Heapbait** | V5 devices | Working |
| **Carbonara** | V5/V6 devices | Working |

### Cara Kerja Auth Bypass

```
Normal Flow:
Device → BROM → SLA/DAA Check → Flash (Butuh Auth Dongle)

Dengan Tool:
Device → BROM → Kamakiri2 Exploit → Bypass SLA/DAA → Flash (Tanpa Dongle)
```

## Kontribusi

Contributions welcome! Buka issue atau PR di GitHub.

```bash
git clone https://github.com/naidrahiqa/mtk-unbrick.git
cd mtk-unbrick
# Buat branch baru
git checkout -b feature/fitur-baru
# Commit changes
git commit -m "Add fitur baru"
# Push
git push origin feature/fitur-baru
# Buka PR
```

## Credits

- [mtkclient](https://github.com/bkerler/mtkclient) - B.Kerler (exploit engine)
- [penumbra](https://github.com/shomykohai/penumbra) - shomykohai (Rust MTK tool)
- [kamakiri exploit](https://blog.r0rt1z2.com/posts/dissecting-a-mantis/) - R0rt1z2
- [heapbait exploit](https://github.com/chimera) - chimera team
- [Xiaomi MTK unlock](https://github.com/Jz8Root/xiaomi-hyperos-bootloader-unlock) - Jz8Root

## License

[GPL-3.0](LICENSE) - Free software, open source.

---

<div align="center">

**WARNING: Gunakan tool ini dengan bijak. Author tidak bertanggung jawab atas kerusakan device.**

Made with ❤️ for Xiaomi MTK community

</div>
