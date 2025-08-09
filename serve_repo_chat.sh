#!/bin/bash

# Serve libraire service using FastAPI

cd /app && python -m uvicorn repo_chat.server:app --host 0.0.0.0 --port 8001 --workers 2 --http httptools --loop uvloop
