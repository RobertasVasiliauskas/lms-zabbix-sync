import logging
from typing import Dict, Any, Optional, List
from pyzabbix import ZabbixAPI
from .utility import get_city_by_zip

logger = logging.getLogger(__name__)

LAYER_TO_NAME = {"c": "Core", "d": "Distribution", "a": "Access"}
TYPE_TO_NAME = {
    "rtr": "Router", "ctr": "Core Router", "etr": "Edge Router", "sw": "Switch",
    "swm": "Switch Management", "ap": "Access Point", "cam": "Camera", "gsm": "GSM Gateway",
    "ptp": "point-to-point", "ptmp": "point-to-multipoint", "olt": "OLT", "onu": "ONU",
    "ont": "ONT", "stb": "STB", "nvr": "NVR", "nas": "NAS", "cld": "Cloud", "srv": "Server", "vm": "Virtual Machine"
}


class ZabbixAPIClient:
    def __init__(self, url: str, username: str, password: str, host_group_id: str = "1") -> None:
        self.url = url.rstrip("/")
        self.username = username
        self.password = password
        self.host_group_id = host_group_id
        self.api: Optional[ZabbixAPI] = None

    def connect(self) -> bool:
        try:
            self.api = ZabbixAPI(self.url)
            self.api.login(self.username, self.password)
            if not self._verify_host_group():
                self._find_available_host_group()
            return True
        except Exception as e:
            logger.exception(f"Failed to connect to Zabbix API: {e}")
            return False

    def _verify_host_group(self) -> bool:
        try:
            groups = self.api.hostgroup.get(groupids=[self.host_group_id])
            return bool(groups)
        except Exception as e:
            logger.exception(f"Error verifying host group: {e}")
            return False

    def _find_available_host_group(self) -> bool:
        try:
            groups = self.api.hostgroup.get()
            if groups:
                self.host_group_id = groups[0]['groupid']
                return True
            return False
        except Exception as e:
            logger.exception(f"Error finding available host group: {e}")
            return False

    def get_host_by_name(self, hostname: str) -> Optional[Dict[str, Any]]:
        try:
            hosts = self.api.host.get(filter={"host": hostname})
            return hosts[0] if hosts else None
        except Exception as e:
            logger.exception(f"Error getting host {hostname}: {e}")
            return None

    def get_host_by_ip(self, ip: str) -> Optional[Dict[str, Any]]:
        try:
            hosts = self.api.host.get()
            for host in hosts:
                if any(iface.get("ip") == ip for iface in self.api.hostinterface.get(hostids=host["hostid"])):
                    return host
            return None
        except Exception as e:
            logger.exception(f"Error getting host by IP {ip}: {e}")
            return None

    def _build_interface(self, ip: str, port: str = "10050") -> Dict[str, Any]:
        return {"type": 1, "main": 1, "useip": 1, "ip": ip, "dns": "", "port": port}

    def create_host(self, host_data: Dict[str, Any]) -> Optional[str]:
        try:
            params = {
                "host": host_data["host"],
                "name": host_data.get("name", host_data["host"]),
                "description": host_data.get("description", ""),
                "interfaces": [self._build_interface(host_data.get("ip", ""))],
                "groups": [{"groupid": self.host_group_id}],
                "templates": host_data.get("templates", []),
                "macros": host_data.get("macros", []),
                "tags": self.find_tags_to_apply(host_data["host"])
            }
            result = self.api.host.create(**params)
            if result and 'hostids' in result:
                return result['hostids'][0]
        except Exception as e:
            logger.exception(f"Error creating host {host_data.get('host')}: {e}")
        return None

    def update_host(self, host_data: Dict[str, Any]) -> bool:
        try:
            host = self.get_host_by_name(host_data["host"])
            if not host:
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
                    self.api.hostinterface.update(**{
                        **self._build_interface(host_data["ip"], port="161"),
                        "interfaceid": interfaces[0]["interfaceid"]
                    })
            self.api.host.update(**update_params, tags=self.find_tags_to_apply(update_params["name"]))
            return True
        except Exception as e:
            logger.exception(f"Error updating host {host_data.get('host')}: {e}")
            return False

    def delete_host(self, hostname: str) -> bool:
        try:
            host = self.get_host_by_name(hostname)
            if not host:
                return False
            self.api.host.delete(host["hostid"])
            return True
        except Exception as e:
            logger.exception(f"Error deleting host {hostname}: {e}")
            return False

    @staticmethod
    def find_tags_to_apply(hostname: str) -> List[Dict[str, str]]:
        try:
            parts = hostname.split("_")
            if len(parts) < 4:
                return []
            zipcode, layer_code, device_code = parts[1], parts[2], parts[3]
            return [
                {"tag": "city", "value": get_city_by_zip(zipcode)},
                {"tag": "layer", "value": LAYER_TO_NAME.get(layer_code, layer_code)},
                {"tag": "type", "value": TYPE_TO_NAME.get(device_code, device_code)},
            ]
        except Exception as e:
            logger.exception(f"Error finding tags for {hostname}: {e}")
            return []
