#!/usr/bin/env bash
# North Voice Editorial Newsroom Admin Launcher

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "=========================================================="
echo "   📰 North Voice Editorial Newsroom Admin Dashboard     "
echo "=========================================================="
echo "Starting local server at http://localhost:8000 ..."

# Open browser after 1.5 seconds in background
(sleep 1.5 && open "http://localhost:8000") &

# Start Uvicorn FastAPI Server
if [ -d ".venv" ]; then
    .venv/bin/python server.py
else
    python3 server.py
fi
