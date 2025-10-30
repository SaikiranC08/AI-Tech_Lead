# 🤖 AI Tech Lead - GitHub App

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![CrewAI](https://img.shields.io/badge/CrewAI-Powered-green.svg)](https://github.com/joaomdmoura/crewAI)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An intelligent, installable GitHub App that automates code review and unit testing for pull requests using advanced AI agents powered by Google Gemini API and CrewAI framework.

## ✨ Features

- **🔍 AI-Powered Code Review**: Comprehensive analysis for style, bugs, security, and performance
- **🧪 Automated Unit Testing**: Generate and execute pytest tests for new functions
- **📝 Professional Reporting**: Detailed Markdown reports posted directly to PRs
- **🚀 Easy Installation**: One-click GitHub App installation - no server setup required
- **🆓 Student-Friendly**: Built for free-tier services (Gemini API, GitHub Student Pack)
- **🐳 Docker Ready**: Containerized for easy deployment
- **🏗️ Modular Architecture**: Clean separation of concerns with specialized agents

## 🏛️ Architecture

The system uses a streamlined multi-agent architecture powered by CrewAI:

```
┌─────────────────────────────────────────────────────────┐
│                    GitHub Webhook                       │
└─────────────────────────┬───────────────────────────────┘
                          │
                          ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Watcher       │    │    Reviewer      │    │    Tester       │
│   Server        │───▶│    Agent         │───▶│    Agent        │
│ (Background)    │    │  (Code Review)   │    │ (Unit Testing)  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                          │
                                                          ▼
                                                ┌─────────────────┐
                                                │    Reporter     │
                                                │     Agent       │
                                                │ (GitHub Posts)  │
                                                └─────────────────┘
```

### Component Responsibilities

- **🎯 Watcher Server**: Flask webhook server that receives GitHub PR events and runs agents in background
- **👨‍💻 Reviewer Agent**: AI-powered comprehensive code analysis using Gemini API
- **🧪 Tester Agent**: Generates pytest unit tests and executes them automatically
- **📊 Reporter Agent**: Creates professional Markdown reports and posts to GitHub PRs

### Key Features

- **Non-blocking webhooks**: Returns 202 Accepted immediately to avoid GitHub timeouts
- **Background processing**: AI analysis runs in separate threads
- **Consolidated reporting**: Single comprehensive report combining all analysis

## 🚀 Quick Start

### Prerequisites

- Python 3.10 (CPython) — recommended 3.10.13 to match the Dockerfile and dependencies
- Git
- GitHub account (preferably with Student Developer Pack)
- Google AI Studio account for Gemini API

Note on Python versions:
- If choosing between Python 3.10.11 and 3.13 for this project, use 3.10.11. This repo is built and tested on Python 3.10 (Dockerfile pins python:3.10-slim). Some AI/dependency stacks may not yet fully support Python 3.13.
- The preferred patch level is 3.10.13 (see .python-version). Any 3.10.x should generally work, but 3.10.13 is recommended.

### 1. Clone and Setup

```bash
git clone https://github.com/yourusername/ai-tech-lead-project.git
cd ai-tech-lead-project

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your API keys and configuration
nano .env  # or use your preferred editor
```

Required environment variables:
- `GEMINI_API_KEY`: Get from [Google AI Studio](https://ai.google.dev/)
- `GITHUB_APP_ID`: Your GitHub App ID
- `GITHUB_APP_PRIVATE_KEY`: Your GitHub App private key
- `GITHUB_WEBHOOK_SECRET`: Webhook secret for security

### 3. Run Locally

```bash
# Development server (single process)
python src/ai_tech_lead_project/watcher_server.py

# Or with Docker
docker-compose up --build

# The server runs on port 5001 by default (configurable via PORT env var)
```

### 4. GitHub App Setup

1. Go to GitHub Settings → Developer Settings → GitHub Apps → New GitHub App
2. Configure:
   - **App name**: AI Tech Lead
   - **Webhook URL**: Your public endpoint (use ngrok for development)
   - **Webhook secret**: Set in your `.env` file
   - **Permissions**: 
     - Pull requests: Read & Write
     - Issues: Write (for comments)
   - **Events**: Pull request
3. Install the app on your repositories

## 🐳 Docker Deployment

### Local Docker

```bash
# Build and run
docker build -t ai-tech-lead .
docker run --env-file .env -p 5000:5000 ai-tech-lead

# Or use docker-compose
docker-compose up -d
```

### Production Deployment

The application is designed to work with major cloud providers:

#### Heroku
```bash
# Create Heroku app
heroku create your-ai-tech-lead-app

# Set environment variables
heroku config:set GEMINI_API_KEY=your_key_here
heroku config:set GITHUB_APP_ID=your_app_id

# Deploy
git push heroku main
```

#### DigitalOcean App Platform
```yaml
# app.yaml
name: ai-tech-lead
services:
- name: web
  source_dir: /
  github:
    repo: your-username/ai-tech-lead-project
    branch: main
  run_command: gunicorn --worker-tmp-dir /dev/shm --config gunicorn_config.py src.ai_tech_lead_project.watcher_server:app
  environment_slug: python
  instance_count: 1
  instance_size_slug: basic-xxs
  envs:
  - key: GEMINI_API_KEY
    value: your_key_here
    type: SECRET
```

## 📚 API Documentation

### Webhook Endpoints

#### `POST /webhook`
Receives GitHub webhook events for pull requests.

**Headers:**
- `X-GitHub-Event`: Event type
- `X-Hub-Signature-256`: HMAC signature

**Events Processed:**
- `pull_request.opened`
- `pull_request.synchronize`

#### `GET /health`
Health check endpoint for monitoring.

**Response:**
```json
{
  "status": "healthy",
  "service": "AI Tech Lead Watcher Agent",
  "version": "1.0.0"
}
```

## 🛠️ Development

### Project Structure

```
ai-tech-lead-project/
├── src/
│   └── ai_tech_lead_project/
│       ├── agents/
│       │   ├── reviewer_agent.py
│       │   ├── tester_agent.py
│       │   └── reporter_agent.py
│       ├── crew.py
│       └── watcher_server.py
├── tests/
├── docs/
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

### Adding New Features

1. **New Analysis Types**: Extend the Reviewer Agent with additional analysis categories
2. **Test Frameworks**: Add support for other testing frameworks beyond pytest
3. **Language Support**: Extend beyond Python to support other languages
4. **Integrations**: Add support for other CI/CD platforms

### Testing

```bash
# Run tests
pytest tests/

# With coverage
pytest tests/ --cov=src --cov-report=html

# Test specific agent
pytest tests/test_reviewer_agent.py -v
```

## 🎓 Free-Tier Resources

This project is optimized for students using free-tier services:

| Resource | Provider | How to Get |
|----------|----------|------------|
| GitHub Pro | GitHub | [Student Developer Pack](https://education.github.com/pack) |
| Copilot Pro | GitHub | Student Developer Pack |
| Gemini API | Google | [AI Studio](https://ai.google.dev/) (Free tier available) |
| Cloud Credits | Various | Student Developer Pack (Azure, AWS, DigitalOcean) |

## 🔒 Security

- **Webhook Verification**: All GitHub webhooks are cryptographically verified
- **Environment Variables**: Sensitive data stored securely in environment variables
- **Private Key Handling**: GitHub App private keys are never logged or exposed
- **Rate Limiting**: Built-in respect for GitHub API rate limits
- **Docker Security**: Non-root user in Docker containers

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for details.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📋 Roadmap

- [ ] **Multi-language Support**: JavaScript, Go, Java analysis
- [ ] **Advanced Testing**: Integration test generation
- [ ] **Performance Metrics**: Code complexity analysis
- [ ] **Security Scanning**: Vulnerability detection
- [ ] **Custom Rules**: Repository-specific analysis rules
- [ ] **Team Analytics**: Aggregate code quality metrics

## 🐛 Troubleshooting

### Common Issues

**"Invalid webhook signature"**
- Verify `GITHUB_WEBHOOK_SECRET` matches your GitHub App configuration
- Ensure the webhook URL is accessible from GitHub

**"GEMINI_API_KEY environment variable is required"**
- Set up your Gemini API key from Google AI Studio
- Verify the key is correctly set in your `.env` file

**"Failed to post PR comment"**
- Check GitHub App permissions (Pull requests: Write, Issues: Write)
- Verify the app is installed on the target repository

### Debug Mode

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
python src/ai_tech_lead_project/watcher_server.py
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [CrewAI](https://github.com/joaomdmoura/crewAI) for the multi-agent framework
- [Google Gemini](https://ai.google.dev/) for AI capabilities  
- [GitHub Student Developer Pack](https://education.github.com/pack) for free resources
- [PyGithub](https://github.com/PyGithub/PyGithub) for GitHub API integration

## 📞 Support

- **Documentation**: Check this README and inline code comments
- **Issues**: Open a GitHub issue for bugs or feature requests
- **Discussions**: Use GitHub Discussions for questions and community support

---

<div align="center">

**Built with ❤️ for the developer community**

[🚀 Get Started](#-quick-start) • [📚 Documentation](#-api-documentation) • [🤝 Contribute](#-contributing) • [📞 Support](#-support)

</div>