import json
import logging
from typing import Dict, Any, Optional
from .buffer import DeviceBuffer
from .zabbix_client import ZabbixAPIClient

logger = logging.getLogger(__name__)


class LMSMessageProcessor:

    def __init__(self, device_buffer: DeviceBuffer, zabbix_api: ZabbixAPIClient):
        self.device_buffer = device_buffer
        self.zabbix_api = zabbix_api

    @staticmethod
    def ip_to_string(ip_int: int) -> str:
        if ip_int == 0:
            return ""
        ip_bytes = ip_int.to_bytes(4, byteorder='big')
        return ".".join(str(b) for b in ip_bytes)

    def parse_lms_message(self, message_body: str) -> Optional[Dict[str, Any]]:
        try:
            lms_data = json.loads(message_body)
            action = lms_data.get("Action")
            table = lms_data.get("Table")
            payload_str = lms_data.get("Payload", "{}")
            payload_previous_str = lms_data.get("PayloadPrevious", "{}")

            payload = json.loads(payload_str) if payload_str else {}
            payload_previous = json.loads(payload_previous_str) if payload_previous_str else {}

            logger.info(f"Processing {action} action for table {table}, ID: {lms_data.get('ID')}")

            if table == "netdevices":
                return self._process_netdevice(action, payload, payload_previous)
            elif table == "nodes":
                return self._process_node(action, payload, payload_previous)
            else:
                logger.warning(f"Unknown table type: {table}")
                return None

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON message: {e}")
            return None
        except Exception as e:
            logger.error(f"Error parsing LMS message: {e}")
            return None

    def _process_netdevice(self, action: str, payload: Dict[str, Any], payload_previous: Dict[str, Any] = None) -> \
            Optional[Dict[str, Any]]:
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
                        "host": complete_device["name"],
                        "name": complete_device["name"],
                        "ip": complete_device["ip"],
                        "description": complete_device["description"],
                        "status": complete_device["status"]
                    }
            return None

        elif action == "UPDATE":
            if payload_previous:
                previous_name = payload_previous.get("name", "")
                previous_clean_name = previous_name.lstrip("#")
                logger.info(f"Looking for host by previous name: {previous_clean_name}")
                host = self.zabbix_api.get_host_by_name(previous_clean_name)

                print(host)

                if host:
                    update_data = {
                        "host": previous_clean_name,
                        "new_host": clean_name,
                        "name": clean_name,
                        "description": payload.get("description", ""),
                        "status": 0 if payload.get("status", 0) == 0 else 1
                    }
                    logger.info(f"Updating host from '{previous_clean_name}' to '{clean_name}' in Zabbix")
                    if self.zabbix_api.update_host(update_data):
                        cached_device = self.device_buffer.device_info_cache.get(device_id, {})
                        cached_device.update({
                            "name": clean_name,
                            "description": payload.get("description", ""),
                            "status": 0 if payload.get("status", 0) == 0 else 1
                        })
                        self.device_buffer.cache_device_info(device_id, cached_device)
                        logger.info(f"Updated cache for device_id={device_id}: {cached_device}")
                    else:
                        logger.error(f"Failed to update host {previous_clean_name}")
                else:
                    logger.warning(f"Host {previous_clean_name} not found in Zabbix for update.")
            else:
                logger.warning("No previous payload available for netdevice UPDATE")
            return None

        elif action == "DELETE":
            self.device_buffer.remove_device(device_id)
            return None

        return None

    def _process_node(self, action: str, payload: Dict[str, Any], payload_previous: Dict[str, Any] = None) -> Optional[
        Dict[str, Any]]:
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
                        "host": complete_device["name"],
                        "name": complete_device["name"],
                        "ip": complete_device["ip"],
                        "description": complete_device["description"],
                        "status": complete_device["status"]
                    }
            return None

        elif action == "UPDATE":
            if payload_previous:
                previous_ip_addr = payload_previous.get("ipaddr", 0)
                previous_ip_string = self.ip_to_string(previous_ip_addr)

                logger.info(f"Looking for host by previous IP: {previous_ip_string}")
                host = self.zabbix_api.get_host_by_ip(previous_ip_string)

                if host:
                    update_data = {
                        "host": host["host"],  # Keep existing hostname
                        "ip": ip_string  # Update to new IP
                    }
                    logger.info(f"Updating host {host['host']} IP from {previous_ip_string} to {ip_string}")

                    if self.zabbix_api.update_host(update_data):
                        cached_device = self.device_buffer.device_info_cache.get(netdev_id, {})
                        cached_device["ip"] = ip_string
                        self.device_buffer.cache_device_info(netdev_id, cached_device)
                        logger.info(f"Updated cache for device_id={netdev_id} with new IP: {ip_string}")
                    else:
                        logger.error(f"Failed to update host {host['host']} IP")
                else:
                    logger.warning(f"No host found with previous IP {previous_ip_string} for update.")
            else:
                logger.warning("No previous payload available for node UPDATE")
            return None

        elif action == "DELETE":
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
