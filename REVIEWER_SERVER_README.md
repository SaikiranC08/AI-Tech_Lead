# AI Tech Lead - Reviewer Server

The Reviewer Server is a Flask-based microservice that receives CrewAI analysis results and automatically posts structured code reviews to GitHub pull requests.

## Overview

The Reviewer Server complements the existing Watcher Server by handling the final step in the automated code review pipeline:

1. **Watcher Server** receives GitHub webhook events and triggers CrewAI workflow
2. **CrewAI** analyzes the code and generates structured feedback
3. **Reviewer Server** transforms the analysis into GitHub review comments and posts them

## Features

- ✅ **RESTful API** with comprehensive endpoints
- ✅ **GitHub App Authentication** with JWT tokens and installation tokens
- ✅ **Intelligent Review Logic** that determines approve/request changes/comment based on analysis
- ✅ **Rich Review Formatting** with emojis, categories, and structured feedback
- ✅ **Error Handling** with detailed logging and graceful failures
- ✅ **Health Monitoring** with connectivity checks
- ✅ **Modular Architecture** with separate concerns for API, review logic, and GitHub integration

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Watcher       │    │     CrewAI      │    │   Reviewer      │
│   Server        │───▶│   Workflow      │───▶│   Server        │
│  (Port 5000)    │    │                 │    │  (Port 5001)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                                              │
         ▼                                              ▼
┌─────────────────┐                            ┌─────────────────┐
│  GitHub         │                            │  GitHub         │
│  Webhooks       │                            │  Reviews API    │
└─────────────────┘                            └─────────────────┘
```

### Components

- **`reviewer_server.py`** - Main Flask application with REST endpoints
- **`github_api.py`** - GitHub API integration with authentication and review posting
- **`review_handler.py`** - Transforms CrewAI analysis into structured GitHub reviews

## Installation & Setup

### Prerequisites

- Python 3.8+
- GitHub App with appropriate permissions
- All dependencies from `requirements.txt`

### Configuration

1. **Environment Variables**: Copy `.env.example` to `.env` and configure:

```bash
# GitHub App Configuration
GITHUB_APP_ID=your_app_id
GITHUB_APP_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----"

# Server Configuration
REVIEWER_PORT=5001
FLASK_ENV=development
LOG_LEVEL=INFO
```

2. **GitHub App Permissions**: Your GitHub App needs these permissions:
   - **Pull requests**: Read & Write
   - **Contents**: Read
   - **Metadata**: Read

3. **Install Dependencies**:
```bash
pip install -r requirements.txt
```

## Running the Server

### Development Mode

```bash
# From the project root
cd src/ai_tech_lead_project
python reviewer_server.py
```

The server will start on `http://localhost:5001`

### Production Mode

```bash
# Using gunicorn
gunicorn -w 4 -b 0.0.0.0:5001 src.ai_tech_lead_project.reviewer_server:app

# Or set environment
export FLASK_ENV=production
python reviewer_server.py
```

## API Endpoints

### `POST /review`

Post a code review to GitHub based on CrewAI analysis results.

**Request Body:**
```json
{
  "pr_info": {
    "number": 123,
    "repo_owner": "username",
    "repo_name": "repository",
    "installation_id": 12345
  },
  "analysis": {
    "quality_score": 7.5,
    "summary": "Overall analysis summary",
    "issues": [
      {
        "title": "SQL Injection Vulnerability",
        "description": "User input is not properly sanitized",
        "severity": "critical",
        "category": "security",
        "file": "src/auth.py",
        "line": 45,
        "suggestion": "Use parameterized queries",
        "code_example": "cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))"
      }
    ],
    "recommendations": [
      {
        "title": "Add Unit Tests",
        "description": "Authentication module lacks tests",
        "category": "testing",
        "priority": "high",
        "file": "src/auth.py",
        "line": 1,
        "benefits": "Improves reliability",
        "example": "def test_auth_success():\n    assert authenticate(user, pass) == True"
      }
    ]
  }
}
```

**Response (Success):**
```json
{
  "message": "Review posted successfully",
  "pr_number": 123,
  "review_id": 456789,
  "status": "success"
}
```

### `GET /health`

Health check endpoint with GitHub API connectivity verification.

**Response:**
```json
{
  "status": "healthy",
  "service": "AI Tech Lead Reviewer Server",
  "version": "1.0.0",
  "timestamp": "2024-01-01T12:00:00.000000",
  "components": {
    "github_api": "healthy"
  }
}
```

### `GET /info`

Server metadata and configuration information.

### `GET /`

Redirects to `/info`.

## Review Logic

The Reviewer Server intelligently determines the review type based on the analysis:

### Review Events

- **`APPROVE`** - Quality score ≥ 8.5 and no high/critical issues
- **`REQUEST_CHANGES`** - Critical issues OR quality score < 6.0 OR ≥3 high issues  
- **`COMMENT`** - Neutral feedback for other cases

