import sys
import logging
from src.config import get_config
from src.sync import LMSZabbixSync

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
    sync = None
    try:
        config = get_config()

        if not config:
            logger.error("Configuration loading failed, exiting")
            sys.exit(1)

        sync = LMSZabbixSync(config['rabbitmq'], config['zabbix'])

        if not sync.connect_rabbitmq():
            logger.error("Failed to connect to RabbitMQ, exiting")
            sys.exit(1)

        if not sync.connect_zabbix():
            logger.error("Failed to connect to Zabbix, exiting")
            sys.exit(1)

        sync.start_consuming()

    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)
    finally:
        sync.device_buffer.save_state()


if __name__ == "__main__":
    main()
