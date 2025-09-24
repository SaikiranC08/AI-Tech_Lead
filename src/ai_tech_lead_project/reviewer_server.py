"""
AI Tech Lead - Reviewer Server
Flask server that receives CrewAI analysis results and posts automated code reviews on GitHub PRs.
"""

import os
import json
import logging
from datetime import datetime
from flask import Flask, request, jsonify
from dotenv import load_dotenv

from github_api import GitHubReviewAPI
from review_handler import ReviewHandler

# Load environment variables
load_dotenv()

# Configure logging
log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Initialize GitHub API and Review Handler
github_api = GitHubReviewAPI()
review_handler = ReviewHandler()


@app.route('/review', methods=['POST'])
def process_review():

    """
    Process CrewAI analysis results and post automated code review to GitHub PR.
    
    Expected JSON payload:
    {
        "pr_info": {
            "number": 123,
            "repo_owner": "username",
            "repo_name": "repository",
            "installation_id": 12345
        },
        "analysis": {
            "issues": [...],
            "recommendations": [...],
            "quality_score": 8.5,
            "summary": "..."
        }
    }
    """
    # Debug: log headers and raw body to diagnose incoming requests
    try:
        logger.debug(f"Incoming headers: {dict(request.headers)}")
        raw_body = request.get_data(as_text=True)
        logger.debug(f"Incoming raw body (truncated): {raw_body[:4000]}")
    except Exception as e:
        logger.debug(f"Failed to log raw request data: {e}")

    try:
        # Validate request content type
        if not request.is_json:
            return jsonify({'error': 'Content-Type must be application/json'}), 400
        
        payload = request.get_json()
        if not payload:
            return jsonify({'error': 'Empty JSON payload'}), 400
        
        # Validate required fields
        required_fields = ['pr_info', 'analysis']
        for field in required_fields:
            if field not in payload:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        pr_info = payload['pr_info']
        analysis = payload['analysis']
        
        # Validate PR info
        pr_required_fields = ['number', 'repo_owner', 'repo_name', 'installation_id']
        for field in pr_required_fields:
            if field not in pr_info:
                return jsonify({'error': f'Missing required pr_info field: {field}'}), 400
        
        logger.info(f"Processing review request for PR #{pr_info['number']} in {pr_info['repo_owner']}/{pr_info['repo_name']}")
        
        # Transform analysis results into review comments
        review_data = review_handler.process_analysis(analysis, pr_info)
        
        # Post review to GitHub
        review_result = github_api.post_review(
            repo_owner=pr_info['repo_owner'],
            repo_name=pr_info['repo_name'],
            pr_number=pr_info['number'],
            installation_id=pr_info['installation_id'],
            review_data=review_data
        )
        
        if review_result['success']:
            logger.info(f"Successfully posted review for PR #{pr_info['number']}")
            return jsonify({
                'message': 'Review posted successfully',
                'pr_number': pr_info['number'],
                'review_id': review_result.get('review_id'),
                'status': 'success'
            }), 200
        else:
            logger.error(f"Failed to post review for PR #{pr_info['number']}: {review_result['error']}")
            return jsonify({
                'error': 'Failed to post review',
                'details': review_result['error'],
                'pr_number': pr_info['number']
            }), 500
            
    except Exception as e:
        logger.error(f"Error processing review request: {str(e)}")
        return jsonify({
            'error': 'Internal server error',
            'details': str(e)
        }), 500


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    try:
        # Basic health check - verify GitHub API connectivity
        github_status = github_api.check_connectivity()
        
        return jsonify({
            'status': 'healthy' if github_status else 'degraded',
            'service': 'AI Tech Lead Reviewer Server',
            'version': '1.0.0',
            'timestamp': datetime.utcnow().isoformat(),
            'components': {
                'github_api': 'healthy' if github_status else 'unhealthy'
            }
        }), 200 if github_status else 503
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'service': 'AI Tech Lead Reviewer Server',
            'version': '1.0.0',
            'timestamp': datetime.utcnow().isoformat(),
            'error': str(e)
        }), 503


@app.route('/info', methods=['GET'])
def info():
    """Server metadata and configuration information."""
    return jsonify({
        'service': 'AI Tech Lead - Reviewer Server',
        'description': 'Automated code review posting service using CrewAI analysis results',
        'version': '1.0.0',
        'endpoints': {
            '/review': 'POST - Process CrewAI results and post GitHub review',
            '/health': 'GET - Health check endpoint',
            '/info': 'GET - Server metadata and configuration'
        },
        'configuration': {
            'log_level': os.getenv('LOG_LEVEL', 'INFO'),
            'port': os.getenv('REVIEWER_PORT', '5006'),
            'github_app_configured': bool(os.getenv('GITHUB_APP_ID'))
        },
        'timestamp': datetime.utcnow().isoformat()
    }), 200


@app.route('/', methods=['GET'])
def index():
    """Root endpoint redirect to info."""
    return info()


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({
        'error': 'Endpoint not found',
        'message': 'The requested endpoint does not exist',
        'available_endpoints': ['/review', '/health', '/info']
    }), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    logger.error(f"Internal server error: {str(error)}")
    return jsonify({
        'error': 'Internal server error',
        'message': 'An unexpected error occurred'
    }), 500


if __name__ == '__main__':
    # Check required environment variables
    required_env_vars = ['GITHUB_APP_ID', 'GITHUB_APP_PRIVATE_KEY']
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {missing_vars}")
        exit(1)
    
    # Get port from environment or default to 5006 (avoiding conflicts)
    port = int(os.getenv('REVIEWER_PORT', 5006))
    debug = os.getenv('FLASK_ENV') == 'development'
    
    logger.info(f"Starting AI Tech Lead Reviewer Server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=debug)