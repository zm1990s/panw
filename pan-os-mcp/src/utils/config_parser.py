"""
Configuration parser for PAN-OS MCP Server.
Handles loading and parsing device configurations.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger("pan-os-mcp.utils")


class ConfigParser:
    """
    Parser for device configuration files.
    """

    def __init__(self, config_path: str):
        """
        Initialize the configuration parser.
        
        Args:
            config_path: Path to the configuration file
        """
        self.config_path = config_path
        self.config = self._load_config()
        logger.info(f"Loaded configuration from {config_path}")

    def _load_config(self) -> Dict[str, Any]:
        """
        Load the configuration from the file.
        
        Returns:
            The parsed configuration
        
        Raises:
            FileNotFoundError: If the configuration file is not found
            ValueError: If the configuration file is invalid
        """
        if not os.path.exists(self.config_path):
            logger.error(f"Configuration file not found: {self.config_path}")
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        
        try:
            with open(self.config_path, "r") as f:
                config = json.load(f)
            
            # Validate the configuration
            if "devices" not in config or not isinstance(config["devices"], list):
                raise ValueError("Invalid configuration: 'devices' must be a list")
            
            return config
        
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in configuration file: {str(e)}")
            raise ValueError(f"Invalid JSON in configuration file: {str(e)}")
        
        except Exception as e:
            logger.error(f"Error loading configuration: {str(e)}")
            raise ValueError(f"Error loading configuration: {str(e)}")

    def get_device(self, name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get a device configuration by name.
        If no name is provided, returns the default device.
        
        Args:
            name: The name of the device to get
        
        Returns:
            The device configuration
        
        Raises:
            ValueError: If the device is not found
        """
        # If no name is provided, use the default device
        if name is None:
            default_device = self.config.get("default_device")
            if not default_device:
                if len(self.config["devices"]) > 0:
                    # Use the first device as default if no default is specified
                    return self.config["devices"][0]
                else:
                    raise ValueError("No devices configured and no default device specified")
            
            name = default_device
        
        # Find the device by name
        for device in self.config["devices"]:
            if device.get("name") == name:
                return device
        
        raise ValueError(f"Device not found: {name}")

    def get_all_devices(self) -> List[Dict[str, Any]]:
        """
        Get all configured devices.
        
        Returns:
            List of device configurations
        """
        return self.config["devices"]

    def get_default_device_name(self) -> str:
        """
        Get the name of the default device.
        
        Returns:
            The name of the default device
        
        Raises:
            ValueError: If no default device is specified and no devices are configured
        """
        default_device = self.config.get("default_device")
        if default_device:
            return default_device
        
        if len(self.config["devices"]) > 0:
            # Use the first device as default if no default is specified
            return self.config["devices"][0].get("name", "unknown")
        
        raise ValueError("No devices configured and no default device specified")
