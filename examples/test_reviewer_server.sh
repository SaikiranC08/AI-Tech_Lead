#!/bin/bash

# Test Script for AI Tech Lead Reviewer Server
# This script demonstrates how to test the Reviewer Server endpoints

# Configuration
REVIEWER_SERVER_URL="http://localhost:5001"
TEST_DATA_FILE="./reviewer_test_payloads.json"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}AI Tech Lead Reviewer Server Test Suite${NC}"
echo -e "${BLUE}========================================${NC}"

# Function to test endpoint
test_endpoint() {
    local endpoint=$1
    local method=$2
    local data=$3
    local description=$4
    
    echo -e "\n${YELLOW}Testing: $description${NC}"
    echo -e "Endpoint: $method $endpoint"
    
    if [ -z "$data" ]; then
        response=$(curl -s -w "\n%{http_code}" "$REVIEWER_SERVER_URL$endpoint")
    else
        response=$(curl -s -w "\n%{http_code}" \
            -H "Content-Type: application/json" \
            -X "$method" \
            -d "$data" \
            "$REVIEWER_SERVER_URL$endpoint")
    fi
    
    # Extract response body and HTTP status code
    http_code=$(echo "$response" | tail -n1)
    response_body=$(echo "$response" | head -n -1)
    
    if [[ $http_code =~ ^2[0-9]{2}$ ]]; then
        echo -e "${GREEN}✅ Success (HTTP $http_code)${NC}"
        echo "$response_body" | jq '.' 2>/dev/null || echo "$response_body"
    else
        echo -e "${RED}❌ Failed (HTTP $http_code)${NC}"
        echo "$response_body" | jq '.' 2>/dev/null || echo "$response_body"
    fi
}

# Test 1: Health Check
test_endpoint "/health" "GET" "" "Health Check"

# Test 2: Server Info
test_endpoint "/info" "GET" "" "Server Information"

# Test 3: Root endpoint
test_endpoint "/" "GET" "" "Root Endpoint"

# Test 4: Test review endpoint with different payloads

# Extract payloads from JSON file (if jq is available)
if command -v jq >/dev/null 2>&1; then
    echo -e "\n${BLUE}Testing Review Endpoint with Different Payloads${NC}"
    
    # Test with basic review payload
    basic_payload=$(jq '.basic_review_payload' $TEST_DATA_FILE)
    test_endpoint "/review" "POST" "$basic_payload" "Basic Review with Issues and Recommendations"
    
    # Test with excellent code payload
    excellent_payload=$(jq '.excellent_code_payload' $TEST_DATA_FILE)
    test_endpoint "/review" "POST" "$excellent_payload" "Excellent Code Review (Should Approve)"
    
    # Test with problematic code payload  
    problematic_payload=$(jq '.problematic_code_payload' $TEST_DATA_FILE)
    test_endpoint "/review" "POST" "$problematic_payload" "Problematic Code Review (Should Request Changes)"
    
    # Test with minimal payload
    minimal_payload=$(jq '.minimal_payload' $TEST_DATA_FILE)
    test_endpoint "/review" "POST" "$minimal_payload" "Minimal Review Payload"
    
else
    echo -e "\n${YELLOW}jq not found. Skipping JSON payload tests.${NC}"
    echo "Install jq to test with structured payloads: brew install jq"
    
    # Simple test payload without jq
    simple_payload='{
        "pr_info": {
            "number": 999,
            "repo_owner": "test-user",
            "repo_name": "test-repo", 
            "installation_id": 12345
        },
        "analysis": {
            "quality_score": 8.0,
            "summary": "Test review from cURL script"
        }
    }'
    
    test_endpoint "/review" "POST" "$simple_payload" "Simple Test Review"
fi

# Test 5: Error cases
echo -e "\n${BLUE}Testing Error Cases${NC}"

# Test with empty payload
test_endpoint "/review" "POST" "{}" "Empty Payload (Should Fail)"

# Test with missing pr_info
missing_pr_info='{"analysis": {"quality_score": 8.0}}'
test_endpoint "/review" "POST" "$missing_pr_info" "Missing PR Info (Should Fail)"

# Test with missing analysis
missing_analysis='{"pr_info": {"number": 123, "repo_owner": "test", "repo_name": "test", "installation_id": 12345}}'
test_endpoint "/review" "POST" "$missing_analysis" "Missing Analysis (Should Fail)"

# Test with invalid JSON
echo -e "\n${YELLOW}Testing: Invalid JSON (Should Fail)${NC}"
echo -e "Endpoint: POST /review"
response=$(curl -s -w "\n%{http_code}" \
    -H "Content-Type: application/json" \
    -X "POST" \
    -d "invalid json" \
    "$REVIEWER_SERVER_URL/review")

http_code=$(echo "$response" | tail -n1)
response_body=$(echo "$response" | head -n -1)

if [[ $http_code == "400" ]]; then
    echo -e "${GREEN}✅ Correctly rejected invalid JSON (HTTP $http_code)${NC}"
else
    echo -e "${RED}❌ Unexpected response to invalid JSON (HTTP $http_code)${NC}"
fi
echo "$response_body" | jq '.' 2>/dev/null || echo "$response_body"

# Test 6: Non-existent endpoint
test_endpoint "/nonexistent" "GET" "" "Non-existent Endpoint (Should Return 404)"

echo -e "\n${BLUE}========================================${NC}"
echo -e "${GREEN}Test Suite Complete${NC}"
echo -e "${BLUE}========================================${NC}"

# Summary
echo -e "\n${YELLOW}Manual Testing Tips:${NC}"
echo "1. Make sure the Reviewer Server is running on port 5001"
echo "2. Ensure your GitHub App credentials are properly configured"
echo "3. Check the server logs for detailed error information"
echo "4. For actual PR testing, update the repo_owner, repo_name, and installation_id in the payloads"

echo -e "\n${YELLOW}Useful Commands:${NC}"
echo "• Start server: python src/ai_tech_lead_project/reviewer_server.py"
echo "• Check logs: tail -f /var/log/ai-tech-lead-reviewer.log (if configured)"
echo "• Quick health check: curl $REVIEWER_SERVER_URL/health"