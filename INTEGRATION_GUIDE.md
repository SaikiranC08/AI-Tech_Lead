# AI Tech Lead - Complete Integration Guide

This guide covers the complete integrated AI Tech Lead system that automatically reviews GitHub pull requests using CrewAI analysis and posts structured reviews.

## 🏗️ System Architecture

```
GitHub PR → Watcher Server → CrewAI Agents → Result Adapter → Reviewer Server → GitHub Review
    ↓            ↓               ↓              ↓               ↓              ↓
 Webhook     Flask(5000)    AI Analysis    Transform       Flask(5001)    Posted Review
```

### Components

1. **Watcher Server** (`port 5000`) - Receives GitHub webhooks, triggers CrewAI
2. **CrewAI Workflow** - Three AI agents analyze code (Reviewer, Tester, Reporter)
3. **Result Adapter** - Transforms CrewAI output to Reviewer Server format
4. **Reviewer Server** (`port 5001`) - Posts structured GitHub reviews
5. **GitHub Integration** - GitHub App with webhook and review capabilities

## 🚀 Quick Start

### 1. Environment Setup

```bash
# Clone or navigate to project
cd ai-tech-lead-project

# Copy environment configuration
cp .env.example .env

# Edit .env with your credentials
nano .env
```

Required environment variables:
```bash
# GitHub App Configuration
GITHUB_APP_ID=your_app_id
GITHUB_APP_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----"
GITHUB_WEBHOOK_SECRET=your_webhook_secret

# AI Configuration
GEMINI_API_KEY=your_gemini_api_key

# Server Configuration
PORT=5000                              # Watcher Server
REVIEWER_PORT=5001                     # Reviewer Server
REVIEWER_SERVER_URL=http://localhost:5001
USE_REVIEWER_SERVER=true               # Enable integration

# Logging
LOG_LEVEL=INFO
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Start the System

```bash
# Start both servers
./scripts/start_servers.sh

# Or start individually:
# Terminal 1: python src/ai_tech_lead_project/reviewer_server.py
# Terminal 2: python src/ai_tech_lead_project/watcher_server.py
```

### 4. Test the Integration

```bash
# Run comprehensive integration tests
python3 scripts/test_integration.py

# Test individual components
curl http://localhost:5000/health  # Watcher Server
curl http://localhost:5001/health  # Reviewer Server

# Test review posting
curl -X POST http://localhost:5001/review \
  -H "Content-Type: application/json" \
  -d @examples/reviewer_test_payloads.json
```

### 5. Stop the System

```bash
./scripts/stop_servers.sh
```

## 🔄 Complete Workflow

### 1. GitHub Webhook Trigger
```
GitHub PR (opened/updated) → POST /webhook → Watcher Server
```

### 2. CrewAI Analysis
```python
# Watcher Server extracts PR info and triggers CrewAI
pr_info = extract_pr_info(webhook_payload)
crew = AITechLeadCrew()
crew_results = crew.kickoff(inputs=pr_info)

# CrewAI Results Format:
{
    'pr_info': {...},
    'review_results': {
        'style_issues': [...],
        'potential_bugs': [...],
        'security_concerns': [...],
        'positive_aspects': [...],
        'summary': '...'
    },
    'test_results': {
        'overall_status': 'PASSED|FAILED|ERROR|SKIPPED',
        'test_files': [...],
        'summary': '...'
    },
    'status': 'completed|error'
}
```

### 3. Result Transformation
```python
# Result Adapter transforms CrewAI output
adapter = CrewAIResultAdapter()
reviewer_payload = adapter.transform_crew_results(crew_results)

# Reviewer Server Format:
{
    'pr_info': {
        'number': 123,
        'repo_owner': 'username',
        'repo_name': 'repository',
        'installation_id': 12345
    },
    'analysis': {
        'quality_score': 7.5,        # 0-10 calculated score
        'summary': '...',             # Generated summary
        'issues': [{                  # Transformed issues
            'title': 'SQL Injection Risk',
            'description': '...',
            'severity': 'critical',
            'category': 'security',
            'file': 'auth.py',
            'line': 45,
            'suggestion': '...'
        }],
        'recommendations': [{         # Generated recommendations
            'title': 'Add Unit Tests',
            'description': '...',
            'category': 'testing',
            'priority': 'high',
            'benefits': '...'
        }]
    }
}
```

### 4. GitHub Review Posting
```python
# Reviewer Server posts structured review
github_api.post_review(
    repo_owner, repo_name, pr_number, 
    installation_id, review_data
)

# Review Decision Logic:
# - APPROVE: quality_score >= 8.5, no critical issues
# - REQUEST_CHANGES: critical issues OR quality_score < 6.0
# - COMMENT: neutral feedback
```

### 5. GitHub Review Output

The system posts rich, structured reviews to GitHub:

#### Main Review Comment
```markdown
## 🤖 Automated Code Review

✨ **Quality Score: 7.5/10**

