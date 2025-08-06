"""
LMS message processor for handling database trigger messages
"""

import json
import logging
from typing import Dict, Any, Optional
from .buffer import DeviceBuffer
from .zabbix_client import ZabbixAPIClient

logger = logging.getLogger(__name__)


class LMSMessageProcessor:
    """Processes LMS database trigger messages."""

    def __init__(self, device_buffer: DeviceBuffer, zabbix_api: ZabbixAPIClient):
        self.device_buffer = device_buffer
        self.zabbix_api = zabbix_api

    @staticmethod
    def ip_to_string(ip_int: int) -> str:
        """Convert integer IP to string format."""
        if ip_int == 0:
            return ""
        ip_bytes = ip_int.to_bytes(4, byteorder='big')
        return ".".join(str(b) for b in ip_bytes)

    def parse_lms_message(self, message_body: str) -> Optional[Dict[str, Any]]:
        """Parse LMS message and route to appropriate processor."""
        try:
            lms_data = json.loads(message_body)
            action = lms_data.get("Action")
            table = lms_data.get("Table")
            payload_str = lms_data.get("Payload", "{}")
            payload = json.loads(payload_str) if payload_str else {}

            logger.info(f"Processing {action} action for table {table}, ID: {lms_data.get('ID')}")

            if table == "netdevices":
                return self._process_netdevice(action, payload)
            elif table == "nodes":
                return self._process_node(action, payload)
            else:
                logger.warning(f"Unknown table type: {table}")
                return None

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON message: {e}")
            return None
        except Exception as e:
            logger.error(f"Error parsing LMS message: {e}")
            return None

    def _process_netdevice(self, action: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process netdevice table messages."""
        device_id = payload.get("id")
        device_name = payload.get("name", "")
        clean_name = device_name.lstrip("#")

        if action == "INSERT":
            device_data = {
                "name": clean_name,
                "description": payload.get("description", ""),
                "status": 0 if payload.get("status", 0) == 0 else 1,
                "action": "create"
            }

            if self.device_buffer.add_device(device_id, device_data):
                complete_device = self.device_buffer.get_complete_device(device_id)
                if complete_device:
                    logger.info(f"Caching device info for device_id={device_id}: {complete_device}")
                    self.device_buffer.cache_device_info(device_id, complete_device)
                    return {
                        "action": "create",
                        "host": f"device-{device_id}",
                        "name": complete_device["name"],
                        "ip": complete_device["ip"],
                        "description": complete_device["description"],
                        "status": complete_device["status"]
                    }
            return None

        elif action == "UPDATE":
            host_name = f"device-{device_id}"
            host = self.zabbix_api.get_host_by_name(host_name)

            if host:
                update_data = {
                    "host": host_name,
                    "name": clean_name,
                    "description": payload.get("description", ""),
                    "status": 0 if payload.get("status", 0) == 0 else 1
                }
                logger.info(f"Updating host {host_name} in Zabbix with info: {update_data}")
                self.zabbix_api.update_host(update_data)
                logger.info(f"Caching device info for device_id={device_id}: {update_data}")
                self.device_buffer.cache_device_info(device_id, update_data)
            else:
                logger.warning(f"Host {host_name} not found in Zabbix for update.")
            return None

        elif action == "DELETE":
            self.device_buffer.remove_device(device_id)
            return None

        return None

    def _process_node(self, action: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process node table messages."""
        node_id = payload.get("id")
        ip_addr = payload.get("ipaddr", 0)
        netdev_id = payload.get("netdev")
        ip_string = self.ip_to_string(ip_addr)

        if not netdev_id:
            logger.warning("Node message missing netdev, skipping")
            return None

        if action == "INSERT":
            if self.device_buffer.add_ip_for_device(netdev_id, ip_string):
                complete_device = self.device_buffer.get_complete_device(netdev_id)
                if complete_device:
                    logger.info(f"Caching device info for device_id={netdev_id}: {complete_device}")
                    self.device_buffer.cache_device_info(netdev_id, complete_device)
                    return {
                        "action": "create",
                        "host": f"device-{netdev_id}",
                        "name": complete_device["name"],
                        "ip": complete_device["ip"],
                        "description": complete_device["description"],
                        "status": complete_device["status"]
                    }
            return None

        elif action == "UPDATE":
            host_name = f"device-{netdev_id}"
            host = self.zabbix_api.get_host_by_name(host_name)

            if host:
                update_data = {
                    "host": host_name,
                    "ip": ip_string
                }
                logger.info(f"Updating host {host_name} IP in Zabbix to: {ip_string}")
                self.zabbix_api.update_host(update_data)
            else:
                logger.warning(f"Host {host_name} not found in Zabbix for IP update.")
            return None

        elif action == "DELETE":
            # Find and delete host in Zabbix by IP
            if ip_string:
                host = self.zabbix_api.get_host_by_ip(ip_string)
                if host:
                    logger.info(f"Deleting host {host['host']} from Zabbix by IP {ip_string}")
                    self.zabbix_api.delete_host(host["host"])
                    logger.info(f"device_info_cache before restore: {self.device_buffer.device_info_cache}")
                    logger.info(f"Restoring device_id={netdev_id} to pending buffer after node deletion.")
                    self.device_buffer.restore_device_to_pending(netdev_id)
                else:
                    logger.warning(f"No host found in Zabbix with IP {ip_string} for deletion.")
            return None

        return None
