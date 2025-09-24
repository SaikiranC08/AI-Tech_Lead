"""
AI Tech Lead - Watcher Agent Server
Flask webhook server that listens for GitHub App events and triggers the CrewAI workflow.
"""

import os
import hmac
import hashlib
import json
import logging
import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from crew import AITechLeadCrew
from result_adapter import CrewAIResultAdapter

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# GitHub App configuration
WEBHOOK_SECRET = os.getenv('GITHUB_WEBHOOK_SECRET')
GITHUB_APP_ID = os.getenv('GITHUB_APP_ID')

# Reviewer Server configuration
REVIEWER_SERVER_URL = os.getenv('REVIEWER_SERVER_URL', 'http://localhost:5006')
USE_REVIEWER_SERVER = os.getenv('USE_REVIEWER_SERVER', 'true').lower() == 'true'

# Initialize result adapter
result_adapter = CrewAIResultAdapter()

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

def send_to_reviewer_server(crew_results):
    """Send CrewAI results to the Reviewer Server for GitHub review posting."""
    if not USE_REVIEWER_SERVER:
        logger.info("Reviewer Server integration disabled")
        return {'success': False, 'reason': 'disabled'}

    try:
        # Transform CrewAI results to Reviewer Server format
        reviewer_payload = result_adapter.transform_crew_results(crew_results)

        # Log the outgoing payload (truncate to avoid huge logs)
        try:
            pretty_payload = json.dumps(reviewer_payload)
            logger.info(f"Posting to Reviewer Server at {REVIEWER_SERVER_URL}/review; payload (truncated): {pretty_payload[:2000]}")
        except Exception:
            logger.info("Posting to Reviewer Server (payload could not be serialized for logging)")

        # Send to Reviewer Server
        response = requests.post(
            f"{REVIEWER_SERVER_URL}/review",
            json=reviewer_payload,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )

        logger.info(f"Reviewer Server responded: {response.status_code} - {response.text[:2000]}")

        # Treat any 2xx as success
        if response.ok:
            try:
                result = response.json()
            except ValueError:
                result = {'raw_text': response.text}
            logger.info(f"Successfully sent review to Reviewer Server: {result.get('review_id') or result.get('review_id')}")
            return {'success': True, 'result': result}
        else:
            error_msg = f"Reviewer Server error: {response.status_code} - {response.text}"
            logger.error(error_msg)
            return {'success': False, 'error': error_msg}

    except requests.exceptions.RequestException as e:
        # Provide more details about connection issues
        logger.exception(f"Failed to connect to Reviewer Server at {REVIEWER_SERVER_URL}: {str(e)}")
        error_msg = f"Failed to connect to Reviewer Server: {str(e)}"
        return {'success': False, 'error': error_msg}
    except Exception as e:
        logger.exception(f"Error sending to Reviewer Server: {str(e)}")
        error_msg = f"Error sending to Reviewer Server: {str(e)}"
        return {'success': False, 'error': error_msg}


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
        
        # Send results to Reviewer Server for GitHub review posting
        reviewer_result = send_to_reviewer_server(result)
        
        # Prepare response based on both CrewAI and Reviewer Server results
        response_data = {
            'message': 'PR analysis completed successfully',
            'pr_number': pr_info['number'],
            'status': 'success',
            'crew_status': result.get('status', 'unknown'),
            'reviewer_server': {
                'enabled': USE_REVIEWER_SERVER,
                'success': reviewer_result.get('success', False)
            }
        }
        
        # Add reviewer server details if successful
        if reviewer_result.get('success'):
            response_data['reviewer_server']['review_id'] = reviewer_result.get('result', {}).get('review_id')
        elif reviewer_result.get('error'):
            response_data['reviewer_server']['error'] = reviewer_result.get('error')
            
        return jsonify(response_data), 200
        
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
    
    # Get port from environment or default to 5001 (avoiding macOS AirPlay)
    port = int(os.getenv('PORT', 5001))
    debug = os.getenv('FLASK_ENV') == 'development'
    
    logger.info(f"Starting AI Tech Lead Watcher Server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=debug)