### 📋 Summary
This pull request introduces new authentication features with good structure, 
but has security concerns that should be addressed before merging.

### 🔍 Issues Found
- **Total Issues:** 3
- **Critical Issues:** 1 🔴
- **High Priority Issues:** 1 🟠

**Issues by Category:**
- 🔐 Security: 2 issues
- 💅 Code Style: 1 issue

### 💡 Key Recommendations
1. Add comprehensive unit tests for authentication module
2. Implement rate limiting for security
3. Review and fix SQL injection vulnerability

---
🤖 *Generated by AI Tech Lead at 2024-01-01 12:00:00 UTC*
💬 This review was automatically generated. Please review suggestions and apply as needed.
```

#### Line-Specific Comments
```markdown
🔴 🔐 **SQL Injection Vulnerability**

The user input is directly concatenated into the SQL query without proper sanitization.

**💡 Suggested Fix:**
Use parameterized queries or an ORM to prevent SQL injection attacks.

**Example:**
```python
cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
```

**📚 References:** https://owasp.org/www-community/attacks/SQL_Injection
```

## ⚙️ Configuration Options

### Integration Settings

```bash
# .env configuration
USE_REVIEWER_SERVER=true          # Enable/disable integration
REVIEWER_SERVER_URL=http://localhost:5001  # Reviewer Server URL

# Quality Score Thresholds (can be customized in review_handler.py)
# APPROVE: >= 8.5
# REQUEST_CHANGES: < 6.0 or critical issues
# COMMENT: neutral feedback
```

### Logging Configuration

```bash
LOG_LEVEL=INFO                    # DEBUG, INFO, WARNING, ERROR
# LOG_FILE=/path/to/logfile.log   # Optional log file
```

### Server Configuration

```bash
PORT=5000                         # Watcher Server port
REVIEWER_PORT=5001                # Reviewer Server port
FLASK_ENV=development             # development or production
```

## 🧪 Testing & Debugging

### Integration Test Suite

```bash
# Run complete test suite
python3 scripts/test_integration.py

# Test output:
🚀 AI Tech Lead Integration Test Suite
==================================================
⚙️ Checking environment configuration...
✅ All required environment variables are set

🧪 Testing Result Adapter...
✅ Adapter transformation successful
   Quality Score: 6.0
   Issues Count: 3
   Recommendations Count: 4

🌐 Testing Reviewer Server connection...
✅ Reviewer Server is healthy: healthy

🌐 Testing Watcher Server connection...
✅ Watcher Server is healthy: healthy

📝 Testing Reviewer Server with sample data...
✅ Review posted successfully!
   Review ID: 123456789
   Status: success
```

### Individual Component Testing

```bash
# Test Reviewer Server standalone
cd examples
./test_reviewer_server.sh

# Test with different payloads
curl -X POST http://localhost:5001/review \
  -H "Content-Type: application/json" \
  -d '{
    "pr_info": {"number": 123, "repo_owner": "test", "repo_name": "test", "installation_id": 12345},
    "analysis": {"quality_score": 8.0, "summary": "Test review", "issues": [], "recommendations": []}
  }'
```

### Debugging Common Issues

#### 1. Environment Variables Missing
```bash
❌ Missing required environment variables: GITHUB_APP_ID, GITHUB_APP_PRIVATE_KEY
```
**Solution:** Copy `.env.example` to `.env` and configure with real credentials.

#### 2. GitHub API Authentication Failed
```bash
❌ GitHub API connectivity check failed
```
**Solutions:**
- Verify `GITHUB_APP_ID` matches your GitHub App
- Check `GITHUB_APP_PRIVATE_KEY` format (must include `\n` for line breaks)
- Ensure GitHub App has required permissions

#### 3. Servers Can't Connect
```bash
❌ Failed to connect to Reviewer Server: Connection refused
```
**Solutions:**
- Check if servers are running: `ps aux | grep python`
- Verify ports are available: `lsof -i :5000` and `lsof -i :5001`
- Check server logs: `tail -f logs/watcher_server.log`

#### 4. Review Not Posted to GitHub
**Debug steps:**
1. Check Reviewer Server logs for GitHub API errors
2. Verify `installation_id` is correct for the repository
3. Ensure GitHub App is installed on target repository
4. Confirm GitHub App has "Pull requests: Write" permission

### Log Analysis

```bash
# Watch server logs in real-time
tail -f logs/watcher_server.log
tail -f logs/reviewer_server.log

