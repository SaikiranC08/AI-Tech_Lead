#!/bin/bash

# Stop AI Tech Lead Servers
# This script stops both the Watcher Server and Reviewer Server

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}🛑 AI Tech Lead - Stopping Servers${NC}"

# Function to stop server by PID file
stop_server() {
    local name=$1
    local pid_file="logs/${name,,}_server.pid"
    
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            echo -e "${BLUE}🔴 Stopping $name (PID: $pid)...${NC}"
            kill "$pid"
            
            # Wait for graceful shutdown
            sleep 2
            
            # Force kill if still running
            if kill -0 "$pid" 2>/dev/null; then
                echo -e "${RED}⚠️  Force killing $name...${NC}"
                kill -9 "$pid"
            fi
            
            echo -e "${GREEN}✅ $name stopped${NC}"
        else
            echo -e "${BLUE}ℹ️  $name was not running${NC}"
        fi
        
        rm -f "$pid_file"
    else
        echo -e "${BLUE}ℹ️  No PID file found for $name${NC}"
    fi
}

# Stop servers
stop_server "Watcher Server"
stop_server "Reviewer Server"

# Also kill any Python processes running our servers (backup method)
echo -e "\n${BLUE}🔍 Checking for remaining server processes...${NC}"

# Kill any remaining watcher server processes
watcher_pids=$(pgrep -f "watcher_server.py" || true)
if [ ! -z "$watcher_pids" ]; then
    echo -e "${BLUE}🔴 Killing remaining watcher server processes: $watcher_pids${NC}"
    kill $watcher_pids 2>/dev/null || true
fi

# Kill any remaining reviewer server processes  
reviewer_pids=$(pgrep -f "reviewer_server.py" || true)
if [ ! -z "$reviewer_pids" ]; then
    echo -e "${BLUE}🔴 Killing remaining reviewer server processes: $reviewer_pids${NC}"
    kill $reviewer_pids 2>/dev/null || true
fi

# Check if ports are free now
echo -e "\n${BLUE}🔍 Checking port status...${NC}"

if lsof -Pi :5000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${RED}⚠️  Port 5000 is still in use${NC}"
    lsof -Pi :5000 -sTCP:LISTEN
else
    echo -e "${GREEN}✅ Port 5000 is free${NC}"
fi

if lsof -Pi :5001 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${RED}⚠️  Port 5001 is still in use${NC}"
    lsof -Pi :5001 -sTCP:LISTEN
else
    echo -e "${GREEN}✅ Port 5001 is free${NC}"
fi

echo -e "\n${GREEN}🎉 All servers stopped!${NC}"