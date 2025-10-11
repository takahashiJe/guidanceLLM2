import logging
import os
from logging.handlers import RotatingFileHandler

LOG_DIR = "backend/logs"
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# Cache for created loggers
loggers = {}

def get_device_logger(device_uuid: str | None) -> logging.Logger:
    """
    Retrieves a logger for a specific device UUID.
    Loggers are cached to avoid recreating them for each request.
    """
    if not device_uuid:
        device_uuid = "unknown_device"

    if device_uuid in loggers:
        return loggers[device_uuid]

    logger = logging.getLogger(device_uuid)
    logger.setLevel(logging.INFO)

    # Prevent propagation to parent loggers (like the root logger)
    logger.propagate = False

    # Create a rotating file handler for this specific UUID
    handler = RotatingFileHandler(
        os.path.join(LOG_DIR, f"{device_uuid}.log"),
        maxBytes=1024 * 1024 * 5,  # 5 MB
        backupCount=3,
        encoding='utf-8'
    )

    # Use a simple formatter, as the message will be pre-formatted
    formatter = logging.Formatter('%(message)s')
    handler.setFormatter(formatter)

    # Add the handler to the logger, ensuring it's not added multiple times
    if not logger.handlers:
        logger.addHandler(handler)

    loggers[device_uuid] = logger
    return logger


def get_lora_logger() -> logging.Logger:
    """
    Retrieves a dedicated logger for LoRa communication events.
    This logger writes to a fixed file 'lora_communication.log'.
    """
    logger_name = "lora_communication"
    
    # Avoid adding handlers multiple times if already configured
    if logger_name in loggers:
        return loggers[logger_name]

    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    # Create a rotating file handler for LoRa communication
    handler = RotatingFileHandler(
        os.path.join(LOG_DIR, "lora_communication.log"),
        maxBytes=1024 * 1024 * 2,  # 2 MB
        backupCount=3,
        encoding='utf-8'
    )

    # Formatter with timestamp
    formatter = logging.Formatter('%(asctime)s - %(message)s')
    handler.setFormatter(formatter)

    if not logger.handlers:
        logger.addHandler(handler)

    loggers[logger_name] = logger
    return logger
