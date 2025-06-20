#!/bin/bash
# Run the PAN-OS MCP Server

# Set up Python path
export PYTHONPATH="$(pwd):$PYTHONPATH"

# Run the server
echo "Starting PAN-OS MCP Server..."
python3 -m src.pan_os_mcp
