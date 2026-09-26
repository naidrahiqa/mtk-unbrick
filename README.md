<div align="center">

# MTK Unbrick

**One-click unbrick tool untuk Xiaomi MTK devices via BROM mode**

Backend: [bkerler/mtkclient](https://github.com/bkerler/mtkclient) — auth bypass (SLA/DAA/SBC), DA upload, DRAM setup.

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](http://www.gnu.org/licenses/gpl-3.0)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Linux](https://img.shields.io/badge/platform-linux%20%7C%20windows-lightgreen.svg)]()

</div>

---

## Fitur

- **Menu interaktif** — jalankan tanpa argumen, tinggal pilih angka (Linux & Windows)
- **Flash folder ROM** — map file `*.img` ke partisi via GPT device (scatter **tidak** wajib)
- **Auto A/B** — `boot.img` otomatis ke `boot_a` + `boot_b` (atau `--slot a|b`)
- **Auto `--preloader`** — preloader di folder ROM dipakai otomatis buat DRAM setup
- **Safety guard** — `preloader`/`lk`/`nvram`/`seccfg` dll tidak di-flash tanpa `--force`; preloader **tidak pernah** di-flash, hanya helper
- **Backup** — dump partisi kritis (`lk`, `seccfg`, `nvram`, ...) sekali jalan
- **Read / erase / reset** partisi individual

## Instalasi

### Linux

```bash
# 1. mtkclient (backend) + deps-nya
git clone https://github.com/bkerler/mtkclient ~/mtkclient
pip install -r ~/mtkclient/requirements.txt   # atau: pip3 install --user -r ...

# 2. tool ini
git clone https://github.com/naidrahiqa/mtk-unbrick.git
cd mtk-unbrick
chmod +x unbrick.sh

# 3. USB permission sekali saja (tanpa ini perlu sudo terus)
sudo cp 50-mtkclient.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger
```

### Windows

```powershell
# 1. Install Python 3.8+ (centang "Add python.exe to PATH")
# 2. mtkclient (backend)
git clone https://github.com/bkerler/mtkclient %USERPROFILE%\mtkclient
pip install -r %USERPROFILE%\mtkclient\requirements.txt

# 3. tool ini
git clone https://github.com/naidrahiqa/mtk-unbrick.git
```

> **Windows:** install driver MediaTek Preloader / DA USB bila device tidak terdeteksi
> (biasanya otomatis kalau pernah pakai SP Flash Tool). Firewall/antivirus
> kadang perlu diizinkan untuk `python.exe`.

mtkclient dicari otomatis di `./mtkclient/`, `../mtkclient/`, `~/mtkclient/`
(`%USERPROFILE%\mtkclient` di Windows), atau lewat `--mtkclient /path/to/mtk.py`
/ env `MTKCLIENT`.

## Pemakaian

### Menu interaktif (recommended)

```
Linux   : ./unbrick.sh            (atau: python3 mtk_unbrick.py)
Windows : unbrick.bat             (double-click juga bisa)
```

Pilih menu → masukkan folder ROM → ikuti konfirmasi.

### Command line

```bash
# Info device + tabel partisi (tes koneksi BROM)
./unbrick.sh info

# Flash semua image di folder ROM (konfirmasi dulu)
./unbrick.sh flash ~/Downloads/miui_SELENEGlobal_V14.0.7.0

# Tanpa konfirmasi, skip userdata, slot A saja
python3 mtk_unbrick.py flash ./rom -y --skip-userdata --slot a

# Backup partisi kritis (sebelum utak-atik!)
python3 mtk_unbrick.py backup ./backup

# Read / erase satu partisi
python3 mtk_unbrick.py read lk_a ./lk_a_backup.img
python3 mtk_unbrick.py erase userdata
```

Windows: ganti `./unbrick.sh` dengan `unbrick.bat` atau `py -3 mtk_unbrick.py`.

### Cara masuk BROM mode

1. Matikan HP (tahan power ~10 detik)
2. Tahan **Vol+ + Vol-**
3. Colok USB ke PC (kabel data, port langsung, jangan hub)
4. mtkclient auto-detect `0e8d:xxxx` dan bypass auth

### Troubleshooting

| Error | Solusi |
|---|---|
| `DRAM setup failed: unpack requires a buffer of 12 bytes` | Kasih `--preloader preloader.img` (auto kalau file ada di folder ROM) |
| `mtkclient not found` | Clone bkerler/mtkclient atau set `--mtkclient` |
| Device not found (Linux) | Cek `lsusb`; pasang udev rule / jalankan dengan `sudo` |
| Device not found (Windows) | Cek Device Manager, install driver MediaTek Preloader |
| Gagal di tengah flashing | Cabut → tahan Vol+ + Vol- → colok → ulangi partisi yang gagal |
| `Permission denied` /libusb | Linux: pakai udev rule atau `sudo` |

## Peringatan

- **Jangan flash `preloader`/`lk`/`nvram`/`nvdata`** tanpa gambaran jelas — bisa hard brick / hilang IMEI
- Backup dulu (`backup`) sebelum flash apa pun
- Tool ini sengaja **tidak** menyentuh partisi berbahaya tanpa `--force`

## Lisensi

GPL v3 — lihat [LICENSE](LICENSE).
