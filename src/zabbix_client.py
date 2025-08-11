import logging
from typing import Dict, Any, Optional
from pyzabbix import ZabbixAPI

from .utility import get_city_by_zip


logger = logging.getLogger(__name__)

LAYER_TO_NAME = {
    "c": "Core",
    "d": "Distribution",
    "a": "Access",
}

TYPE_TO_NAME = {
    "rtr": "Router",
    "ctr": "Core Router",
    "etr": "Edge Router",
    "sw": "Switch",
    "swm": "Switch Management",
    "ap": "Access Point",
    "cam": "Camera",
    "gsm": "GSM Gateway",
    "ptp": "point-to-point",
    "ptmp": "point-to-multipoint",
    "olt": "OLT",
    "onu": "ONU",
    "ont": "ONT",
    "stb": "STB",
    "nvr": "NVR",
    "nas": "NAS",
    "cld": "Cloud",
    "srv": "Server",
    "vm": "Virtual Machine",
}

class ZabbixAPIClient:

    def __init__(self, url: str, username: str, password: str, host_group_id: str = "1"):
        self.url = url.rstrip('/')
        self.username = username
        self.password = password
        self.host_group_id = host_group_id
        self.api = None

    def connect(self) -> bool:
        try:
            self.api = ZabbixAPI(self.url)
            self.api.login(self.username, self.password)
            logger.info("Successfully connected to Zabbix API")

            if not self._verify_host_group():
                logger.warning(f"Host group {self.host_group_id} not found, will try to use first available group")
                self._find_available_host_group()

            return True
        except Exception as e:
            logger.error(f"Failed to connect to Zabbix API: {e}")
            return False

    def _verify_host_group(self) -> bool:
        try:
            groups = self.api.hostgroup.get(groupids=[self.host_group_id])
            if groups:
                logger.info(f"Using host group: {groups[0]['name']} (ID: {self.host_group_id})")
                return True
            else:
                logger.warning(f"Host group {self.host_group_id} not found")
                return False
        except Exception as e:
            logger.error(f"Error verifying host group: {e}")
            return False

    def _find_available_host_group(self) -> bool:
        try:
            groups = self.api.hostgroup.get()
            if groups:
                self.host_group_id = groups[0]['groupid']
                logger.info(f"Using first available host group: {groups[0]['name']} (ID: {self.host_group_id})")
                return True
            else:
                logger.error("No host groups found in Zabbix")
                return False
        except Exception as e:
            logger.error(f"Error finding available host group: {e}")
            return False

    def get_host_by_name(self, hostname: str) -> Optional[Dict[str, Any]]:
        try:
            hosts = self.api.host.get(filter={"host": hostname})
            return hosts[0] if hosts else None
        except Exception as e:
            logger.error(f"Error getting host {hostname}: {e}")
            return None

    def get_host_by_ip(self, ip: str) -> Optional[Dict[str, Any]]:
        try:
            hosts = self.api.host.get()
            for host in hosts:
                interfaces = self.api.hostinterface.get(hostids=host["hostid"])
                for iface in interfaces:
                    if iface.get("ip") == ip:
                        return host
            return None
        except Exception as e:
            logger.error(f"Error getting host by IP {ip}: {e}")
            return None

    def create_host(self, host_data: Dict[str, Any]) -> Optional[str]:

        print(host_data)

        try:
            interface = {
                "type": 1,
                "main": 1,
                "useip": 1,
                "ip": host_data.get("ip", ""),
                "dns": "",
                "port": "10050"
            }

            groups = [{"groupid": self.host_group_id}]

            templates = host_data.get("templates", [])

            macros = host_data.get("macros", [])

            tags = self.find_tags_to_apply(host_data["host"])

            host_params = {
                "host": host_data["host"],
                "name": host_data.get("name", host_data["host"]),
                "description": host_data.get("description", ""),
                "interfaces": [interface],
                "groups": groups,
                "templates": templates,
                "macros": macros,
                "tags": tags
            }

            logger.info(f"Creating host with parameters: {host_params}")
            result = self.api.host.create(**host_params)

            if result and 'hostids' in result:
                host_id = result['hostids'][0]
                logger.info(f"Host created successfully: {host_data['host']} (ID: {host_id})")
                return host_id
            else:
                logger.error(f"Failed to create host: {host_data['host']}")
                return None

        except Exception as e:
            logger.error(f"Error creating host {host_data.get('host', 'unknown')}: {e}")
            return None

    def update_host(self, host_data: Dict[str, Any]) -> bool:
        try:
            host = self.get_host_by_name(host_data["host"])
            if not host:
                logger.error(f"Host not found for update: {host_data['host']}")
                return False

            update_params = {
                "hostid": host["hostid"],
                "name": host_data.get("name", host_data["host"]),
                "description": host_data.get("description", ""),
                "status": host_data.get("status", 0)
            }

            if "ip" in host_data:
                interfaces = self.api.hostinterface.get(hostids=host["hostid"])
                if interfaces:
                    interface = interfaces[0]
                    interface_params = {
                        "interfaceid": interface["interfaceid"],
                        "type": 1,
                        "main": 1,
                        "useip": 1,
                        "ip": host_data["ip"],
                        "dns": "",
                        "port": "161"
                    }
                    self.api.hostinterface.update(**interface_params)

            result = self.api.host.update(**update_params, tags=self.find_tags_to_apply(update_params["name"]))

            if result:
                logger.info(f"Host updated successfully: {host_data['host']}")
                return True
            else:
                logger.error(f"Failed to update host: {host_data['host']}")
                return False

        except Exception as e:
            logger.error(f"Error updating host {host_data.get('host', 'unknown')}: {e}")
            return False

    def delete_host(self, hostname: str) -> bool:
        try:
            host = self.get_host_by_name(hostname)
            if not host:
                logger.error(f"Host not found for deletion: {hostname}")
                return False

            result = self.api.host.delete(host["hostid"])

            if result:
                logger.info(f"Host deleted successfully: {hostname}")
                return True
            else:
                logger.error(f"Failed to delete host: {hostname}")
                return False

        except Exception as e:
            logger.error(f"Error deleting host {hostname}: {e}")
            return False

    @staticmethod
    def find_tags_to_apply(hostname: str) -> list[dict[str, str]]:
        tags_to_apply = []
        try:
            zipcode = hostname.split("_")[1]
            city = get_city_by_zip(zipcode)
            tags_to_apply.append({"tag": "city", "value": city})

            layer = hostname.split("_")[2]
            tags_to_apply.append({"tag": "layer", "value": LAYER_TO_NAME.get(layer, layer)})

            device_type = hostname.split("_")[3]
            tags_to_apply.append({"tag": "type", "value": TYPE_TO_NAME.get(device_type, device_type)})

            return tags_to_apply
        except Exception as e:
            logger.error(f"Error finding tags to apply for host {hostname}: {e}")
            return []
