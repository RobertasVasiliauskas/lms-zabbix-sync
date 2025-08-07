import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class DeviceBuffer:

    def __init__(self):
        self.pending_devices = {}
        self.device_ips = {}
        self.device_info_cache = {}

    def add_device(self, device_id: int, device_data: Dict[str, Any]) -> bool:
        self.pending_devices[device_id] = device_data

        if device_id in self.device_ips:
            self.pending_devices[device_id]["ip"] = self.device_ips[device_id]

        device = self.pending_devices[device_id]
        if device.get("name") and device.get("ip"):
            logger.info(f"Device {device_id} is now complete with IP: {device['ip']}")
            return True
        else:
            logger.info(f"Device {device_id} buffered (incomplete: name={device.get('name')}, ip={device.get('ip')})")
            return False

    def add_ip_for_device(self, device_id: int, ip: str) -> bool:
        self.device_ips[device_id] = ip

        if device_id in self.pending_devices:
            self.pending_devices[device_id]["ip"] = ip
            device = self.pending_devices[device_id]
            if device.get("name") and device.get("ip"):
                logger.info(f"Device {device_id} is now complete with IP: {device['ip']}")
                return True

        logger.info(f"Device {device_id} IP buffered (ip={ip})")
        return False

    def get_complete_device(self, device_id: int) -> Optional[Dict[str, Any]]:
        if device_id in self.pending_devices:
            device = self.pending_devices[device_id]
            if device.get("name") and device.get("ip"):
                # Remove from buffer after use
                del self.pending_devices[device_id]
                if device_id in self.device_ips:
                    del self.device_ips[device_id]
                return device
        return None

    def remove_device(self, device_id: int):
        if device_id in self.pending_devices:
            del self.pending_devices[device_id]
        if device_id in self.device_ips:
            del self.device_ips[device_id]
        logger.info(f"Removed device {device_id} from buffer")

    def get_buffer_status(self) -> Dict[str, int]:
        return {
            "pending_devices": len(self.pending_devices),
            "pending_ips": len(self.device_ips)
        }

    def cache_device_info(self, device_id: int, device_data: Dict[str, Any]):
        self.device_info_cache[device_id] = {
            k: device_data[k] for k in ("name", "description", "status") if k in device_data
        }

    def restore_device_to_pending(self, device_id: int):
        if device_id in self.device_info_cache:
            cached = self.device_info_cache[device_id].copy()
            cached.pop("ip", None)
            self.pending_devices[device_id] = cached
            logger.info(f"Restored device {device_id} to pending buffer after node deletion.")
