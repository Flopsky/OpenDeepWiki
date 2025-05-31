# Base image
FROM python:3.12-slim

# Install Node.js, npm, supervisord, git, curl, and other dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    nodejs npm supervisor git curl \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy the entire project
COPY . /app

# Make scripts executable
RUN chmod +x /app/serve_indexer.sh /app/serve_repo_chat.sh

# Install Python dependencies
RUN pip install --no-cache-dir -r /app/requirements.txt

# Install frontend dependencies and build
RUN cd /app/frontend && npm install && npm run build

# Copy supervisord configuration
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Create log directory for supervisord
RUN mkdir -p /var/log/supervisor

# Expose necessary ports
EXPOSE 7860 8001 8002 5050

# Command to run supervisord
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
