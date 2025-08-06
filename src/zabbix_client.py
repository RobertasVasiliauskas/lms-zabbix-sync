"""
Zabbix API client for managing hosts
"""

import logging
from typing import Dict, Any, Optional
from pyzabbix import ZabbixAPI

logger = logging.getLogger(__name__)


class ZabbixAPIClient:
    """Zabbix API client using py-zabbix library."""

    def __init__(self, url: str, username: str, password: str, host_group_id: str = "1"):
        self.url = url.rstrip('/')
        self.username = username
        self.password = password
        self.host_group_id = host_group_id
        self.api = None

    def connect(self) -> bool:
        """Connect to Zabbix API."""
        try:
            self.api = ZabbixAPI(self.url)
            self.api.login(self.username, self.password)
            logger.info("Successfully connected to Zabbix API")

            # Verify host group exists
            if not self._verify_host_group():
                logger.warning(f"Host group {self.host_group_id} not found, will try to use first available group")
                self._find_available_host_group()

            return True
        except Exception as e:
            logger.error(f"Failed to connect to Zabbix API: {e}")
            return False

    def _verify_host_group(self) -> bool:
        """Verify that the configured host group exists."""
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
        """Find and use the first available host group."""
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
        """Get host by name."""
        try:
            hosts = self.api.host.get(filter={"host": hostname})
            return hosts[0] if hosts else None
        except Exception as e:
            logger.error(f"Error getting host {hostname}: {e}")
            return None

    def get_host_by_ip(self, ip: str) -> Optional[Dict[str, Any]]:
        """Get host by IP address."""
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
        """Create a new host in Zabbix."""
        try:
            # Prepare interface
            interface = {
                "type": 1,  # SNMP
                "main": 1,
                "useip": 1,
                "ip": host_data.get("ip", ""),
                "dns": "",
                "port": "10050"
            }

            # Prepare host groups
            groups = [{"groupid": self.host_group_id}]

            # Prepare templates (empty list if not provided)
            templates = host_data.get("templates", [])

            # Prepare macros (empty list if not provided)
            macros = host_data.get("macros", [])

            # Prepare tags (empty list if not provided)
            tags = host_data.get("tags", [])

            # Create host
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
        """Update an existing host in Zabbix."""
        try:
            # Get existing host
            host = self.get_host_by_name(host_data["host"])
            if not host:
                logger.error(f"Host not found for update: {host_data['host']}")
                return False

            # Prepare update parameters
            update_params = {
                "hostid": host["hostid"],
                "name": host_data.get("name", host_data["host"]),
                "description": host_data.get("description", ""),
                "status": host_data.get("status", 0)
            }

            # Update interfaces if IP is provided
            if "ip" in host_data:
                # Get existing interfaces
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
                        "port": "10050"
                    }
                    self.api.hostinterface.update(**interface_params)

            # Update host
            result = self.api.host.update(**update_params)

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
        """Delete a host from Zabbix."""
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
