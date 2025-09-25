"""
AI Tech Lead - Reviewer Server
Flask server that receives CrewAI analysis results and posts automated code reviews on GitHub PRs.
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
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
    # Debug: log headers and request info
    try:
        logger.debug(f"Incoming request: {request.method} {request.path}")
        logger.debug(f"Content-Type: {request.headers.get('Content-Type')}")
        logger.debug(f"Content-Length: {request.headers.get('Content-Length')}")
        
        # Only log raw body for small payloads to avoid massive logs
        content_length = int(request.headers.get('Content-Length', 0))
        if content_length < 10000:  # Only log bodies smaller than 10KB
            raw_body = request.get_data(as_text=True)
            logger.debug(f"Request body: {raw_body[:2000]}{'...' if len(raw_body) > 2000 else ''}")
        else:
            logger.debug(f"Large payload received ({content_length} bytes), skipping body logging")
            
    except Exception as e:
        logger.warning(f"Failed to log request debug info: {e}")

    try:
        # Validate request content type
        if not request.headers.get('Content-Type', '').startswith('application/json'):
            logger.error(f"Invalid content type: {request.headers.get('Content-Type')}")
            return jsonify({
                'error': 'Content-Type must be application/json',
                'received': request.headers.get('Content-Type', 'none')
            }), 400
        
        # Parse JSON payload
        try:
            payload = request.get_json()
        except Exception as json_error:
            logger.error(f"Failed to parse JSON: {json_error}")
            return jsonify({
                'error': 'Invalid JSON payload',
                'details': str(json_error)
            }), 400
            
        if not payload:
            logger.error("Empty or null JSON payload")
            return jsonify({'error': 'Empty JSON payload'}), 400
        
        # Validate payload structure
        validation_error = _validate_review_payload(payload)
        if validation_error:
            logger.error(f"Payload validation failed: {validation_error}")
            return jsonify({'error': validation_error}), 400
        
        pr_info = payload['pr_info']
        analysis = payload['analysis']
        
        logger.info(f"Processing review for PR #{pr_info['number']} in {pr_info['repo_owner']}/{pr_info['repo_name']} (installation: {pr_info['installation_id']})")
        
        # Validate analysis data with review handler
        if not review_handler.validate_analysis(analysis):
            logger.warning("Analysis data appears invalid or empty, proceeding with fallback")
        
        # Transform analysis results into review comments
        review_data = review_handler.process_analysis(analysis, pr_info)
        
        if not review_data or not isinstance(review_data, dict):
            logger.error("Review handler returned invalid data")
            return jsonify({
                'error': 'Failed to process analysis data',
                'pr_number': pr_info['number']
            }), 500
        
        logger.info(f"Generated review data: event={review_data.get('event')}, comments={len(review_data.get('comments', []))}")
        
        # Post review to GitHub
        review_result = github_api.post_review(
            repo_owner=pr_info['repo_owner'],
            repo_name=pr_info['repo_name'],
            pr_number=pr_info['number'],
            installation_id=pr_info['installation_id'],
            review_data=review_data
        )
        
        if review_result.get('success'):
            response_data = {
                'message': 'Review posted successfully',
                'pr_number': pr_info['number'],
                'review_id': review_result.get('review_id'),
                'html_url': review_result.get('html_url'),
                'event': review_result.get('event'),
                'comments_count': review_result.get('comments_count', 0),
                'status': 'success'
            }
            logger.info(f"✅ Successfully posted review {review_result.get('review_id')} for PR #{pr_info['number']}")
            return jsonify(response_data), 200
        else:
            # Determine appropriate HTTP status code based on error type
            error_type = review_result.get('error_type', 'unknown')
            status_code = review_result.get('status_code', 500)
            
            if error_type == 'validation':
                status_code = 422
            elif error_type == 'connection':
                status_code = 503
            elif status_code in [403, 404, 422]:  # Pass through GitHub API status codes
                pass
            else:
                status_code = 500
            
            error_response = {
                'error': 'Failed to post review to GitHub',
                'details': review_result.get('error'),
                'pr_number': pr_info['number'],
                'error_type': error_type
            }
            
            # Include additional context for debugging
            if review_result.get('details'):
                error_response['github_details'] = review_result['details']
            
            logger.error(f"❌ Failed to post review for PR #{pr_info['number']}: {review_result.get('error')}")
            return jsonify(error_response), status_code
            
    except ValueError as e:
        logger.error(f"Validation error processing review: {str(e)}")
        return jsonify({
            'error': 'Invalid request data',
            'details': str(e)
        }), 400
    except ConnectionError as e:
        logger.error(f"Connection error processing review: {str(e)}")
        return jsonify({
            'error': 'GitHub API connection failed',
            'details': str(e)
        }), 503
    except Exception as e:
        logger.exception(f"Unexpected error processing review request: {str(e)}")
        return jsonify({
            'error': 'Internal server error',
            'details': str(e),
            'type': type(e).__name__
        }), 500


def _validate_review_payload(payload: Dict[str, Any]) -> Optional[str]:
    """Validate the review request payload structure.
    
    Args:
        payload: The JSON payload to validate
        
    Returns:
        None if valid, error message string if invalid
    """
    try:
        # Check top-level structure
        if not isinstance(payload, dict):
            return "Payload must be a JSON object"
            
        required_fields = ['pr_info', 'analysis']
        for field in required_fields:
            if field not in payload:
                return f"Missing required field: {field}"
        
        # Validate pr_info structure
        pr_info = payload['pr_info']
        if not isinstance(pr_info, dict):
            return "pr_info must be an object"
            
        pr_required_fields = {
            'number': int,
            'repo_owner': str,
            'repo_name': str,
            'installation_id': (int, str)  # Accept both int and string for installation_id
        }
        
        for field, expected_type in pr_required_fields.items():
            if field not in pr_info:
                return f"Missing required pr_info field: {field}"
            
            value = pr_info[field]
            if not isinstance(value, expected_type):
                return f"pr_info.{field} must be of type {expected_type.__name__ if not isinstance(expected_type, tuple) else ' or '.join(t.__name__ for t in expected_type)}"
            
            # Additional validation for specific fields
            if field == 'number' and value <= 0:
                return "pr_info.number must be a positive integer"
            elif field in ['repo_owner', 'repo_name'] and not str(value).strip():
                return f"pr_info.{field} cannot be empty"
                
        # Validate installation_id can be converted to int
        try:
            installation_id = int(pr_info['installation_id'])
            if installation_id <= 0:
                return "pr_info.installation_id must be a positive integer"
        except (ValueError, TypeError):
            return "pr_info.installation_id must be a valid integer"
        
        # Validate analysis structure (basic check)
        analysis = payload['analysis']
        if not isinstance(analysis, dict):
            return "analysis must be an object"
            
        # At least one of these should be present for meaningful analysis
        analysis_fields = ['issues', 'recommendations', 'summary', 'quality_score']
        if not any(field in analysis for field in analysis_fields):
            return f"analysis must contain at least one of: {', '.join(analysis_fields)}"
            
        # Validate quality_score if present
        if 'quality_score' in analysis:
            score = analysis['quality_score']
            if not isinstance(score, (int, float)):
                return "analysis.quality_score must be a number"
            if not (0 <= score <= 10):
                return "analysis.quality_score must be between 0 and 10"
        
        # Validate issues structure if present
        if 'issues' in analysis:
            issues = analysis['issues']
            if not isinstance(issues, list):
                return "analysis.issues must be an array"
                
        # Validate recommendations structure if present
        if 'recommendations' in analysis:
            recommendations = analysis['recommendations']
            if not isinstance(recommendations, list):
                return "analysis.recommendations must be an array"
        
        return None  # Valid
        
    except Exception as e:
        return f"Payload validation error: {str(e)}"


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
        logger.error("Please set the required GitHub App credentials:")
        logger.error("- GITHUB_APP_ID: Your GitHub App ID")
        logger.error("- GITHUB_APP_PRIVATE_KEY: Your GitHub App private key (PEM format)")
        exit(1)
    
    # Get port from environment or default to 5006 (avoiding conflicts)
    port = int(os.getenv('REVIEWER_PORT', 5006))
    debug = os.getenv('FLASK_ENV') == 'development'
    
    logger.info(f"Starting AI Tech Lead Reviewer Server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=debug)