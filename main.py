import sys
import logging
from src.config import get_config
from src.sync import LMSZabbixSync

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('lms_zabbix_sync.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def main():
    """Main function to run the LMS-Zabbix sync."""
    try:
        # Load configuration
        config = get_config()

        # Create sync instance
        sync = LMSZabbixSync(config['rabbitmq'], config['zabbix'])

        # Connect to services
        if not sync.connect_rabbitmq():
            logger.error("Failed to connect to RabbitMQ, exiting")
            sys.exit(1)

        if not sync.connect_zabbix():
            logger.error("Failed to connect to Zabbix, exiting")
            sys.exit(1)

        # Start consuming messages
        sync.start_consuming()

    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
