import logging
from typing import Dict, Any, Optional
import json
import os

logger = logging.getLogger(__name__)

BUFFER_STATE_FILE = "buffer_state.json"

class DeviceBuffer:
    def __init__(self) -> None:
        self.pending_devices: Dict[int, Dict[str, Any]] = {}
        self.device_ips: Dict[int, str] = {}
        self.device_info_cache: Dict[int, Dict[str, Any]] = {}
        self.load_state()

    @staticmethod
    def _is_device_complete(device: Dict[str, Any]) -> bool:
        return bool(device.get("name") and device.get("ip"))

    def add_device(self, device_id: int, device_data: Dict[str, Any]) -> bool:
        if device_id in self.device_ips:
            device_data["ip"] = self.device_ips[device_id]
        self.pending_devices[device_id] = device_data

        if self._is_device_complete(device_data):
            logger.info(f"Device {device_id} complete with IP {device_data['ip']}")
            return True
        logger.info(f"Device {device_id} buffered (incomplete)")
        return False

    def add_ip_for_device(self, device_id: int, ip: str) -> bool:
        self.device_ips[device_id] = ip
        if device_id in self.pending_devices:
            self.pending_devices[device_id]["ip"] = ip
            if self._is_device_complete(self.pending_devices[device_id]):
                logger.info(f"Device {device_id} complete with IP {ip}")
                return True
        logger.info(f"Device {device_id} IP buffered ({ip})")
        return False

    def get_complete_device(self, device_id: int) -> Optional[Dict[str, Any]]:
        device = self.pending_devices.get(device_id)
        if device and self._is_device_complete(device):
            self.pending_devices.pop(device_id, None)
            self.device_ips.pop(device_id, None)
            return device
        return None

    def remove_device(self, device_id: int) -> None:
        self.pending_devices.pop(device_id, None)
        self.device_ips.pop(device_id, None)
        logger.info(f"Removed device {device_id} from buffer")

    def get_buffer_status(self) -> Dict[str, int]:
        return {
            "pending_devices": len(self.pending_devices),
            "pending_ips": len(self.device_ips)
        }

    def cache_device_info(self, device_id: int, device_data: Dict[str, Any]) -> None:
        self.device_info_cache[device_id] = {
            k: device_data[k] for k in ("name", "description", "status", "ip") if k in device_data
        }

    def restore_device_to_pending(self, device_id: int) -> None:
        if device_id in self.device_info_cache:
            cached = self.device_info_cache[device_id].copy()
            cached.pop("ip", None)
            self.pending_devices[device_id] = cached
            logger.info(f"Restored device {device_id} to pending buffer after deletion.")

    def save_state(self) -> None:
        try:
            state = {
                "pending_devices": self.pending_devices,
                "device_ips": self.device_ips,
                "device_info_cache": self.device_info_cache
            }
            with open(BUFFER_STATE_FILE, "w") as f:
                json.dump(state, f)
            logger.info("Buffer state saved.")
        except Exception as e:
            logger.exception(f"Failed to save buffer state: {e}")

    def load_state(self) -> None:
        if not os.path.exists(BUFFER_STATE_FILE):
            logger.info("No buffer state file found, starting fresh.")
            return
        try:
            with open(BUFFER_STATE_FILE, "r") as f:
                state = json.load(f)
            self.pending_devices = state.get("pending_devices", {})
            self.device_ips = state.get("device_ips", {})
            self.device_info_cache = state.get("device_info_cache", {})
            logger.info("Buffer state loaded.")
        except Exception as e:
            logger.exception(f"Failed to load buffer state: {e}")
