"""
Device buffer for managing incomplete device data
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class DeviceBuffer:
    """Buffers device and node information until all required data is available."""

    def __init__(self):
        self.pending_devices = {}  # device_id -> device_data (from netdevices)
        self.device_ips = {}  # device_id -> ip (from nodes)
        self.device_info_cache = {}  # device_id -> last known info (name, desc, status)

    def add_device(self, device_id: int, device_data: Dict[str, Any]) -> bool:
        """Add or update device info from netdevices. Returns True if device is ready for Zabbix."""
        self.pending_devices[device_id] = device_data

        # Check if we already have an IP for this device
        if device_id in self.device_ips:
            self.pending_devices[device_id]["ip"] = self.device_ips[device_id]

        # Ready if we have both name and ip
        device = self.pending_devices[device_id]
        if device.get("name") and device.get("ip"):
            logger.info(f"Device {device_id} is now complete with IP: {device['ip']}")
            return True
        else:
            logger.info(f"Device {device_id} buffered (incomplete: name={device.get('name')}, ip={device.get('ip')})")
            return False

    def add_ip_for_device(self, device_id: int, ip: str) -> bool:
        """Add or update IP for a device from nodes. Returns True if device is ready for Zabbix."""
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
        """Get complete device data and remove from buffer."""
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
        """Remove device from buffer."""
        if device_id in self.pending_devices:
            del self.pending_devices[device_id]
        if device_id in self.device_ips:
            del self.device_ips[device_id]
        logger.info(f"Removed device {device_id} from buffer")

    def get_buffer_status(self) -> Dict[str, int]:
        """Get current buffer status."""
        return {
            "pending_devices": len(self.pending_devices),
            "pending_ips": len(self.device_ips)
        }

    def cache_device_info(self, device_id: int, device_data: Dict[str, Any]):
        """Cache device information."""
        self.device_info_cache[device_id] = {
            k: device_data[k] for k in ("name", "description", "status") if k in device_data
        }

    def restore_device_to_pending(self, device_id: int):
        """Restore device to pending buffer from cache."""
        if device_id in self.device_info_cache:
            cached = self.device_info_cache[device_id].copy()
            cached.pop("ip", None)
            self.pending_devices[device_id] = cached
            logger.info(f"Restored device {device_id} to pending buffer after node deletion.")
