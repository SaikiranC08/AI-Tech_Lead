
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
from threading import Thread
from typing import Dict, Any, Optional

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
REVIEWER_SERVER_URL = os.getenv('REVIEWER_SERVER_URL', 'http://localhost:5006/review')
USE_REVIEWER_SERVER = os.getenv('USE_REVIEWER_SERVER', 'true').lower() == 'true'

# Initialize result adapter
result_adapter = CrewAIResultAdapter()

# Initialize the Code Review Crew
code_review_crew = AITechLeadCrew()

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

def send_to_reviewer_server(crew_results, pr_info):
    """Transforms and sends the analysis results to the reviewer server."""
    try:
        # Adapt the raw CrewAI results into the structured format the reviewer expects
        reviewer_payload = result_adapter.transform_crew_results(crew_results, pr_info)

        # Log the outgoing payload
        try:
            pretty_payload = json.dumps(reviewer_payload, indent=2)
            logger.info(f"Posting to Reviewer Server at {REVIEWER_SERVER_URL}; payload (truncated):\n{pretty_payload[:2000]}")
        except Exception:
            logger.info("Posting to Reviewer Server (payload could not be serialized for logging)")

        # Send to Reviewer Server
        response = requests.post(
            REVIEWER_SERVER_URL,
            json=reviewer_payload,
            headers={'Content-Type': 'application/json'},
            timeout=60  # Increased timeout for potentially larger payloads
        )

        logger.info(f"Reviewer Server responded: {response.status_code} - {response.text[:500]}")

        if response.ok:
            return {'success': True, 'result': response.json()}
        else:
            error_msg = f"Reviewer Server error: {response.status_code} - {response.text}"
            logger.error(error_msg)
            return {'success': False, 'error': error_msg}

    except requests.exceptions.RequestException as e:
        logger.exception(f"Failed to connect to Reviewer Server at {REVIEWER_SERVER_URL}: {str(e)}")
        return {'success': False, 'error': f"Failed to connect to Reviewer Server: {str(e)}"}
    except Exception as e:
        logger.exception(f"Error sending to Reviewer Server: {str(e)}")
        return {'success': False, 'error': f"Error sending to Reviewer Server: {str(e)}"}


