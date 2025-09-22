"""
AI Tech Lead - Watcher Agent Server
Flask webhook server that listens for GitHub App events and triggers the CrewAI workflow.
"""

import os
import hmac
import hashlib
import json
import logging
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from crew import AITechLeadCrew

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# GitHub App configuration
WEBHOOK_SECRET = os.getenv('GITHUB_WEBHOOK_SECRET')
GITHUB_APP_ID = os.getenv('GITHUB_APP_ID')

def verify_github_signature(payload_body, signature):
    """Verify GitHub webhook signature for security."""
    if not WEBHOOK_SECRET:
        logger.error("GITHUB_WEBHOOK_SECRET not configured")
        return False
    
    if not signature:
        logger.error("No signature provided")
        return False
    
    # Create expected signature
    expected_signature = 'sha256=' + hmac.new(
        WEBHOOK_SECRET.encode(),
        payload_body,
        hashlib.sha256
    ).hexdigest()
    
    # Compare signatures securely
    return hmac.compare_digest(signature, expected_signature)

def extract_pr_info(payload):
    """Extract relevant PR information from GitHub webhook payload."""
    try:
        pr_data = payload.get('pull_request', {})
        return {
            'number': pr_data.get('number'),
            'title': pr_data.get('title'),
            'repo_name': payload.get('repository', {}).get('full_name'),
            'repo_owner': payload.get('repository', {}).get('owner', {}).get('login'),
            'repo_clone_url': payload.get('repository', {}).get('clone_url'),
            'pr_author': pr_data.get('user', {}).get('login'),
            'pr_url': pr_data.get('html_url'),
            'base_branch': pr_data.get('base', {}).get('ref'),
            'head_branch': pr_data.get('head', {}).get('ref'),
            'head_sha': pr_data.get('head', {}).get('sha'),
            'diff_url': pr_data.get('diff_url'),
            'patch_url': pr_data.get('patch_url'),
            'installation_id': payload.get('installation', {}).get('id')
        }
    except Exception as e:
        logger.error(f"Error extracting PR info: {e}")
        return None

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle GitHub webhook events."""
    
    # Verify signature
    signature = request.headers.get('X-Hub-Signature-256')
    if not verify_github_signature(request.data, signature):
        logger.error("Invalid webhook signature")
        return jsonify({'error': 'Invalid signature'}), 403
    
    # Get event type
    event_type = request.headers.get('X-GitHub-Event')
    payload = request.get_json()
    
    logger.info(f"Received {event_type} event")
    
    # Only process pull request events
    if event_type != 'pull_request':
        return jsonify({'message': f'Event {event_type} ignored'}), 200
    
    # Check if it's an opened or synchronize event (new PR or updated PR)
    action = payload.get('action')
    if action not in ['opened', 'synchronize']:
        return jsonify({'message': f'PR action {action} ignored'}), 200
    
    # Extract PR information
    pr_info = extract_pr_info(payload)
    if not pr_info:
        return jsonify({'error': 'Failed to extract PR information'}), 400
    
    logger.info(f"Processing PR #{pr_info['number']} from {pr_info['repo_name']}")
    
    try:
        # Initialize and run the CrewAI workflow
        crew = AITechLeadCrew()
        result = crew.kickoff(inputs=pr_info)
        
        logger.info(f"CrewAI workflow completed for PR #{pr_info['number']}")
        return jsonify({
            'message': 'PR analysis completed successfully',
            'pr_number': pr_info['number'],
            'status': 'success'
        }), 200
        
    except Exception as e:
        logger.error(f"Error processing PR #{pr_info['number']}: {str(e)}")
        return jsonify({
            'error': 'Failed to process PR',
            'pr_number': pr_info['number'],
            'details': str(e)
        }), 500

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'service': 'AI Tech Lead Watcher Agent',
        'version': '1.0.0'
    }), 200

@app.route('/', methods=['GET'])
def index():
    """Root endpoint with basic service info."""
    return jsonify({
        'service': 'AI Tech Lead - GitHub App Webhook Server',
        'description': 'Automated code review and unit testing using AI agents',
        'version': '1.0.0',
        'endpoints': {
            '/webhook': 'GitHub webhook endpoint',
            '/health': 'Health check endpoint'
        }
    }), 200

if __name__ == '__main__':
    # Check required environment variables
    required_env_vars = ['GITHUB_WEBHOOK_SECRET', 'GITHUB_APP_ID']
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {missing_vars}")
        exit(1)
    
    # Get port from environment or default to 5000
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_ENV') == 'development'
    
    logger.info(f"Starting AI Tech Lead Watcher Server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=debug)