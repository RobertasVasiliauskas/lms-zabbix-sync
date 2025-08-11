import json
import logging
from typing import Dict, Any, Optional, Callable
from .buffer import DeviceBuffer
from .zabbix_client import ZabbixAPIClient

logger = logging.getLogger(__name__)


class LMSMessageProcessor:
    def __init__(self, device_buffer: DeviceBuffer, zabbix_api: ZabbixAPIClient) -> None:
        self.device_buffer = device_buffer
        self.zabbix_api = zabbix_api
        self.table_handlers: Dict[str, Callable] = {
            "netdevices": self._process_netdevice,
            "nodes": self._process_node
        }

    @staticmethod
    def ip_to_string(ip_int: int) -> str:
        if ip_int == 0:
            return ""
        return ".".join(str(b) for b in ip_int.to_bytes(4, byteorder="big"))

    def parse_lms_message(self, message_body: str) -> Optional[Dict[str, Any]]:
        try:
            lms_data = json.loads(message_body)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON message: {e}")
            return None

        action = lms_data.get("Action")
        table = lms_data.get("Table")
        payload = json.loads(lms_data.get("Payload", "{}") or "{}")
        payload_previous = json.loads(lms_data.get("PayloadPrevious", "{}") or "{}")

        logger.info(f"Processing {action} for table {table}, ID={lms_data.get('ID')}")

        handler = self.table_handlers.get(table)
        if handler:
            try:
                return handler(action, payload, payload_previous)
            except Exception as e:
                logger.exception(f"Error processing table {table}: {e}")
        else:
            logger.warning(f"Unknown table type: {table}")
        return None

    # --- Private Processing Methods ---

    def _process_netdevice(
        self, action: str, payload: Dict[str, Any], payload_previous: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        device_id = payload.get("id")
        clean_name = payload.get("name", "").lstrip("#")

        if action == "INSERT":
            device_data = {
                "name": clean_name,
                "description": payload.get("description", ""),
                "status": 0 if payload.get("status", 0) == 0 else 1,
                "action": "create"
            }
            if self.device_buffer.add_device(device_id, device_data):
                return self._finalize_device(device_id)
            self.device_buffer.save_state()

        elif action == "UPDATE":
            self._update_netdevice(device_id, clean_name, payload, payload_previous)

        elif action == "DELETE":
            self.device_buffer.remove_device(device_id)
            self.device_buffer.save_state()
        return None

    def _update_netdevice(
        self, device_id: int, clean_name: str, payload: Dict[str, Any], payload_previous: Dict[str, Any]
    ) -> None:
        if not payload_previous:
            logger.warning("No previous payload available for netdevice UPDATE")
            return

        prev_clean_name = payload_previous.get("name", "").lstrip("#")
        host = self.zabbix_api.get_host_by_name(prev_clean_name)

        if host:
            update_data = {
                "host": prev_clean_name,
                "new_host": clean_name,
                "name": clean_name,
                "description": payload.get("description", ""),
                "status": 0 if payload.get("status", 0) == 0 else 1
            }
            if self.zabbix_api.update_host(update_data):
                cached = self.device_buffer.device_info_cache.get(device_id, {})
                cached.update({
                    "name": clean_name,
                    "description": update_data["description"],
                    "status": update_data["status"]
                })
                self.device_buffer.cache_device_info(device_id, cached)
        else:
            for dev_id, data in self.device_buffer.pending_devices.items():
                if data.get("name") == prev_clean_name:
                    data.update({
                        "name": clean_name,
                        "description": payload.get("description", ""),
                        "status": 0 if payload.get("status", 0) == 0 else 1
                    })
                    self.device_buffer.pending_devices[dev_id] = data
                    self.device_buffer.save_state()
                    return
            logger.info(f"Host {prev_clean_name} not found in pending buffer")

    def _process_node(
        self, action: str, payload: Dict[str, Any], payload_previous: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        ip_string = self.ip_to_string(payload.get("ipaddr", 0))
        netdev_id = payload.get("netdev")

        if not netdev_id:
            logger.warning("Node message missing netdev, skipping")
            return None

        if action == "INSERT":
            if self.device_buffer.add_ip_for_device(netdev_id, ip_string):
                return self._finalize_device(netdev_id)

        elif action == "UPDATE":
            self._update_node_ip(netdev_id, ip_string, payload_previous)

        elif action == "DELETE":
            self._delete_node(netdev_id, ip_string)
        return None

    def _update_node_ip(self, netdev_id: int, ip_string: str, payload_previous: Dict[str, Any]) -> None:
        if not payload_previous:
            logger.warning("No previous payload available for node UPDATE")
            return
        prev_ip_string = self.ip_to_string(payload_previous.get("ipaddr", 0))
        host = self.zabbix_api.get_host_by_ip(prev_ip_string)
        if host and self.zabbix_api.update_host({"host": host["host"], "ip": ip_string}):
            cached = self.device_buffer.device_info_cache.get(netdev_id, {})
            cached["ip"] = ip_string
            self.device_buffer.cache_device_info(netdev_id, cached)

    def _delete_node(self, netdev_id: int, ip_string: str) -> None:
        if not ip_string:
            return
        host = self.zabbix_api.get_host_by_ip(ip_string)
        if host:
            self.zabbix_api.delete_host(host["host"])
            self.device_buffer.restore_device_to_pending(netdev_id)

    def _finalize_device(self, device_id: int) -> Optional[Dict[str, Any]]:
        complete_device = self.device_buffer.get_complete_device(device_id)
        if complete_device:
            self.device_buffer.cache_device_info(device_id, complete_device)
            return {
                "action": "create",
                "host": complete_device["name"],
                "name": complete_device["name"],
                "ip": complete_device["ip"],
                "description": complete_device["description"],
                "status": complete_device["status"]
            }
        return None