def extract_pr_info(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extracts PR information from 'pull_request' or 'check_suite' webhook payloads."""
    event_type = payload.get('action')
    
    try:
        if 'pull_request' in payload:
            # Handling 'pull_request' events (opened, reopened, synchronize)
            pr = payload['pull_request']
            repo = payload['repository']
            
            return {
                'number': pr['number'],
                'url': pr['html_url'],
                'repo_owner': repo['owner']['login'],
                'repo_name': repo['name'],  # Correctly use 'name'
                'installation_id': payload.get('installation', {}).get('id'),
                'diff_url': pr['diff_url'],
                'clone_url': repo['clone_url'],
                'branch': pr['head']['ref']
            }
            
        elif 'check_suite' in payload and payload.get('check_suite', {}).get('pull_requests'):
            # Handling 'check_suite' events (typically for pushes to a PR branch)
            check_suite = payload['check_suite']
            pr = check_suite['pull_requests'][0]  # Use the first associated PR
            repo = payload['repository']
            
            return {
                'number': pr['number'],
                'url': f"{repo['html_url']}/pull/{pr['number']}", # Construct URL
                'repo_owner': repo['owner']['login'],
                'repo_name': repo['name'],  # Correctly use 'name' instead of 'full_name'
                'installation_id': payload.get('installation', {}).get('id'),
                'diff_url': f"{repo['html_url']}/pull/{pr['number']}.diff", # Construct diff URL
                'clone_url': repo['clone_url'],
                'branch': pr['head']['ref'] if 'head' in pr else None # Branch might not be in this payload
            }
            
    except (KeyError, IndexError) as e:
        logger.error(f"Failed to extract PR info from payload due to missing key: {e}")
        return None
        
    return None


def verify_signature(payload_body, signature_header):
    """Verify that the payload was sent from GitHub."""
    if not signature_header:
        return False
    hash_object = hmac.new(WEBHOOK_SECRET.encode('utf-8'), msg=payload_body, digestmod=hashlib.sha256)
    expected_signature = "sha256=" + hash_object.hexdigest()
    return hmac.compare_digest(expected_signature, signature_header)

def process_pr_event(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Processes a pull request event by extracting relevant information and
    triggering the CrewAI workflow.
    """
    pr_info = extract_pr_info(payload)
    if not pr_info:
        logger.warning("Could not extract PR info from payload.")
        return {'success': False, 'error': 'Could not extract PR info.'}

    action = payload.get('action')
    if action not in ['opened', 'reopened', 'synchronize']:
        logger.info(f"Ignoring PR event with action: {action}")
        return {'success': True, 'message': f"Event action '{action}' ignored."}

    logger.info(f"Processing PR #{pr_info['number']} with action '{action}'")

    try:
        # Asynchronously run the crew and send results
        run_crew_and_send_results(pr_info)
        return {'success': True, 'message': f"CrewAI task for PR #{pr_info['number']} started."}
    except Exception as e:
        logger.exception(f"Failed to start CrewAI task for PR #{pr_info['number']}: {str(e)}")
        return {'success': False, 'error': f"Internal server error: {str(e)}"}

def run_crew_and_send_results(pr_info):
    """Runs the CrewAI workflow and sends results to reviewer server."""
    try:
        # Run the CrewAI workflow
        crew_results = code_review_crew.kickoff(pr_info)
        
        # Send results to reviewer server
        review_response = send_to_reviewer_server(crew_results, pr_info)
        
        if review_response['success']:
            logger.info(f"Successfully sent review to Reviewer Server for PR #{pr_info['number']}")
        else:
            logger.error(f"Failed to send review to Reviewer Server for PR #{pr_info['number']}: {review_response['error']}")
            
    except Exception as e:
        logger.exception(f"Error in crew execution for PR #{pr_info['number']}: {str(e)}")

@app.route('/webhook', methods=['POST'])
def github_webhook():
    """
    Listen for GitHub webhooks, filter for relevant PR events, and trigger the reviewer.
    """
    # Verify webhook signature for security
    if WEBHOOK_SECRET:
        signature = request.headers.get('X-Hub-Signature-256')
        if not verify_signature(request.data, signature):
            logger.warning("Invalid webhook signature.")
            return jsonify({'error': 'Invalid signature'}), 403

    event = request.headers.get('X-GitHub-Event', 'ping')
    if event == 'ping':
        logger.info("Received ping event from GitHub.")
        return jsonify({'msg': 'pong'}), 200

    # We are now interested in 'check_suite' as well to trigger on pushes to a PR branch
    if event not in ['pull_request', 'check_suite']:
        logger.info(f"Ignoring '{event}' event.")
        return jsonify({'msg': f"Ignoring '{event}' event."}), 200

    try:
        payload = request.get_json()
        
        # Determine action and if we should proceed
        action = payload.get('action')
        if event == 'pull_request' and action not in ['opened', 'reopened', 'synchronize']:
            logger.info(f"Ignoring pull_request action: '{action}'")
            return jsonify({'msg': f"Ignoring PR action: '{action}'"}), 200
        
        if event == 'check_suite' and action != 'requested':
             logger.info(f"Ignoring check_suite action: '{action}'")
             return jsonify({'msg': f"Ignoring check_suite action: '{action}'"}), 200

        # Extract PR info from payload (this now handles both event types)
        pr_info = extract_pr_info(payload)
        
        if not pr_info:
            logger.warning("Could not extract PR info from payload.")
            return jsonify({'error': 'Could not extract PR information'}), 400

        # Trigger the CrewAI workflow
        logger.info(f"Starting CrewAI workflow for PR #{pr_info['number']} in {pr_info['repo_owner']}/{pr_info['repo_name']}")
        
        # Run the CrewAI workflow
        crew_results = code_review_crew.kickoff(pr_info)
        
        # Send results to reviewer server
        review_response = send_to_reviewer_server(crew_results, pr_info)
        
        if review_response['success']:
            logger.info(f"Successfully sent review to Reviewer Server for PR #{pr_info['number']}")
            return jsonify({
                'status': 'review_sent',
                'pr_number': pr_info['number'],
                'review_id': review_response['result'].get('review_id')
            }), 200
        else:
            logger.error(f"Failed to send review to Reviewer Server for PR #{pr_info['number']}: {review_response['error']}")
            return jsonify({'error': 'Failed to send review to Reviewer Server'}), 500

    except Exception as e:
        logger.exception(f"Error processing webhook: {e}")
        return jsonify({'error': 'Internal server error'}), 500

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
