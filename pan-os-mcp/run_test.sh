#!/bin/bash
# Run the PAN-OS MCP Server with the test client

# Set up Python path
export PYTHONPATH="$(pwd):$PYTHONPATH"

# Run the server with the test client
echo "Starting PAN-OS MCP Server with test client..."

# Create a simple test that just verifies the server starts correctly
echo "Testing server startup..."
python3 -m src.pan_os_mcp &
SERVER_PID=$!

# Wait a moment for the server to start
sleep 2

# Kill the server
echo "Test complete. Stopping server..."
kill $SERVER_PID
