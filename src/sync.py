"""
Main sync class that handles RabbitMQ messages and Zabbix operations
"""

import logging
import pika
import sys
from typing import Dict, Any
from .buffer import DeviceBuffer
from .zabbix_client import ZabbixAPIClient
from .message_processor import LMSMessageProcessor

logger = logging.getLogger(__name__)


class LMSZabbixSync:
    """Main sync class that handles RabbitMQ messages and Zabbix operations."""

    def __init__(self, rabbitmq_config: Dict[str, Any], zabbix_config: Dict[str, Any]):
        self.rabbitmq_config = rabbitmq_config
        self.zabbix_config = zabbix_config
        self.zabbix_api = ZabbixAPIClient(
            zabbix_config["url"],
            zabbix_config["username"],
            zabbix_config["password"],
            zabbix_config.get("host_group_id", "1")
        )
        self.device_buffer = DeviceBuffer()
        self.message_processor = LMSMessageProcessor(self.device_buffer, self.zabbix_api)
        self.connection = None
        self.channel = None

    def connect_rabbitmq(self) -> bool:
        """Connect to RabbitMQ."""
        try:
            credentials = pika.PlainCredentials(
                self.rabbitmq_config["username"],
                self.rabbitmq_config["password"]
            )

            parameters = pika.ConnectionParameters(
                host=self.rabbitmq_config["host"],
                port=self.rabbitmq_config["port"],
                virtual_host=self.rabbitmq_config["virtual_host"],
                credentials=credentials
            )

            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()

            # Declare queue
            self.channel.queue_declare(
                queue=self.rabbitmq_config["queue"],
                durable=True
            )

            # Set QoS for fair dispatch
            self.channel.basic_qos(prefetch_count=1)

            logger.info(f"Connected to RabbitMQ: {self.rabbitmq_config['host']}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            return False

    def connect_zabbix(self) -> bool:
        """Connect to Zabbix API."""
        return self.zabbix_api.connect()

    def process_message(self, message_body: str) -> bool:
        """Process a single message and apply changes to Zabbix."""
        try:
            # Parse LMS message format
            zabbix_data = self.message_processor.parse_lms_message(message_body)

            if not zabbix_data:
                # Message was buffered or couldn't be parsed
                buffer_status = self.device_buffer.get_buffer_status()
                logger.info(f"Message buffered or skipped. Buffer status: {buffer_status}")
                return True  # Don't requeue, message was handled appropriately

            action = zabbix_data.get("action")
            host = zabbix_data.get("host")

            if not action or not host:
                logger.error("Invalid message format: missing action or host")
                return False

            logger.info(f"Processing {action} action for host: {host}")

            if action == "create":
                return self.zabbix_api.create_host(zabbix_data) is not None
            elif action == "update":
                return self.zabbix_api.update_host(zabbix_data)
            elif action == "delete":
                return self.zabbix_api.delete_host(host)
            else:
                logger.error(f"Unknown action: {action}")
                return False

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return False

    def message_callback(self, ch, method, properties, body):
        """Callback function for processing RabbitMQ messages."""
        try:
            message_body = body.decode('utf-8')
            logger.info(f"Received message: {method.delivery_tag}")

            # Process the message
            success = self.process_message(message_body)

            if success:
                # Acknowledge the message
                ch.basic_ack(delivery_tag=method.delivery_tag)
                logger.info(f"Message processed successfully: {method.delivery_tag}")
            else:
                # Reject the message and requeue it
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
                logger.warning(f"Message processing failed, requeuing: {method.delivery_tag}")

        except Exception as e:
            logger.error(f"Unexpected error processing message: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    def start_consuming(self):
        """Start consuming messages from RabbitMQ."""
        try:
            # Set up consumer
            self.channel.basic_consume(
                queue=self.rabbitmq_config["queue"],
                on_message_callback=self.message_callback,
                auto_ack=False
            )

            logger.info("Starting to consume messages from RabbitMQ...")

            # Start consuming messages
            self.channel.start_consuming()

        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt, stopping...")
        except Exception as e:
            logger.error(f"Error in consumer: {e}")
        finally:
            if self.connection and not self.connection.is_closed:
                self.connection.close()
            logger.info("Consumer stopped")
