"""
Configuration management for LMS-Zabbix Sync
"""

import os
from typing import Dict, Any


def get_config() -> Dict[str, Any]:
    """Get configuration from environment variables or defaults."""
    return {
        "rabbitmq": {
            "host": os.getenv("RABBITMQ_HOST", "10.20.2.16"),
            "port": int(os.getenv("RABBITMQ_PORT", "5672")),
            "username": os.getenv("RABBITMQ_USERNAME", "zabbix"),
            "password": os.getenv("RABBITMQ_PASSWORD", "i5zWVKXSXmmNA"),
            "virtual_host": os.getenv("RABBITMQ_VHOST", "/"),
            "queue": os.getenv("RABBITMQ_QUEUE", "zabbix")
        },
        "zabbix": {
            "url": os.getenv("ZABBIX_URL", "http://94.232.224.241/zabbix"),
            "username": os.getenv("ZABBIX_USERNAME", "Admin"),
            "password": os.getenv("ZABBIX_PASSWORD", "zabbix"),
            "host_group_id": os.getenv("ZABBIX_HOST_GROUP_ID", "1")
        }
    }


def validate_config(config: Dict[str, Any]) -> bool:
    """Validate configuration parameters."""
    required_rabbitmq = ["host", "port", "username", "password", "queue"]
    required_zabbix = ["url", "username", "password"]

    for key in required_rabbitmq:
        if not config["rabbitmq"].get(key):
            raise ValueError(f"Missing required RabbitMQ config: {key}")

    for key in required_zabbix:
        if not config["zabbix"].get(key):
            raise ValueError(f"Missing required Zabbix config: {key}")

    return True
