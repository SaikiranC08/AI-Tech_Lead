# AI Tech Lead - GitHub App

**Last Updated:** September 25, 2025

## Overview

This is an AI-powered GitHub App that provides automated code review and unit testing for pull requests using Google Gemini API and the CrewAI framework. The application is structured as a Flask-based webhook server that integrates with GitHub to analyze code changes and provide intelligent feedback.

## Recent Changes

- **September 25, 2025**: Initial Replit setup completed
  - Installed Python 3.11 and all project dependencies
  - Configured Flask watcher server to run on port 5000
  - Set up workflow with environment variables for development
  - Configured deployment settings for production (VM with Gunicorn)
  - Server successfully running and responding to health checks

## Project Architecture

### Core Components
- **Watcher Server** (`watcher_server.py`): Main Flask webhook server (port 5000)
- **Reviewer Server** (`reviewer_server.py`): GitHub review posting service (port 5006) - Optional
- **CrewAI Agents**: AI-powered analysis agents (reviewer, tester, reporter)
- **GitHub API Integration**: Handles GitHub App authentication and review posting

### Multi-Agent Architecture
```
GitHub PR Event → Watcher Server → CrewAI Crew → AI Analysis → GitHub Comment
```

## Configuration

### Environment Variables (for production)
The following environment variables are required for full functionality:
- `GITHUB_APP_ID`: GitHub App ID
- `GITHUB_APP_PRIVATE_KEY`: GitHub App private key (PEM format)
- `GITHUB_WEBHOOK_SECRET`: Webhook secret for security
- `GEMINI_API_KEY`: Google Gemini API key for AI analysis
- `FLASK_ENV`: Environment setting (development/production)
- `PORT`: Server port (default: 5000)
- `LOG_LEVEL`: Logging level (INFO, DEBUG, etc.)

### Current Development Settings
- Running on port 5000 with placeholder credentials
- USE_REVIEWER_SERVER disabled (single-server mode)
- Development mode with debug enabled

## Technical Setup

### Dependencies
- Python 3.11
- Flask 3.0.3 for web server
- CrewAI 0.193.2 for AI agent orchestration
- Google Generative AI 0.8.3 for Gemini integration
- PyGithub 2.4.0 for GitHub API
- Gunicorn 23.0.0 for production deployment

### File Structure
```
src/ai_tech_lead_project/
├── watcher_server.py       # Main Flask server
├── reviewer_server.py      # Optional review posting service
├── crew.py                 # CrewAI orchestration
├── github_api.py          # GitHub API wrapper
├── review_handler.py      # Review formatting
├── result_adapter.py      # Data transformation
└── agents/                # AI agent implementations
    ├── reviewer_agent.py
    ├── tester_agent.py
    └── reporter_agent.py
```

## Deployment

- **Deployment Target**: VM (maintains server state)
- **Production Command**: Gunicorn with 2 workers, 300s timeout
- **Health Check**: Available at `/health` endpoint
- **Webhook Endpoint**: `/webhook` for GitHub integration

## Notes

- This is a GitHub App requiring real API credentials for production use
- Currently running in development mode with placeholder credentials
- The reviewer server component is optional and disabled in this setup
- AI analysis requires valid Gemini API key
- GitHub App installation required for webhook functionality