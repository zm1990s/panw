"""
MCP Server implementation for PAN-OS.
Handles the server lifecycle and tool/resource registration.
"""

import json
import logging
import sys
import traceback
from typing import Any, Callable, Dict, List, Optional

from .protocol import MCPProtocol, MessageType

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger("pan-os-mcp")


class MCPServer:
    """
    MCP Server for PAN-OS.
    Handles the server lifecycle, tool registration, and message processing.
    """

    def __init__(self, name: str, version: str, vendor: str, description: str):
        """Initialize the MCP server."""
        self.protocol = MCPProtocol(name, version, vendor, description)
        self.tool_handlers: Dict[str, Callable] = {}
        self.resource_handlers: Dict[str, Callable] = {}
        self.running = False
        logger.info(f"Initialized MCP server: {name} v{version}")

    def register_tool(
        self, name: str, description: str, input_schema: Dict[str, Any], handler: Callable
    ) -> None:
        """
        Register a tool with the server.
        
        Args:
            name: Tool name
            description: Tool description
            input_schema: JSON schema for tool input
            handler: Function that implements the tool
        """
        self.protocol.register_tool(name, description, input_schema)
        self.tool_handlers[name] = handler
        logger.info(f"Registered tool: {name}")

    def register_resource(
        self, uri: str, description: str, content_type: str, handler: Callable
    ) -> None:
        """
        Register a resource with the server.
        
        Args:
            uri: Resource URI
            description: Resource description
            content_type: MIME type of the resource
            handler: Function that provides the resource
        """
        self.protocol.register_resource(uri, description, content_type)
        self.resource_handlers[uri] = handler
        logger.info(f"Registered resource: {uri}")

    def start(self) -> None:
        """Start the MCP server."""
        self.running = True
        
        # Send hello message
        hello_message = self.protocol.create_hello_message()
        self.protocol.send_message(hello_message)
        logger.info("Sent hello message")
        
        # Main server loop
        try:
            while self.running:
                try:
                    # Read and process message
                    message = self.protocol.read_message()
                    self._process_message(message)
                except EOFError:
                    logger.info("End of input stream, shutting down")
                    self.running = False
                except Exception as e:
                    logger.error(f"Error processing message: {str(e)}")
                    error_details = {
                        "traceback": traceback.format_exc()
                    }
                    error_message = self.protocol.create_error(
                        "error", f"Internal server error: {str(e)}", error_details
                    )
                    self.protocol.send_message(error_message)
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt, shutting down")
            self.running = False
        
        logger.info("Server stopped")

    def stop(self) -> None:
        """Stop the MCP server."""
        self.running = False
        logger.info("Stopping server")

    def _process_message(self, message: Dict[str, Any]) -> None:
        """
        Process an incoming message.
        
        Args:
            message: The parsed message
        """
        message_type = message.get("type")
        
        if message_type == MessageType.TOOL_CALL:
            self._handle_tool_call(message)
        elif message_type == MessageType.RESOURCE_REQUEST:
            self._handle_resource_request(message)
        else:
            logger.warning(f"Received unsupported message type: {message_type}")
            error_message = self.protocol.create_error(
                message.get("id", "unknown"),
                f"Unsupported message type: {message_type}"
            )
            self.protocol.send_message(error_message)

    def _handle_tool_call(self, message: Dict[str, Any]) -> None:
        """
        Handle a tool call message.
        
        Args:
            message: The tool call message
        """
        call_id = message.get("id")
        tool_name = message.get("name")
        args = message.get("args", {})
        
        logger.info(f"Received tool call: {tool_name} (ID: {call_id})")
        
        if tool_name not in self.tool_handlers:
            logger.warning(f"Tool not found: {tool_name}")
            error_message = self.protocol.create_error(
                call_id, f"Tool not found: {tool_name}"
            )
            self.protocol.send_message(error_message)
            return
        
        try:
            # Call the tool handler
            handler = self.tool_handlers[tool_name]
            result = handler(**args)
            
            # Send the result
            result_message = self.protocol.create_tool_result(call_id, result)
            self.protocol.send_message(result_message)
            logger.info(f"Tool call completed: {tool_name} (ID: {call_id})")
        
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {str(e)}")
            error_details = {
                "traceback": traceback.format_exc()
            }
            error_message = self.protocol.create_error(
                call_id, f"Error executing tool: {str(e)}", error_details
            )
            self.protocol.send_message(error_message)

    def _handle_resource_request(self, message: Dict[str, Any]) -> None:
        """
        Handle a resource request message.
        
        Args:
            message: The resource request message
        """
        request_id = message.get("id")
        uri = message.get("uri")
        
        logger.info(f"Received resource request: {uri} (ID: {request_id})")
        
        if uri not in self.resource_handlers:
            logger.warning(f"Resource not found: {uri}")
            error_message = self.protocol.create_error(
                request_id, f"Resource not found: {uri}"
            )
            self.protocol.send_message(error_message)
            return
        
        try:
            # Call the resource handler
            handler = self.resource_handlers[uri]
            data = handler()
            
            # Send the response
            response_message = self.protocol.create_resource_response(request_id, data)
            self.protocol.send_message(response_message)
            logger.info(f"Resource request completed: {uri} (ID: {request_id})")
        
        except Exception as e:
            logger.error(f"Error retrieving resource {uri}: {str(e)}")
            error_details = {
                "traceback": traceback.format_exc()
            }
            error_message = self.protocol.create_error(
                request_id, f"Error retrieving resource: {str(e)}", error_details
            )
            self.protocol.send_message(error_message)
