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
        
        # Properly format private key - handle multiple escape patterns
        self.private_key = self._format_private_key(self.private_key)
        
        # Cache for installation tokens
        self._token_cache = {}
        
        logger.info(f"GitHub API initialized for App ID: {self.app_id}")
    
    def _format_private_key(self, private_key: str) -> str:
        """Properly format private key from environment variable."""
        try:
            # Handle different escape patterns
            key = private_key.replace('\\n', '\n').replace('\\r', '\r')
            
            # Ensure proper formatting
            if not key.startswith('-----BEGIN'):
                logger.error("Private key does not start with proper header")
                raise ValueError("Invalid private key format")
            
            # Add newline after BEGIN header if missing
            if '-----BEGIN RSA PRIVATE KEY-----' in key and not '-----BEGIN RSA PRIVATE KEY-----\n' in key:
                key = key.replace('-----BEGIN RSA PRIVATE KEY-----', '-----BEGIN RSA PRIVATE KEY-----\n')
            elif '-----BEGIN PRIVATE KEY-----' in key and not '-----BEGIN PRIVATE KEY-----\n' in key:
                key = key.replace('-----BEGIN PRIVATE KEY-----', '-----BEGIN PRIVATE KEY-----\n')
            
            # Add newline before END footer if missing
            if '-----END RSA PRIVATE KEY-----' in key and not '\n-----END RSA PRIVATE KEY-----' in key:
                key = key.replace('-----END RSA PRIVATE KEY-----', '\n-----END RSA PRIVATE KEY-----')
            elif '-----END PRIVATE KEY-----' in key and not '\n-----END PRIVATE KEY-----' in key:
                key = key.replace('-----END PRIVATE KEY-----', '\n-----END PRIVATE KEY-----')
            
            return key
            
        except Exception as e:
            logger.error(f"Error formatting private key: {str(e)}")
            raise ValueError(f"Failed to format private key: {str(e)}")
    
    def _generate_jwt_token(self) -> str:
        """Generate JWT token for GitHub App authentication."""
        try:
            # JWT payload with proper timing
            now = int(time.time())
            payload = {
                'iat': now - 10,  # Issued 10 seconds ago to account for clock skew
                'exp': now + (9 * 60),  # Expires in 9 minutes (GitHub allows max 10 minutes)
                'iss': int(self.app_id)  # Ensure app_id is integer
            }
            
            # Generate JWT with proper algorithm
            token = jwt.encode(payload, self.private_key, algorithm='RS256')
            
            # Handle both string and bytes return from PyJWT
            if isinstance(token, bytes):
                token = token.decode('utf-8')
                
            logger.debug(f"Generated JWT token for app {self.app_id}, expires at {datetime.fromtimestamp(payload['exp'])}")
            return token
            
        except Exception as e:
            logger.error(f"Failed to generate JWT token: {str(e)}")
            logger.error(f"App ID type: {type(self.app_id)}, value: {self.app_id}")
            # Log key format info without exposing key content
            key_info = "unknown format"
            if self.private_key.startswith('-----BEGIN RSA PRIVATE KEY-----'):
                key_info = "RSA PRIVATE KEY format"
            elif self.private_key.startswith('-----BEGIN PRIVATE KEY-----'):
                key_info = "PKCS#8 PRIVATE KEY format"
            logger.error(f"Private key format: {key_info}")
            raise ValueError(f"JWT generation failed: {str(e)}")
    
    def _get_installation_token(self, installation_id: int) -> str:
        """Get installation access token for specific installation."""
        # Validate installation_id
        if not installation_id or not isinstance(installation_id, (int, str)):
            raise ValueError(f"Invalid installation_id: {installation_id}")
            
        installation_id = int(installation_id)  # Ensure it's an integer
        
        # Check cache first
        cache_key = f"token_{installation_id}"
        if cache_key in self._token_cache:
            token_data = self._token_cache[cache_key]
            try:
                # Check if token is still valid (with 5 minute buffer)
                expires_at = datetime.fromisoformat(token_data['expires_at'].replace('Z', '+00:00'))
                if expires_at > datetime.now().astimezone() + timedelta(minutes=5):
                    logger.debug(f"Using cached token for installation {installation_id}")
                    return token_data['token']
                else:
                    logger.debug(f"Cached token for installation {installation_id} expired, fetching new one")
            except Exception as e:
                logger.warning(f"Error checking cached token expiry: {e}, fetching new token")
        
        try:
            # Generate JWT for app authentication
            jwt_token = self._generate_jwt_token()
            
            # Request installation token with proper headers
            headers = {
                'Authorization': f'Bearer {jwt_token}',
                'Accept': 'application/vnd.github+json',  # Updated to newer API version
                'X-GitHub-Api-Version': '2022-11-28',
                'User-Agent': 'AI-Tech-Lead-Reviewer/1.0.0'
            }
            
            url = f"{self.base_url}/app/installations/{installation_id}/access_tokens"
            logger.debug(f"Requesting installation token from: {url}")
            
            response = requests.post(
                url,
                headers=headers,
                timeout=30
            )
            
            logger.debug(f"Installation token response: {response.status_code}")
            
            if response.status_code == 201:
                token_data = response.json()
                # Cache the token
                self._token_cache[cache_key] = token_data
                logger.info(f"Successfully obtained installation token for installation {installation_id}")
                return token_data['token']
            elif response.status_code == 404:
                error_msg = f"Installation {installation_id} not found. Check if the GitHub App is installed on the repository."
                logger.error(error_msg)
                raise ValueError(error_msg)
            elif response.status_code == 401:
                error_msg = f"Authentication failed for installation {installation_id}. Check GitHub App credentials."
                logger.error(error_msg)
                raise ValueError(error_msg)
            else:
                error_msg = f"Failed to get installation token. Status: {response.status_code}, Response: {response.text}"
                logger.error(error_msg)
                response.raise_for_status()
                
        except requests.exceptions.RequestException as e:
            error_msg = f"Network error getting installation token: {str(e)}"
            logger.error(error_msg)
            raise ConnectionError(error_msg)
        except Exception as e:
            error_msg = f"Error getting installation token: {str(e)}"
            logger.error(error_msg)
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
            # Validate input parameters
            if not all([repo_owner, repo_name, pr_number, installation_id]):
                raise ValueError("Missing required parameters: repo_owner, repo_name, pr_number, or installation_id")
            
            if not isinstance(review_data, dict):
                raise ValueError("review_data must be a dictionary")
            
            # Get installation token
            token = self._get_installation_token(installation_id)
            
            # Updated headers for newer GitHub API
            headers = {
                'Authorization': f'Bearer {token}',  # Updated to Bearer token
                'Accept': 'application/vnd.github+json',
                'X-GitHub-Api-Version': '2022-11-28',
                'User-Agent': 'AI-Tech-Lead-Reviewer/1.0.0',
                'Content-Type': 'application/json'
            }
            
            # Prepare and validate review payload
            review_body = review_data.get('body', '')
            review_event = review_data.get('event', 'COMMENT')
            review_comments = review_data.get('comments', [])
            
            # Validate review event
            valid_events = ['APPROVE', 'REQUEST_CHANGES', 'COMMENT']
            if review_event not in valid_events:
                logger.warning(f"Invalid review event '{review_event}', defaulting to 'COMMENT'")
                review_event = 'COMMENT'
            
            review_payload = {
                'body': review_body,
                'event': review_event
            }
            
            # Validate and process comments
            if review_comments:
                valid_comments = []
                for i, comment in enumerate(review_comments):
                    try:
                        if not all(key in comment for key in ['path', 'line', 'body']):
                            logger.warning(f"Skipping comment {i}: missing required fields (path, line, body)")
                            continue
                            
                        # Validate line number
                        line_num = int(comment['line'])
                        if line_num <= 0:
                            logger.warning(f"Skipping comment {i}: invalid line number {line_num}")
                            continue
                            
                        valid_comment = {
                            'path': str(comment['path']).strip(),
                            'line': line_num,
                            'body': str(comment['body']).strip()
                        }
                        
                        # Add optional side field for diff comments
                        if 'side' in comment:
                            valid_comment['side'] = comment['side']
                            
                        valid_comments.append(valid_comment)
                        
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Skipping invalid comment {i}: {str(e)}")
                        continue
                
                if valid_comments:
                    review_payload['comments'] = valid_comments
                    logger.info(f"Prepared {len(valid_comments)} valid comments")
                else:
                    logger.info("No valid comments to include")
            
            # Log the request details
            url = f"{self.base_url}/repos/{repo_owner}/{repo_name}/pulls/{pr_number}/reviews"
            logger.info(f"Posting {review_event} review to {repo_owner}/{repo_name}#{pr_number}")
            logger.debug(f"Review URL: {url}")
            logger.debug(f"Review payload: {review_payload}")
            
            # Make API request
            response = requests.post(
                url,
                headers=headers,
                json=review_payload,
                timeout=45  # Increased timeout for large reviews
            )
            
            logger.debug(f"GitHub API response: {response.status_code}")

            if response.ok:
                try:
                    review_response = response.json()
                    review_id = review_response.get('id')
                    html_url = review_response.get('html_url')
                    logger.info(f"✅ Successfully posted review {review_id} to PR #{pr_number}")
                    return {
                        'success': True,
                        'review_id': review_id,
                        'html_url': html_url,
                        'event': review_event,
                        'comments_count': len(review_payload.get('comments', [])),
                        'raw_response': review_response
                    }
                except ValueError as e:
                    logger.error(f"Failed to parse GitHub API response: {e}")
                    return {
                        'success': True,  # Request succeeded even if response parsing failed
                        'review_id': 'unknown',
                        'raw_text': response.text
                    }
            elif response.status_code == 422:
                # Unprocessable entity - often due to invalid file paths or line numbers
                error_details = response.json() if response.headers.get('content-type', '').startswith('application/json') else {'message': response.text}
                error_msg = f"GitHub API validation error (422): {error_details.get('message', 'Unknown validation error')}"
                logger.error(error_msg)
                logger.debug(f"Full error response: {response.text}")
                return {
                    'success': False,
                    'error': error_msg,
                    'status_code': response.status_code,
                    'details': error_details
                }
            elif response.status_code == 403:
                error_msg = f"Forbidden (403): GitHub App may lack required permissions for {repo_owner}/{repo_name}"
                logger.error(error_msg)
                return {
                    'success': False,
                    'error': error_msg,
                    'status_code': response.status_code
                }
            elif response.status_code == 404:
                error_msg = f"Not found (404): PR #{pr_number} not found in {repo_owner}/{repo_name}"
                logger.error(error_msg)
                return {
                    'success': False,
                    'error': error_msg,
                    'status_code': response.status_code
                }
            else:
                error_msg = f"GitHub API error {response.status_code}: {response.text}"
                logger.error(error_msg)
                return {
                    'success': False,
                    'error': error_msg,
                    'status_code': response.status_code
                }

        except ConnectionError as e:
            error_msg = f"Network error posting review: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg,
                'error_type': 'connection'
            }
        except ValueError as e:
            error_msg = f"Validation error: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg,
                'error_type': 'validation'
            }
        except Exception as e:
            error_msg = f"Unexpected error posting review: {str(e)}"
            logger.exception(error_msg)  # Include full traceback
            return {
                'success': False,
                'error': error_msg,
                'error_type': 'unexpected'
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