# Search for errors
grep -i error logs/*.log

# View recent webhook events
grep -i "webhook" logs/watcher_server.log | tail -10
```

## 🔧 Customization

### Custom Review Logic

Edit `src/ai_tech_lead_project/review_handler.py`:

```python
def _determine_review_event(self, issues: List[Dict], quality_score: float) -> str:
    # Custom logic for APPROVE/REQUEST_CHANGES/COMMENT
    if quality_score >= 9.0 and not issues:
        return 'APPROVE'
    elif any(issue.get('severity') == 'critical' for issue in issues):
        return 'REQUEST_CHANGES'
    else:
        return 'COMMENT'
```

### Custom Quality Score Calculation

Edit `src/ai_tech_lead_project/result_adapter.py`:

```python
def _calculate_quality_score(self, review_results, test_results) -> float:
    score = 10.0
    # Custom scoring logic
    score -= (critical_issues * 3.0)  # Stricter penalties
    score += (positive_aspects * 0.2)  # More credit for good practices
    return max(0.0, min(10.0, score))
```

### Custom Categories and Emojis

Edit category mappings in `review_handler.py`:

```python
self.category_emojis = {
    'security': '🛡️',
    'performance': '⚡',
    'maintainability': '🔧',
    'custom_category': '🎯'  # Add custom categories
}
```

## 🚀 Production Deployment

### Docker Deployment

Create `docker-compose.yml`:

```yaml
version: '3.8'
services:
  watcher:
    build: .
    command: python src/ai_tech_lead_project/watcher_server.py
    ports:
      - "5000:5000"
    env_file:
      - .venv/gitignore/.env

  reviewer:
    build: .
    command: python src/ai_tech_lead_project/reviewer_server.py
    ports:
      - "5001:5001"
    env_file:
      - .venv/gitignore/.env
```

### GitHub App Configuration

1. **Create GitHub App** at https://github.com/settings/apps/new
2. **Set Webhook URL:** `https://your-domain.com/webhook`
3. **Configure Permissions:**
   - Pull requests: Read & Write
   - Contents: Read
   - Metadata: Read
4. **Subscribe to Events:** Pull request
5. **Generate Private Key** and add to `.env`

### ngrok for Testing

```bash
# Install ngrok
brew install ngrok  # macOS
# or download from https://ngrok.com/

# Start ngrok tunnel
ngrok http 5000

# Use the HTTPS URL for GitHub webhook
# Example: https://abc123.ngrok.io/webhook
```

### Health Monitoring

```bash
# Add to your monitoring system
curl -f http://localhost:5000/health || alert "Watcher Server Down"
curl -f http://localhost:5001/health || alert "Reviewer Server Down"
```

## 📊 Metrics & Analytics

### Key Metrics to Monitor

1. **Review Success Rate** - Percentage of successful review posts
2. **Processing Time** - Time from webhook to review posting
3. **Quality Score Distribution** - Average quality scores over time
4. **Issue Categories** - Most common types of issues found
5. **GitHub API Rate Limits** - Monitor API usage

### Sample Monitoring Setup

```python
# Add to your servers
import logging
import time
from datetime import datetime

# Metrics collection
def track_review_metrics(pr_number, quality_score, processing_time, success):
    metrics = {
        'timestamp': datetime.utcnow().isoformat(),
        'pr_number': pr_number,
        'quality_score': quality_score,
        'processing_time_seconds': processing_time,
        'success': success
    }
    # Send to your monitoring system (e.g., CloudWatch, DataDog, etc.)
    logger.info(f"METRICS: {metrics}")
```

## 🎯 Best Practices

### Security
- Never commit real credentials to version control
- Use environment variables for all secrets
- Rotate GitHub App private keys regularly
- Implement webhook signature verification
- Use HTTPS in production

### Performance
- Monitor GitHub API rate limits
- Implement proper error handling and retries
- Cache GitHub installation tokens
- Use background job processing for large repos
- Monitor server resource usage

### Reliability
- Implement proper logging at all levels
- Set up health checks and monitoring
- Handle network failures gracefully
- Provide clear error messages
- Test with various PR scenarios

### Code Quality
- Follow the same standards your AI enforces
- Write comprehensive tests
- Document configuration options
- Use type hints throughout
- Regular dependency updates

## 🆘 Support & Troubleshooting

### Getting Help

1. **Check Logs:** Always start with server logs
2. **Run Integration Tests:** Use `python3 scripts/test_integration.py`
3. **Verify Configuration:** Ensure all environment variables are set
4. **Test Components Individually:** Use the provided test scripts
5. **Check GitHub App Setup:** Verify permissions and webhook configuration

### Common Solutions

| Issue | Solution |
|-------|----------|
| Webhook not received | Check ngrok tunnel, verify webhook URL |
| Review not posted | Verify GitHub App permissions and installation |
| Server crashes | Check logs, verify dependencies installed |
| High processing time | Monitor AI API response times, optimize prompts |
| Rate limit exceeded | Implement exponential backoff, monitor usage |

---

## 🎉 Congratulations!

You now have a complete AI-powered code review system! The integration automatically:

- ✅ Receives GitHub webhook events
- ✅ Analyzes code using multiple AI agents  
- ✅ Transforms results into structured reviews
- ✅ Posts professional reviews to GitHub PRs
- ✅ Provides intelligent approve/request changes decisions

Your AI Tech Lead is ready to help maintain code quality across your projects! 🚀