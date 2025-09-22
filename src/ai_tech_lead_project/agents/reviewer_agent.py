"""
AI Tech Lead - Reviewer Agent
LLM-powered code review agent using Gemini API for comprehensive code analysis.
"""

import os
import json
import logging
import requests
from typing import Dict, Any
import google.generativeai as genai
from crewai import Agent, Task
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class CodeReviewTool:
    """Tool for performing AI-powered code reviews using Gemini API."""
    
    def __init__(self):
        """Initialize the Gemini API client."""
        self.api_key = os.getenv('GEMINI_API_KEY')
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")
        
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-1.5-pro')
    
    def get_pr_diff(self, diff_url: str) -> str:
        """Fetch the PR diff from GitHub."""
        try:
            response = requests.get(diff_url)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"Error fetching PR diff: {e}")
            return ""
    
    def analyze_code(self, code_diff: str, pr_info: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze code diff using Gemini API."""
        
        if not code_diff.strip():
            return {
                "style_issues": [],
                "documentation_issues": [],
                "potential_bugs": [],
                "error_handling_issues": [],
                "summary": "No code changes detected in the diff."
            }
        
        # Enhanced prompt for comprehensive code review
        prompt = f"""
You are a Senior Software Engineer conducting a thorough code review. Analyze the provided code diff and provide detailed feedback.

**Pull Request Information:**
- Title: {pr_info.get('title', 'N/A')}
- Repository: {pr_info.get('repo_name', 'N/A')}
- Author: {pr_info.get('pr_author', 'N/A')}

**Code Diff:**
```diff
{code_diff}
```

**Instructions:**
Analyze the code changes and provide feedback in the following areas:

1. **Coding Standards & Style:** Check for PEP8 compliance (Python), naming conventions, code formatting, and consistency with existing codebase patterns.

2. **Documentation & Comments:** Evaluate docstrings, inline comments, and code readability. Identify missing documentation for complex logic.

3. **Potential Bugs & Code Smells:** Look for logical errors, edge cases, race conditions, memory leaks, infinite loops, and anti-patterns.

4. **Error Handling:** Check for proper exception handling, input validation, and graceful error recovery mechanisms.

5. **Security Concerns:** Identify potential security vulnerabilities like SQL injection, XSS, hardcoded secrets, or insecure data handling.

6. **Performance Issues:** Look for inefficient algorithms, unnecessary loops, database query issues, or resource usage problems.

**Output Format:**
Return your analysis as a valid JSON object with the following structure:

{{
    "style_issues": [
        {{
            "line": "line_number_or_range",
            "issue": "description_of_style_issue",
            "severity": "low|medium|high",
            "suggestion": "how_to_fix_it"
        }}
    ],
    "documentation_issues": [
        {{
            "line": "line_number_or_range",
            "issue": "description_of_documentation_issue",
            "severity": "low|medium|high",
            "suggestion": "how_to_improve_documentation"
        }}
    ],
    "potential_bugs": [
        {{
            "line": "line_number_or_range",
            "issue": "description_of_potential_bug",
            "severity": "low|medium|high|critical",
            "suggestion": "how_to_fix_the_bug"
        }}
    ],
    "error_handling_issues": [
        {{
            "line": "line_number_or_range",
            "issue": "description_of_error_handling_issue",
            "severity": "low|medium|high",
            "suggestion": "how_to_improve_error_handling"
        }}
    ],
    "security_concerns": [
        {{
            "line": "line_number_or_range",
            "issue": "description_of_security_concern",
            "severity": "low|medium|high|critical",
            "suggestion": "how_to_address_security_issue"
        }}
    ],
    "performance_issues": [
        {{
            "line": "line_number_or_range",
            "issue": "description_of_performance_issue",
            "severity": "low|medium|high",
            "suggestion": "how_to_optimize_performance"
        }}
    ],
    "positive_aspects": [
        "list_of_good_practices_or_improvements_found_in_the_code"
    ],
    "summary": "overall_assessment_of_the_code_changes"
}}

Be specific about line numbers when possible and provide actionable suggestions. If no issues are found in a category, return an empty array for that category.
"""

        try:
            response = self.model.generate_content(prompt)
            
            # Extract JSON from the response
            response_text = response.text.strip()
            
            # Try to find JSON in the response (sometimes the model wraps it in markdown)
            if '```json' in response_text:
                json_start = response_text.find('```json') + 7
                json_end = response_text.find('```', json_start)
                json_text = response_text[json_start:json_end].strip()
            elif response_text.startswith('{'):
                json_text = response_text
            else:
                # Fallback: try to extract JSON from the response
                json_start = response_text.find('{')
                json_end = response_text.rfind('}') + 1
                json_text = response_text[json_start:json_end] if json_start >= 0 else response_text
            
            # Parse the JSON response
            analysis_result = json.loads(json_text)
            
            # Validate required keys
            required_keys = ['style_issues', 'documentation_issues', 'potential_bugs', 
                           'error_handling_issues', 'summary']
            for key in required_keys:
                if key not in analysis_result:
                    analysis_result[key] = [] if key != 'summary' else 'Analysis completed'
            
            return analysis_result
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response from Gemini: {e}")
            return {
                "style_issues": [],
                "documentation_issues": [],
                "potential_bugs": [],
                "error_handling_issues": [],
                "security_concerns": [],
                "performance_issues": [],
                "positive_aspects": [],
                "summary": f"Code review completed but failed to parse detailed results: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Error during code analysis: {e}")
            return {
                "style_issues": [],
                "documentation_issues": [],
                "potential_bugs": [],
                "error_handling_issues": [],
                "security_concerns": [],
                "performance_issues": [],
                "positive_aspects": [],
                "summary": f"Code review failed due to error: {str(e)}"
            }

def create_reviewer_agent() -> Agent:
    """Create and configure the Reviewer Agent."""
    
    return Agent(
        role="Senior Code Reviewer",
        goal="Perform comprehensive code reviews to ensure high code quality, identify potential issues, and suggest improvements",
        backstory="""You are an experienced Senior Software Engineer with 10+ years of experience 
        in code review, software architecture, and best practices. You have expertise in multiple 
        programming languages, with particular strength in Python, JavaScript, and modern development 
        practices. You're known for providing constructive, actionable feedback that helps developers 
        improve their skills while maintaining high code quality standards.""",
        verbose=True,
        allow_delegation=False,
        tools=[]  # Tools will be added during task execution
    )

def create_review_task(agent: Agent, pr_info: Dict[str, Any]) -> Task:
    """Create a code review task for the Reviewer Agent."""
    
    return Task(
        description=f"""
        Conduct a comprehensive code review for Pull Request #{pr_info.get('number')} 
        in repository {pr_info.get('repo_name')}.
        
        **Task Details:**
        - Analyze the code diff from: {pr_info.get('diff_url')}
        - Review for coding standards, documentation, potential bugs, and error handling
        - Identify security concerns and performance issues
        - Provide constructive feedback and actionable suggestions
        
        **PR Information:**
        - Title: {pr_info.get('title')}
        - Author: {pr_info.get('pr_author')}
        - Branch: {pr_info.get('head_branch')} → {pr_info.get('base_branch')}
        
        Use the CodeReviewTool to fetch and analyze the PR diff. Return a detailed analysis 
        with specific issues, suggestions, and an overall assessment.
        """,
        expected_output="""A comprehensive code review analysis containing:
        1. Style and formatting issues with specific line references
        2. Documentation and commenting suggestions
        3. Potential bugs and code smell identification
        4. Error handling improvement recommendations  
        5. Security vulnerability assessment
        6. Performance optimization opportunities
        7. Positive aspects and good practices found
        8. Overall summary and recommendations
        
        The output should be structured as a JSON object with categorized findings 
        and actionable suggestions for each identified issue.""",
        agent=agent
    )