### Review Structure

1. **Main Review Comment**:
   - Quality score with emoji
   - Analysis summary
   - Issues breakdown by severity and category
   - Key recommendations

2. **Line-Specific Comments**:
   - Issues with severity indicators
   - Recommendations with examples
   - Proper markdown formatting
   - Category emojis for visual clarity

## Testing

### Automated Testing

Run the comprehensive test suite:

```bash
# Make the test script executable (already done)
chmod +x examples/test_reviewer_server.sh

# Run tests (requires jq for JSON parsing)
cd examples
./test_reviewer_server.sh
```

### Manual Testing

Test individual endpoints:

```bash
# Health check
curl http://localhost:5001/health

# Server info
curl http://localhost:5001/info

# Post a review (using example payload)
curl -X POST http://localhost:5001/review \
  -H "Content-Type: application/json" \
  -d @examples/reviewer_test_payloads.json
```

### Test Payloads

The `examples/reviewer_test_payloads.json` file contains:
- **basic_review_payload** - Standard review with issues and recommendations
- **excellent_code_payload** - High-quality code (should approve)
- **problematic_code_payload** - Poor code (should request changes)  
- **minimal_payload** - Minimal valid payload

## Integration with CrewAI

To integrate with your existing CrewAI workflow, modify the CrewAI agent to send results to the Reviewer Server:

```python
import requests

def send_to_reviewer(analysis_result, pr_info):
    payload = {
        "pr_info": pr_info,
        "analysis": analysis_result
    }
    
    response = requests.post(
        "http://localhost:5001/review",
        json=payload,
        headers={"Content-Type": "application/json"}
    )
    
    return response.json()
```

## Example Integration Flow

1. **GitHub webhook** triggers Watcher Server
2. **Watcher Server** extracts PR info and calls CrewAI
3. **CrewAI** analyzes code and returns structured results
4. **Watcher Server** sends results to Reviewer Server:

```python
# In your CrewAI completion callback
review_payload = {
    "pr_info": pr_info,  # From webhook payload
    "analysis": crew_result  # From CrewAI
}

response = requests.post(
    "http://localhost:5001/review",
    json=review_payload
)
```

## Logging

The server provides comprehensive logging:

- **INFO**: Normal operations, review postings
- **ERROR**: API failures, invalid payloads
- **DEBUG**: Detailed GitHub API interactions

Configure logging level via `LOG_LEVEL` environment variable.

## Error Handling

The server handles various error scenarios:

- **Invalid payloads** → 400 Bad Request with details
- **GitHub API errors** → 500 Internal Server Error with GitHub response
- **Authentication failures** → Proper error logging and user feedback
- **Network issues** → Graceful degradation with retry logic

## Security

- **GitHub App Authentication** using JWT and installation tokens
- **Token caching** with automatic expiration handling
- **Input validation** for all API endpoints
- **Secure credential handling** via environment variables

## Monitoring

Monitor the service using:
- Health check endpoint (`/health`)
- Server logs
- GitHub API rate limits
- Review posting success rates

## Troubleshooting

### Common Issues

1. **"Missing required environment variables"**
   - Ensure `GITHUB_APP_ID` and `GITHUB_APP_PRIVATE_KEY` are set
   - Check that private key format includes proper line breaks (`\n`)

2. **"GitHub API connectivity check failed"**
   - Verify GitHub App ID is correct
   - Ensure private key matches the GitHub App
   - Check network connectivity to api.github.com

3. **"Failed to get installation token"**
   - Verify the installation_id in the payload is correct
   - Ensure your GitHub App is installed on the target repository
   - Check GitHub App permissions (needs Pull requests: Write)

4. **Review not appearing on GitHub**
   - Check that the PR number, repo_owner, and repo_name are correct
   - Verify the GitHub App has proper permissions
   - Review server logs for API errors

### Debug Mode

Run with debug logging:
```bash
export LOG_LEVEL=DEBUG
python reviewer_server.py
```

## Performance

- **Token caching** reduces GitHub API calls
- **Async-ready architecture** for future scaling
- **Error resilience** prevents cascading failures
- **Rate limit handling** for GitHub API compliance

## Future Enhancements

- **Webhook integration** for direct CrewAI to Reviewer communication
- **Review templates** for different project types
- **Multi-repository support** with different review strategies
- **Analytics dashboard** for review metrics
- **Custom review rules** per repository

---

## Quick Start Commands

```bash
# 1. Setup environment
cp .env.example .env
# Edit .env with your GitHub App credentials

# 2. Install dependencies  
pip install -r requirements.txt

# 3. Start server
python src/ai_tech_lead_project/reviewer_server.py

# 4. Test server
curl http://localhost:5001/health

# 5. Run comprehensive tests
cd examples && ./test_reviewer_server.sh
```

The Reviewer Server is now ready to handle automated code reviews! 🚀