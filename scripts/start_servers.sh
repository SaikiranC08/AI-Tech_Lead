#!/bin/bash

# Start AI Tech Lead Servers
# This script starts both the Watcher Server and Reviewer Server

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 AI Tech Lead - Starting Servers${NC}"
echo "Project root: $PROJECT_ROOT"

# Check if .env exists
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️  .env file not found. Copying from .env.example...${NC}"
    cp .env.example .env
    echo -e "${RED}❗ Please edit .env with your actual credentials before proceeding${NC}"
    exit 1
fi

# Check for required Python modules
echo -e "\n${BLUE}📦 Checking dependencies...${NC}"
if ! python3 -c "import flask, requests, dotenv, google.generativeai, crewai" 2>/dev/null; then
    echo -e "${RED}❌ Missing dependencies. Installing...${NC}"
    pip3 install -r requirements.txt
fi

# Function to check if port is in use
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null; then
        return 0
    else
        return 1
    fi
}

# Function to start server in background
start_server() {
    local name=$1
    local script_path=$2
    local port=$3
    local log_file=$4
    
    if check_port $port; then
        echo -e "${YELLOW}⚠️  Port $port is already in use. $name may already be running.${NC}"
        return 1
    fi
    
    echo -e "${GREEN}🟢 Starting $name on port $port...${NC}"
    cd src/ai_tech_lead_project
    nohup python3 "$script_path" > "../../logs/$log_file" 2>&1 &
    local pid=$!
    echo $pid > "../../logs/${name,,}_server.pid"
    cd "$PROJECT_ROOT"
    
    # Wait a moment and check if server started
    sleep 2
    if kill -0 $pid 2>/dev/null; then
        echo -e "${GREEN}✅ $name started successfully (PID: $pid)${NC}"
        return 0
    else
        echo -e "${RED}❌ Failed to start $name${NC}"
        return 1
    fi
}

# Create logs directory
mkdir -p logs

# Start servers
echo -e "\n${BLUE}🔧 Starting servers...${NC}"

# Start Reviewer Server first (dependency for Watcher Server)
start_server "Reviewer Server" "reviewer_server.py" 5001 "reviewer_server.log"
reviewer_status=$?

# Start Watcher Server
start_server "Watcher Server" "watcher_server.py" 5000 "watcher_server.log"
watcher_status=$?

# Wait for servers to fully initialize
echo -e "\n${BLUE}⏳ Waiting for servers to initialize...${NC}"
sleep 5

# Health check
echo -e "\n${BLUE}🏥 Performing health checks...${NC}"

# Check Reviewer Server
if curl -s http://localhost:5001/health > /dev/null; then
    echo -e "${GREEN}✅ Reviewer Server (port 5001) is healthy${NC}"
else
    echo -e "${RED}❌ Reviewer Server health check failed${NC}"
fi

# Check Watcher Server
if curl -s http://localhost:5000/health > /dev/null; then
    echo -e "${GREEN}✅ Watcher Server (port 5000) is healthy${NC}"
else
    echo -e "${RED}❌ Watcher Server health check failed${NC}"
fi

# Display status
echo -e "\n${BLUE}📊 Server Status:${NC}"
echo "=================================="
echo "Watcher Server:   http://localhost:5000"
echo "Reviewer Server:  http://localhost:5001"
echo ""
echo "Logs:"
echo "  Watcher:   tail -f logs/watcher_server.log"
echo "  Reviewer:  tail -f logs/reviewer_server.log"
echo ""
echo "Stop servers: ./scripts/stop_servers.sh"

# Show integration test option
echo -e "\n${YELLOW}🧪 To test the integration:${NC}"
echo "  python3 scripts/test_integration.py"

# Show useful endpoints
echo -e "\n${BLUE}🔗 Useful Endpoints:${NC}"
echo "  Health checks:"
echo "    curl http://localhost:5000/health"
echo "    curl http://localhost:5001/health"
echo ""
echo "  Server info:"
echo "    curl http://localhost:5000/"
echo "    curl http://localhost:5001/info"
echo ""
echo "  Test review posting:"
echo "    curl -X POST http://localhost:5001/review \\"
echo "      -H 'Content-Type: application/json' \\"
echo "      -d @examples/reviewer_test_payloads.json"

echo -e "\n${GREEN}🎉 AI Tech Lead servers are ready!${NC}"