"""
GitHub API Integration Module
Handles GitHub App authentication and API interactions for posting code reviews.
"""

import os
import time
import jwt
import requests
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class GitHubReviewAPI:
    """GitHub API handler for posting automated code reviews."""
    
    def __init__(self):
        """Initialize GitHub API client with app credentials."""
        self.app_id = os.getenv('GITHUB_APP_ID')
        self.private_key = os.getenv('GITHUB_APP_PRIVATE_KEY')
        self.base_url = "https://api.github.com"
        
        # Validate required configuration
        if not self.app_id or not self.private_key:
            raise ValueError("GITHUB_APP_ID and GITHUB_APP_PRIVATE_KEY must be set")
        
        # Clean up private key format
        self.private_key = self.private_key.replace('\\n', '\n')
        
        # Cache for installation tokens
        self._token_cache = {}
    
    def _generate_jwt_token(self) -> str:
        """Generate JWT token for GitHub App authentication."""
        try:
            # JWT payload
            now = int(time.time())
            payload = {
                'iat': now - 60,  # Issued at time (60 seconds in the past to account for clock skew)
                'exp': now + (10 * 60),  # Expiration time (10 minutes from now)
                'iss': self.app_id  # Issuer (GitHub App ID)
            }
            
            # Generate JWT
            token = jwt.encode(payload, self.private_key, algorithm='RS256')
            logger.debug("Generated JWT token for GitHub App authentication")
            return token
            
        except Exception as e:
            logger.error(f"Failed to generate JWT token: {str(e)}")
            raise
    
    def _get_installation_token(self, installation_id: int) -> str:
        """Get installation access token for specific installation."""
        # Check cache first
        cache_key = f"token_{installation_id}"
        if cache_key in self._token_cache:
            token_data = self._token_cache[cache_key]
            # Check if token is still valid (with 5 minute buffer)
            if datetime.fromisoformat(token_data['expires_at'].replace('Z', '+00:00')) > datetime.now().astimezone() + timedelta(minutes=5):
                return token_data['token']
        
        try:
            # Generate JWT for app authentication
            jwt_token = self._generate_jwt_token()
            
            # Request installation token
            headers = {
                'Authorization': f'Bearer {jwt_token}',
                'Accept': 'application/vnd.github.v3+json',
                'User-Agent': 'AI-Tech-Lead-Reviewer/1.0.0'
            }
            
            response = requests.post(
                f"{self.base_url}/app/installations/{installation_id}/access_tokens",
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 201:
                token_data = response.json()
                # Cache the token
                self._token_cache[cache_key] = token_data
                logger.debug(f"Successfully obtained installation token for installation {installation_id}")
                return token_data['token']
            else:
                logger.error(f"Failed to get installation token. Status: {response.status_code}, Response: {response.text}")
                response.raise_for_status()
                
        except Exception as e:
            logger.error(f"Error getting installation token: {str(e)}")
            raise
    
    def check_connectivity(self) -> bool:
        """Check if GitHub API is accessible with current credentials."""
        try:
            jwt_token = self._generate_jwt_token()
            headers = {
                'Authorization': f'Bearer {jwt_token}',
                'Accept': 'application/vnd.github.v3+json',
                'User-Agent': 'AI-Tech-Lead-Reviewer/1.0.0'
            }
            
            response = requests.get(
                f"{self.base_url}/app",
                headers=headers,
                timeout=10
            )
            
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"GitHub API connectivity check failed: {str(e)}")
            return False
    
    def post_review(self, repo_owner: str, repo_name: str, pr_number: int, 
                   installation_id: int, review_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Post a code review to a GitHub pull request.
        
        Args:
            repo_owner: Repository owner username
            repo_name: Repository name
            pr_number: Pull request number
            installation_id: GitHub App installation ID
            review_data: Review data containing comments, event, and body
            
        Returns:
            Dict containing success status and review ID or error details
        """
        try:
            # Get installation token
            token = self._get_installation_token(installation_id)
            
            headers = {
                'Authorization': f'token {token}',
                'Accept': 'application/vnd.github.v3+json',
                'User-Agent': 'AI-Tech-Lead-Reviewer/1.0.0'
            }
            
            # Prepare review payload
            review_payload = {
                'body': review_data.get('body', ''),
                'event': review_data.get('event', 'COMMENT'),  # COMMENT, APPROVE, REQUEST_CHANGES
                'comments': review_data.get('comments', [])
            }
            
            # Only include comments if they exist and have required fields
            if review_payload['comments']:
                # Validate comment structure
                valid_comments = []
                for comment in review_payload['comments']:
                    if all(key in comment for key in ['path', 'line', 'body']):
                        valid_comments.append({
                            'path': comment['path'],
                            'line': comment['line'],
                            'body': comment['body']
                        })
                    else:
                        logger.warning(f"Skipping invalid comment: {comment}")
                
                review_payload['comments'] = valid_comments
            
            logger.info(f"Posting review to {repo_owner}/{repo_name}#{pr_number} with {len(review_payload.get('comments', []))} comments")
            
            # Make API request
            response = requests.post(
                f"{self.base_url}/repos/{repo_owner}/{repo_name}/pulls/{pr_number}/reviews",
                headers=headers,
                json=review_payload,
                timeout=30
            )

            if response.ok:
                try:
                    review_response = response.json()
                except ValueError:
                    review_response = {}
                review_id = review_response.get('id') or review_response.get('review', {}).get('id')
                html_url = review_response.get('html_url')
                logger.info(f"Successfully posted review {review_id} to PR #{pr_number}")
                return {
                    'success': True,
                    'review_id': review_id,
                    'html_url': html_url,
                    'raw_response': review_response
                }
            else:
                error_msg = f"GitHub API error: {response.status_code} - {response.text}"
                logger.error(error_msg)
                return {
                    'success': False,
                    'error': error_msg,
                    'status_code': response.status_code
                }


        except Exception as e:
            error_msg = f"Failed to post review: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg
            }
    
    def get_pull_request(self, repo_owner: str, repo_name: str, pr_number: int, 
                        installation_id: int) -> Optional[Dict[str, Any]]:
        """
        Get pull request details from GitHub.
        
        Args:
            repo_owner: Repository owner username
            repo_name: Repository name
            pr_number: Pull request number
            installation_id: GitHub App installation ID
            
        Returns:
            Dict containing PR details or None if failed
        """
        try:
            token = self._get_installation_token(installation_id)
            
            headers = {
                'Authorization': f'token {token}',
                'Accept': 'application/vnd.github.v3+json',
                'User-Agent': 'AI-Tech-Lead-Reviewer/1.0.0'
            }
            
            response = requests.get(
                f"{self.base_url}/repos/{repo_owner}/{repo_name}/pulls/{pr_number}",
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get PR details: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting PR details: {str(e)}")
            return None
    
    def get_pr_files(self, repo_owner: str, repo_name: str, pr_number: int,
                    installation_id: int) -> Optional[list]:
        """
        Get list of files changed in a pull request.
        
        Args:
            repo_owner: Repository owner username
            repo_name: Repository name
            pr_number: Pull request number
            installation_id: GitHub App installation ID
            
        Returns:
            List of changed files or None if failed
        """
        try:
            token = self._get_installation_token(installation_id)
            
            headers = {
                'Authorization': f'token {token}',
                'Accept': 'application/vnd.github.v3+json',
                'User-Agent': 'AI-Tech-Lead-Reviewer/1.0.0'
            }
            
            response = requests.get(
                f"{self.base_url}/repos/{repo_owner}/{repo_name}/pulls/{pr_number}/files",
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get PR files: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting PR files: {str(e)}")
            return None