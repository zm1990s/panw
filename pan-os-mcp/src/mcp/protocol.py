"""
MCP Protocol implementation for PAN-OS MCP Server.
Handles the Model Context Protocol communication.
"""

import json
import sys
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class MessageType(str, Enum):
    """MCP message types."""
    HELLO = "hello"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    RESOURCE_REQUEST = "resource_request"
    RESOURCE_RESPONSE = "resource_response"
    ERROR = "error"


class HelloMessage(BaseModel):
    """Hello message sent by the server to introduce itself."""
    type: str = MessageType.HELLO
    name: str
    version: str
    vendor: str
    description: str
    tools: Dict[str, Dict[str, Any]]
    resources: Dict[str, Dict[str, Any]]


class ToolCallMessage(BaseModel):
    """Tool call message received from the client."""
    type: str = MessageType.TOOL_CALL
    id: str
    name: str
    args: Dict[str, Any]


class ToolResultMessage(BaseModel):
    """Tool result message sent back to the client."""
    type: str = MessageType.TOOL_RESULT
    id: str
    result: Dict[str, Any]


class ResourceRequestMessage(BaseModel):
    """Resource request message received from the client."""
    type: str = MessageType.RESOURCE_REQUEST
    id: str
    uri: str


class ResourceResponseMessage(BaseModel):
    """Resource response message sent back to the client."""
    type: str = MessageType.RESOURCE_RESPONSE
    id: str
    data: Any


class ErrorMessage(BaseModel):
    """Error message sent back to the client."""
    type: str = MessageType.ERROR
    id: str
    error: str
    details: Optional[Dict[str, Any]] = None


class MCPProtocol:
    """
    Handles the Model Context Protocol communication.
    Responsible for parsing incoming messages and formatting outgoing messages.
    """

    def __init__(self, server_name: str, server_version: str, server_vendor: str, server_description: str):
        """Initialize the MCP protocol handler."""
        self.server_name = server_name
        self.server_version = server_version
        self.server_vendor = server_vendor
        self.server_description = server_description
        self.tools = {}
        self.resources = {}

    def register_tool(self, name: str, description: str, input_schema: Dict[str, Any]) -> None:
        """Register a tool with the protocol handler."""
        self.tools[name] = {
            "description": description,
            "input_schema": input_schema
        }

    def register_resource(self, uri: str, description: str, content_type: str) -> None:
        """Register a resource with the protocol handler."""
        self.resources[uri] = {
            "description": description,
            "content_type": content_type
        }

    def create_hello_message(self) -> Dict[str, Any]:
        """Create a hello message to introduce the server."""
        return HelloMessage(
            name=self.server_name,
            version=self.server_version,
            vendor=self.server_vendor,
            description=self.server_description,
            tools=self.tools,
            resources=self.resources
        ).model_dump()

    def parse_message(self, message_str: str) -> Dict[str, Any]:
        """Parse an incoming message string into a structured message."""
        try:
            message = json.loads(message_str)
            if not isinstance(message, dict) or "type" not in message:
                raise ValueError("Invalid message format: missing 'type' field")
            
            message_type = message.get("type")
            
            if message_type == MessageType.TOOL_CALL:
                return ToolCallMessage(**message).model_dump()
            elif message_type == MessageType.RESOURCE_REQUEST:
                return ResourceRequestMessage(**message).model_dump()
            else:
                raise ValueError(f"Unsupported message type: {message_type}")
        
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {str(e)}")
        except Exception as e:
            raise ValueError(f"Error parsing message: {str(e)}")

    def create_tool_result(self, call_id: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """Create a tool result message."""
        return ToolResultMessage(
            id=call_id,
            result=result
        ).model_dump()

    def create_resource_response(self, request_id: str, data: Any) -> Dict[str, Any]:
        """Create a resource response message."""
        return ResourceResponseMessage(
            id=request_id,
            data=data
        ).model_dump()

    def create_error(self, message_id: str, error_message: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create an error message."""
        return ErrorMessage(
            id=message_id,
            error=error_message,
            details=details
        ).model_dump()

    def send_message(self, message: Dict[str, Any]) -> None:
        """Send a message to stdout."""
        json_str = json.dumps(message)
        sys.stdout.write(json_str + "\n")
        sys.stdout.flush()

    def read_message(self) -> Dict[str, Any]:
        """Read a message from stdin."""
        line = sys.stdin.readline().strip()
        if not line:
            raise EOFError("End of input stream")
        return self.parse_message(line)
