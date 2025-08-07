"""
Configuration management for LMS-Zabbix Sync
"""

import os
from typing import Dict, Any

import dotenv

dotenv.load_dotenv()

def get_config() -> Dict[str, Any]:
    """Get configuration from environment variables or defaults."""
    return {
        "rabbitmq": {
            "host": os.getenv("RABBITMQ_HOST"),
            "port": int(os.getenv("RABBITMQ_PORT")),
            "username": os.getenv("RABBITMQ_USERNAME"),
            "password": os.getenv("RABBITMQ_PASSWORD"),
            "virtual_host": os.getenv("RABBITMQ_VHOST"),
            "queue": os.getenv("RABBITMQ_QUEUE")
        },
        "zabbix": {
            "url": os.getenv("ZABBIX_URL"),
            "username": os.getenv("ZABBIX_USERNAME"),
            "password": os.getenv("ZABBIX_PASSWORD"),
            "host_group_id": os.getenv("ZABBIX_HOST_GROUP_ID")
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
