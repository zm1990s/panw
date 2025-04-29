FROM python:3-alpine

# Set the working directory
WORKDIR /app

# Copy the necessary files
COPY src/panw_airs_mcp_sse.py ./

# Install the project's dependencies
RUN pip3 install mcp httpx requests tabulate -i https://pypi.tuna.tsinghua.edu.cn/simple

# Copy the rest of the application files

# Expose the port that the server will run on
EXPOSE 8080

# Default command to run the server
CMD ["python3", "panw_airs_mcp_sse.py"]