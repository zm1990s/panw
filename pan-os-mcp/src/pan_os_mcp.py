#!/usr/bin/env python3
"""
PAN-OS MCP Server main entry point.
Registers tools and starts the MCP server.
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.panos.client import PANOSClient
from src.mcp.server import MCPServer
from src.utils.config_parser import ConfigParser

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger("pan-os-mcp")

# Tool input schemas
GET_SYSTEM_INFO_SCHEMA = {
    "type": "object",
    "properties": {},
    "title": "get_system_infoArguments"
}

OP_COMMAND_SCHEMA = {
    "type": "object",
    "properties": {
        "xml_cmd": {
            "title": "Xml Cmd",
            "type": "string"
        }
    },
    "required": [
        "xml_cmd"
    ],
    "title": "op_commandArguments"
}

COMMIT_CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "force": {
            "default": False,
            "title": "Force",
            "type": "boolean"
        },
        "partial_xml": {
            "anyOf": [
                {
                    "type": "string"
                },
                {
                    "type": "null"
                }
            ],
            "default": None,
            "title": "Partial Xml"
        }
    },
    "title": "commit_configArguments"
}

COMMIT_ALL_SHARED_POLICY_SCHEMA = {
    "type": "object",
    "properties": {
        "device_group": {
            "anyOf": [
                {
                    "type": "string"
                },
                {
                    "type": "null"
                }
            ],
            "default": None,
            "title": "Device Group"
        },
        "validate_only": {
            "default": False,
            "title": "Validate Only",
            "type": "boolean"
        }
    },
    "title": "commit_all_shared_policyArguments"
}

CONFIG_ACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "title": "Action",
            "type": "string"
        },
        "xpath": {
            "title": "Xpath",
            "type": "string"
        },
        "element_xml": {
            "anyOf": [
                {
                    "type": "string"
                },
                {
                    "type": "null"
                }
            ],
            "default": None,
            "title": "Element Xml"
        },
        "newname": {
            "anyOf": [
                {
                    "type": "string"
                },
                {
                    "type": "null"
                }
            ],
            "default": None,
            "title": "Newname"
        },
        "from_path": {
            "anyOf": [
                {
                    "type": "string"
                },
                {
                    "type": "null"
                }
            ],
            "default": None,
            "title": "From Path"
        },
        "dst": {
            "anyOf": [
                {
                    "type": "string"
                },
                {
                    "type": "null"
                }
            ],
            "default": None,
            "title": "Dst"
        },
        "where": {
            "anyOf": [
                {
                    "type": "string"
                },
                {
                    "type": "null"
                }
            ],
            "default": None,
            "title": "Where"
        }
    },
    "required": [
        "action",
        "xpath"
    ],
    "title": "config_actionArguments"
}


class PANOSMCPServer:
    """
    PAN-OS MCP Server.
    Registers tools and starts the MCP server.
    """

    def __init__(self):
        """Initialize the PAN-OS MCP Server."""
        # Find the config directory relative to this file
        script_dir = Path(__file__).resolve().parent.parent
        config_path = script_dir / "config" / "devices.json"
        
        # Load device configuration
        self.config_parser = ConfigParser(str(config_path))
        
        # Create PAN-OS client for the default device
        device_config = self.config_parser.get_device()
        self.client = self._create_client(device_config)
        
        # Create MCP server
        self.server = MCPServer(
            name="pan-os",
            version="1.0.0",
            vendor="Palo Alto Networks",
            description="MCP Server for PAN-OS XML API"
        )
        
        # Register tools
        self._register_tools()

    def _create_client(self, device_config: Dict[str, Any]) -> PANOSClient:
        """
        Create a PAN-OS client from device configuration.
        
        Args:
            device_config: The device configuration
        
        Returns:
            The PAN-OS client
        """
        hostname = device_config.get("ip")
        if not hostname:
            raise ValueError("Device IP is required")
        
        auth_method = device_config.get("auth_method", "api_key")
        
        if auth_method == "api_key":
            api_key = device_config.get("api_key")
            if not api_key:
                raise ValueError("API key is required for auth_method='api_key'")
            
            return PANOSClient(hostname=hostname, api_key=api_key)
        
        elif auth_method == "username_password":
            username = device_config.get("username")
            password = device_config.get("password")
            if not username or not password:
                raise ValueError("Username and password are required for auth_method='username_password'")
            
            return PANOSClient(hostname=hostname, username=username, password=password)
        
        else:
            raise ValueError(f"Unsupported auth_method: {auth_method}")

    def _register_tools(self):
        """Register all tools with the MCP server."""
        # Register get_system_info tool
        self.server.register_tool(
            name="get_system_info",
            description="Example MCP tool function that retrieves basic system info\nfrom a PAN-OS device using the XML API.",
            input_schema=GET_SYSTEM_INFO_SCHEMA,
            handler=self.get_system_info
        )
        
        # Register op_command tool
        self.server.register_tool(
            name="op_command",
            description="Executes an arbitrary operational command (e.g. <show><system><info></info></system></show>)\nor \n<request><restart><system></system></restart></request>",
            input_schema=OP_COMMAND_SCHEMA,
            handler=self.op_command
        )
        
        # Register commit_config tool
        self.server.register_tool(
            name="commit_config",
            description="Commit the candidate config on the firewall. \nOptionally handle force commits or partial commits (by providing partial_xml).\n:param force: If True, commits with <force></force>\n:param partial_xml: e.g. <partial><admin><member>bob</member></admin></partial>",
            input_schema=COMMIT_CONFIG_SCHEMA,
            handler=self.commit_config
        )
        
        # Register commit_all_shared_policy tool
        self.server.register_tool(
            name="commit_all_shared_policy",
            description="Commit (push) changes from Panorama to managed devices.\nIf 'validate_only' is True, no actual commit is performed (just validation).\nIf 'device_group' is provided, push only to that device-group.",
            input_schema=COMMIT_ALL_SHARED_POLICY_SCHEMA,
            handler=self.commit_all_shared_policy
        )
        
        # Register config_action tool
        self.server.register_tool(
            name="config_action",
            description="Perform config actions (set/edit/delete/rename/clone/move/override...) on a \nspecified XPath. \n:param action: e.g. \"show\", \"get\", \"set\", \"edit\", \"delete\", \"rename\",\n                          \"clone\", \"move\", \"override\", \"multi-move\", ...\n:param xpath:  The target XPath, e.g. /config/devices/entry/vsys/entry/rulebase/security\n:param element_xml: XML snippet to set or edit (if any)\n:param newname: Used with rename or clone\n:param from_path: The source for clone\n:param dst: Used with move action to indicate the destination\n:param where: \"before\", \"after\", \"top\", or \"bottom\" for move actions",
            input_schema=CONFIG_ACTION_SCHEMA,
            handler=self.config_action
        )

    def get_system_info(self) -> Dict[str, Any]:
        """
        Get system information from the PAN-OS device.
        
        Returns:
            Dictionary containing system information
        """
        try:
            return self.client.get_system_info()
        except Exception as e:
            logger.error(f"Error getting system info: {str(e)}")
            return {"error": str(e)}

    def op_command(self, xml_cmd: str) -> Dict[str, Any]:
        """
        Execute an operational command.
        
        Args:
            xml_cmd: The XML command to execute
        
        Returns:
            Dictionary containing the command result
        """
        try:
            return self.client.execute_op_command(xml_cmd)
        except Exception as e:
            logger.error(f"Error executing op command: {str(e)}")
            return {"error": str(e)}

    def commit_config(self, force: bool = False, partial_xml: Optional[str] = None) -> Dict[str, Any]:
        """
        Commit the candidate configuration.
        
        Args:
            force: Whether to force the commit
            partial_xml: XML for partial commit
        
        Returns:
            Dictionary containing the commit result
        """
        try:
            return self.client.commit(force=force, partial=partial_xml)
        except Exception as e:
            logger.error(f"Error committing config: {str(e)}")
            return {"error": str(e)}

    def commit_all_shared_policy(self, device_group: Optional[str] = None, validate_only: bool = False) -> Dict[str, Any]:
        """
        Commit (push) changes from Panorama to managed devices.
        
        Args:
            device_group: The device group to push to
            validate_only: Whether to only validate the commit
        
        Returns:
            Dictionary containing the commit result
        """
        try:
            cmd_parts = ["<commit-all>"]
            
            if validate_only:
                cmd_parts.append("<validate-only>yes</validate-only>")
            
            if device_group:
                cmd_parts.append(f"<device-group><entry name='{device_group}'/></device-group>")
            
            cmd_parts.append("</commit-all>")
            cmd = "".join(cmd_parts)
            
            return self.client.execute_op_command(cmd)
        except Exception as e:
            logger.error(f"Error committing shared policy: {str(e)}")
            return {"error": str(e)}

    def config_action(
        self,
        action: str,
        xpath: str,
        element_xml: Optional[str] = None,
        newname: Optional[str] = None,
        from_path: Optional[str] = None,
        dst: Optional[str] = None,
        where: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Perform a configuration action.
        
        Args:
            action: The action to perform
            xpath: The XPath to the configuration
            element_xml: The XML element to set or edit
            newname: Used with rename or clone
            from_path: The source for clone
            dst: Used with move action to indicate the destination
            where: "before", "after", "top", or "bottom" for move actions
        
        Returns:
            Dictionary containing the result
        """
        try:
            if action == "get":
                return self.client.get_configuration(xpath)
            elif action == "set":
                if not element_xml:
                    raise ValueError("element_xml is required for action='set'")
                return self.client.set_configuration(xpath, element_xml)
            elif action == "edit":
                if not element_xml:
                    raise ValueError("element_xml is required for action='edit'")
                return self.client.edit_configuration(xpath, element_xml)
            elif action == "delete":
                return self.client.delete_configuration(xpath)
            else:
                # For other actions, construct a custom request
                extra_params = {"action": action, "xpath": xpath}
                
                if element_xml:
                    extra_params["element"] = element_xml
                
                if newname:
                    extra_params["newname"] = newname
                
                if from_path:
                    extra_params["from"] = from_path
                
                if dst:
                    extra_params["dst"] = dst
                
                if where:
                    extra_params["where"] = where
                
                root = self.client._make_request("config", **extra_params)
                return self.client._xml_to_dict(root)
        
        except Exception as e:
            logger.error(f"Error performing config action: {str(e)}")
            return {"error": str(e)}

    def start(self):
        """Start the MCP server."""
        try:
            logger.info("Starting PAN-OS MCP Server")
            self.server.start()
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt, shutting down")
        except Exception as e:
            logger.error(f"Error starting server: {str(e)}")
            sys.exit(1)


def main():
    """Main entry point."""
    try:
        server = PANOSMCPServer()
        server.start()
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
