"""MTK device detection and USB communication"""
import struct
import logging
import time
from enum import Enum
from typing import Optional, Tuple

try:
    import usb.core
    import usb.util
except ImportError:
    usb = None

logger = logging.getLogger(__name__)

# MTK USB IDs
MTK_VID = 0x0E8D

# Known MTK PIDs
BROM_PIDS = [0x0003, 0x0023, 0x0033, 0x0043, 0x0053, 0x0135, 0x0136, 0x01A3, 0x01A5]
PRELOADER_PIDS = [0x0001, 0x0021, 0x0031, 0x0041, 0x0051, 0x0133, 0x0134, 0x01A1, 0x01A2]
DA_PIDS = [0x0005, 0x0025, 0x0035, 0x0045, 0x0055, 0x0137, 0x0138, 0x01A7, 0x01A8]

# Additional PIDs for specific devices
XIAOMI_PIDS = [0x0003, 0x0013, 0x0023, 0x0033, 0x0043, 0x0053, 0x0135, 0x0136]


class DeviceMode(Enum):
    UNKNOWN = "unknown"
    BROM = "brom"
    PRELOADER = "preloader"
    DA = "da"
    FASTBOOT = "fastboot"
    RECOVERY = "recovery"


@dataclass
class DeviceInfo:
    vid: int
    pid: int
    mode: DeviceMode
    hw_code: Optional[int] = None
    hw_ver: Optional[int] = None
    sw_ver: Optional[int] = None
    me_id: Optional[str] = None
    soc_id: Optional[str] = None
    chipconfig: Optional[dict] = None
    target_config: Optional[int] = None
    sbc_enabled: bool = False
    sla_enabled: bool = False
    daa_enabled: bool = False


from dataclasses import dataclass


class MTKDevice:
    """MTK USB device handler"""

    def __init__(self):
        self.device = None
        self.endpoint_in = None
        self.endpoint_out = None
        self.info: Optional[DeviceInfo] = None
        self._detected_mode = DeviceMode.UNKNOWN

    def detect(self, timeout: float = 5.0) -> Optional[DeviceInfo]:
        """Detect MTK device and determine its mode"""
        if usb is None:
            raise ImportError("pyusb not installed. Run: pip install pyusb")

        # Scan for MTK devices
        for pid in BROM_PIDS:
            dev = usb.core.find(idVendor=MTK_VID, idProduct=pid)
            if dev:
                self.device = dev
                self._detected_mode = DeviceMode.BROM
                return self._init_device(pid, DeviceMode.BROM)

        for pid in PRELOADER_PIDS:
            dev = usb.core.find(idVendor=MTK_VID, idProduct=pid)
            if dev:
                self.device = dev
                self._detected_mode = DeviceMode.PRELOADER
                return self._init_device(pid, DeviceMode.PRELOADER)

        for pid in DA_PIDS:
            dev = usb.core.find(idVendor=MTK_VID, idProduct=pid)
            if dev:
                self.device = dev
                self._detected_mode = DeviceMode.DA
                return self._init_device(pid, DeviceMode.DA)

        # Try generic MTK PID
        for pid in range(0x0001, 0x01FF):
            dev = usb.core.find(idVendor=MTK_VID, idProduct=pid)
            if dev:
                self.device = dev
                mode = self._guess_mode(pid)
                return self._init_device(pid, mode)

        return None

    def _guess_mode(self, pid: int) -> DeviceMode:
        if pid in BROM_PIDS:
            return DeviceMode.BROM
        elif pid in PRELOADER_PIDS:
            return DeviceMode.PRELOADER
        elif pid in DA_PIDS:
            return DeviceMode.DA
        return DeviceMode.UNKNOWN

    def _init_device(self, pid: int, mode: DeviceMode) -> DeviceInfo:
        try:
            if self.device.is_kernel_driver_active(0):
                self.device.detach_kernel_driver(0)
        except (usb.core.USBError, NotImplementedError):
            pass

        try:
            usb.util.claim_interface(self.device, 0)
        except usb.core.USBError:
            pass

        cfg = self.device.get_active_configuration()
        intf = cfg[(0, 0)]

        self.endpoint_in = usb.util.find_descriptor(
            intf, custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN
        )
        self.endpoint_out = usb.util.find_descriptor(
            intf, custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT
        )

        self.info = DeviceInfo(
            vid=MTK_VID,
            pid=pid,
            mode=mode,
        )

        logger.info(f"Device detected: VID={hex(MTK_VID)} PID={hex(pid)} Mode={mode.value}")
        return self.info

    def read(self, length: int = 512, timeout: int = 5000) -> bytes:
        """Read data from device"""
        if not self.endpoint_in:
            raise RuntimeError("Device not initialized")
        return bytes(self.endpoint_in.read(length, timeout))

    def write(self, data: bytes, timeout: int = 5000):
        """Write data to device"""
        if not self.endpoint_out:
            raise RuntimeError("Device not initialized")
        self.endpoint_out.write(data, timeout)

    def ctrl_transfer(self, bmRequestType: int, bRequest: int, wValue: int, wIndex: int, data_or_length=None, timeout: int = 5000):
        """USB control transfer"""
        if self.device is None:
            raise RuntimeError("Device not initialized")
        return self.device.ctrl_transfer(bmRequestType, bRequest, wValue, wIndex, data_or_length, timeout)

    def close(self):
        """Close device connection"""
        if self.device:
            try:
                usb.util.dispose_resources(self.device)
            except Exception:
                pass
            self.device = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def wait_for_device(mode: DeviceMode = DeviceMode.BROM, timeout: float = 30.0) -> Optional[MTKDevice]:
    """Wait for MTK device to appear"""
    logger.info(f"Waiting for MTK device in {mode.value} mode...")
    start = time.time()

    while time.time() - start < timeout:
        dev = MTKDevice()
        info = dev.detect(timeout=1.0)
        if info and (mode == DeviceMode.UNKNOWN or info.mode == mode):
            return dev
        time.sleep(0.5)

    logger.warning("Timeout waiting for device")
    return None
