#!/usr/bin/env python3
"""
Test script for PAN-OS MCP Server.
"""

import json
import sys
import time
from typing import Dict, Any

# Sample MCP messages
HELLO_MESSAGE = {
    "type": "hello"
}

GET_SYSTEM_INFO_MESSAGE = {
    "type": "tool_call",
    "id": "test-1",
    "name": "get_system_info",
    "args": {}
}

OP_COMMAND_MESSAGE = {
    "type": "tool_call",
    "id": "test-2",
    "name": "op_command",
    "args": {
        "xml_cmd": "<show><system><info></info></system></show>"
    }
}

CONFIG_ACTION_MESSAGE = {
    "type": "tool_call",
    "id": "test-3",
    "name": "config_action",
    "args": {
        "action": "get",
        "xpath": "/config/devices/entry/deviceconfig/system"
    }
}


def send_message(message: Dict[str, Any]) -> None:
    """
    Send a message to the MCP server.
    
    Args:
        message: The message to send
    """
    json_str = json.dumps(message)
    print(f"Sending: {json_str}", file=sys.stderr)
    print(json_str)
    sys.stdout.flush()


def read_message() -> Dict[str, Any]:
    """
    Read a message from the MCP server.
    
    Returns:
        The parsed message
    """
    try:
        line = sys.stdin.readline().strip()
        if not line:
            print("Error: Empty response from server", file=sys.stderr)
            sys.exit(1)
        
        print(f"Received: {line}", file=sys.stderr)
        return json.loads(line)
    except Exception as e:
        print(f"Error reading message: {str(e)}", file=sys.stderr)
        sys.exit(1)


def main():
    """Main entry point."""
    try:
        # Wait for hello message
        hello_response = read_message()
        if hello_response.get("type") != "hello":
            print(f"Error: Expected hello message, got: {hello_response}", file=sys.stderr)
            sys.exit(1)
        
        print("Server info:", file=sys.stderr)
        print(f"  Name: {hello_response.get('name')}", file=sys.stderr)
        print(f"  Version: {hello_response.get('version')}", file=sys.stderr)
        print(f"  Vendor: {hello_response.get('vendor')}", file=sys.stderr)
        print(f"  Description: {hello_response.get('description')}", file=sys.stderr)
        print(f"  Tools: {len(hello_response.get('tools', {}))}", file=sys.stderr)
        print(f"  Resources: {len(hello_response.get('resources', {}))}", file=sys.stderr)
        
        # Test get_system_info
        print("\nTesting get_system_info...", file=sys.stderr)
        send_message(GET_SYSTEM_INFO_MESSAGE)
        system_info_response = read_message()
        
        if system_info_response.get("type") != "tool_result":
            print(f"Error: Expected tool_result, got: {system_info_response}", file=sys.stderr)
        else:
            print(f"System info result: {json.dumps(system_info_response.get('result'), indent=2)}", file=sys.stderr)
        
        # Test op_command
        print("\nTesting op_command...", file=sys.stderr)
        send_message(OP_COMMAND_MESSAGE)
        op_command_response = read_message()
        
        if op_command_response.get("type") != "tool_result":
            print(f"Error: Expected tool_result, got: {op_command_response}", file=sys.stderr)
        else:
            print(f"Op command result: {json.dumps(op_command_response.get('result'), indent=2)}", file=sys.stderr)
        
        # Test config_action
        print("\nTesting config_action...", file=sys.stderr)
        send_message(CONFIG_ACTION_MESSAGE)
        config_action_response = read_message()
        
        if config_action_response.get("type") != "tool_result":
            print(f"Error: Expected tool_result, got: {config_action_response}", file=sys.stderr)
        else:
            print(f"Config action result: {json.dumps(config_action_response.get('result'), indent=2)}", file=sys.stderr)
        
        print("\nAll tests completed.", file=sys.stderr)
    
    except KeyboardInterrupt:
        print("Test interrupted by user", file=sys.stderr)
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
