import logging
from typing import Dict, Any, Optional
import json
import os

logger = logging.getLogger(__name__)

BUFFER_STATE_FILE = "buffer_state.json"

class DeviceBuffer:

    def __init__(self):
        self.pending_devices = {}
        self.device_ips = {}
        self.device_info_cache = {}
        self.load_state()

    def add_device(self, device_id: str, device_data: Dict[str, Any]) -> bool:
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
        device_id = str(device_id)
        self.device_ips[device_id] = ip

        if device_id in self.pending_devices:
            print("dupa 2")
            self.pending_devices[device_id]["ip"] = ip
            device = self.pending_devices[device_id]
            if device.get("name") and device.get("ip"):
                logger.info(f"Device {device_id} is now complete with IP: {device['ip']}")
                return True

        logger.info(f"Device {device_id} IP buffered (ip={ip})")
        return False

    def get_complete_device(self, device_id: int) -> Optional[Dict[str, Any]]:
        device_id = str(device_id)
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
        device_id = str(device_id)
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

    def restore_device_to_pending(self, host: Dict[str, Any]):
        device_id = str(host.get("host").split("_")[4])
        self.add_device(device_id, {'name': host.get("name"), 'description': host.get("description"), 'status': host.get("status")})
        logger.info(f"Restored device {device_id} to pending buffer after node deletion.")

    def save_state(self):
        try:
            state = {
                "pending_devices": self.pending_devices,
            }
            with open(BUFFER_STATE_FILE, "w") as f:
                json.dump(state, f)
            logger.info("Buffer state saved to disk.")
        except Exception as e:
            logger.error(f"Failed to save buffer state: {e}")

    def load_state(self):
        if os.path.exists(BUFFER_STATE_FILE):
            try:
                with open(BUFFER_STATE_FILE, "r") as f:
                    state = json.load(f)
                self.pending_devices = state.get("pending_devices", {})
                self.device_ips = state.get("device_ips", {})
                self.device_info_cache = state.get("device_info_cache", {})
                logger.info("Buffer state loaded from disk.")
            except Exception as e:
                logger.error(f"Failed to load buffer state: {e}")
        else:
            logger.info("No buffer state file found, starting fresh.")
