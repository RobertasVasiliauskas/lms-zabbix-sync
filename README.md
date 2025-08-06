# LMS-Zabbix Sync

A Python application that synchronizes device data from LMS (LAN Management System) with Zabbix monitoring system via
RabbitMQ message queue.

## Features

- Connects to RabbitMQ queue to receive LMS database trigger messages
- Processes device and node information from LMS
- Automatically creates, updates, and deletes hosts in Zabbix
- Buffers incomplete device data until all required information is available
- Configurable via environment variables
- Comprehensive logging

## Project Structure

```
lms-zabbix-sync/
├── main.py                  # Main entry point
├── pyproject.toml           # Project metadata and dependencies
├── uv.lock                  # Locked dependencies
├── lms_zabbix_sync.log      # Application log file
├── src/
│   ├── __init__.py              # Package initialization
│   ├── buffer.py                # Device buffer for incomplete data
│   ├── config.py                # Configuration management
│   ├── message_processor.py     # LMS message processing
│   ├── sync.py                  # Main sync orchestration
│   └── zabbix_client.py         # Zabbix API client
│   
├── .env.example             # Environment variables example
└── README.md                # Project documentation
```

## Installation

1. Clone the repository
    ```bash
    git clone git@github.com:RobertasVasiliauskas/lms-zabbix-sync.git
   ```
2. install uv if not already installed:
   ```bash
   pip install uv
   ```
3. Install dependencies using uv:
   ```bash
   uv sync
   ```
4. Run the application:
   ```bash
   uv run python main.py
   ```

## Configuration

The application can be configured using environment variables. See `.env.example` for all available options.

## Usage

The application will:

1. Connect to RabbitMQ and Zabbix
2. Start consuming messages from the configured queue
3. Process device and node changes from LMS
4. Synchronize changes with Zabbix monitoring system

## Logging

Logs are written to both console and `lms_zabbix_sync.log` file.
