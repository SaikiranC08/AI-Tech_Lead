
"""
AI Tech Lead - Reviewer Agent
LLM-powered code review agent using Gemini API for comprehensive code analysis.
"""
from dotenv import load_dotenv
import os
import json
import logging
import requests
from typing import Dict, Any
import google.generativeai as genai
from crewai import Agent, Task
from crewai.tools import BaseTool
from pydantic import BaseModel, Field, PrivateAttr
from typing import Type, Any

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

class CodeReviewSchema(BaseModel):
    """Input schema for the Code Review Tool."""
    pr_info: Dict[str, Any] = Field(description="Dictionary containing pull request information.")
    diff: str = Field(description="The git diff content of the pull request.")

class CodeReviewTool(BaseTool):
    name: str = "AI Code Reviewer"
    description: str = "Performs an AI-powered code review on a git diff."
    args_schema: Type[BaseModel] = CodeReviewSchema
    api_key: str = Field(default_factory=lambda: os.getenv('GEMINI_API_KEY'))
    _model: Any = PrivateAttr(default=None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self._model = genai.GenerativeModel("gemini-1.5-pro")

    def get_pr_diff(self, diff_url: str) -> str:
        """Fetches the diff content of a pull request from its diff URL."""
        if not diff_url:
            logging.warning("No diff URL provided to get_pr_diff.")
            return ""
        try:
            response = requests.get(diff_url)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            logging.error(f"Error fetching PR diff from {diff_url}: {e}")
            return ""

    def _run(self, pr_info: Dict[str, Any], diff: str) -> Dict[str, Any]:
        """
        Executes the code review using the Gemini API.
        If the review fails, it attempts to use the AI to suggest a fix for the error.
        """
        if not self._model:
            return {"error": "GEMINI_API_KEY not found or model not initialized."}
        
        logger.info(f"Performing AI code review on diff (first 200 chars): {diff[:200]}")
        
        prompt = f"""
        You are an expert senior software engineer conducting a code review. 
        Analyze the following git diff and provide a comprehensive review.

        PR Information:
        - Title: {pr_info.get('title', 'N/A')}
        - Author: {pr_info.get('pr_author', 'N/A')}
        - Repository: {pr_info.get('repo_name', 'N/A')}
        - Branch: {pr_info.get('head_branch', 'N/A')} → {pr_info.get('base_branch', 'N/A')}

        Git Diff:
        ```
        {diff}
        ```

        Please analyze the code changes and provide:
        1. Style and formatting issues with specific line references
        2. Documentation and commenting suggestions
        3. Potential bugs and code smell identification
        4. Error handling improvement recommendations  
        5. Security vulnerability assessment
        6. Performance optimization opportunities
        7. Positive aspects and good practices found
        8. Overall summary and recommendations

        Format your response as a JSON object with the following structure:
        {{
          "summary": "Brief overview of the review",
          "style_issues": [],
          "potential_bugs": [],
          "security_concerns": [],
          "performance_issues": [],
          "documentation_issues": [],
          "positive_aspects": []
        }}
        """

        try:
            response = self._model.generate_content(prompt)
            review_data = response.text
            
            # Clean the response to extract only the JSON part
            json_str = review_data.strip().replace("```json", "").replace("```", "")
            parsed_data = json.loads(json_str)
            return parsed_data
            
        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"Error during AI code review: {str(e)}. Attempting to get AI-suggested fix.")
            # If parsing fails or another error occurs, ask the AI to fix it.
            return self._suggest_fix(diff, str(e), review_data)

    def _suggest_fix(self, diff: str, error: str, raw_response: str) -> Dict[str, Any]:
        """
        If the initial review fails, this method asks the AI to analyze the failure
        and suggest a fix or explanation.
        """
        logger.info("Attempting to get AI-suggested fix for the review failure.")
        
        prompt = f"""
        A previous AI code review attempt failed. Please analyze the error and the original code
        to provide a helpful diagnosis.

        Original Git Diff:
        ```
        {diff}
        ```

        Error Encountered:
        {error}

        Raw AI Response (that caused the error):
        {raw_response}

        Please provide a summary of why the review might have failed and what the core issues
        in the code are. Format your response as a JSON object.
        {{
            "summary": "The code review failed, likely due to [reason]. The primary code issue seems to be [issue].",
            "potential_bugs": ["A brief description of the likely bug causing the issue."],
            "style_issues": [],
            "security_concerns": [],
            "performance_issues": [],
            "documentation_issues": [],
            "positive_aspects": []
        }}
        """
        try:
            response = self._model.generate_content(prompt)
            review_data = response.text
            json_str = review_data.strip().replace("```json", "").replace("```", "")
            return json.loads(json_str)
        except Exception as e:
            logger.error(f"AI-suggested fix also failed: {str(e)}")
            return {
                "summary": f"The AI code review process failed twice. Initial error: {error}. Follow-up error: {str(e)}",
                "potential_bugs": ["Unable to analyze code due to processing errors."],
                "style_issues": [], "security_concerns": [], "performance_issues": [],
                "documentation_issues": [], "positive_aspects": []
            }

    async def _arun(self, *args, **kwargs):
        # For async compatibility, you can delegate to the sync version
        # This is a simple approach; a true async implementation would use an async http client
        raise NotImplementedError("Async execution not supported")

def create_reviewer_agent(code_review_tool: CodeReviewTool) -> Agent:
    """
    Creates the Reviewer Agent, responsible for analyzing code changes.
    """
    return Agent(
        role='Senior Software Engineer',
        goal=(
            'Analyze the provided code changes (git diff) for a pull request. '
            'Identify bugs, security vulnerabilities, performance issues, and deviations from best practices. '
            'Provide a comprehensive, professional, and constructive code review.'
        ),
        backstory=(
            'You are a meticulous Senior Software Engineer with years of experience in code reviews. '
            'You have a keen eye for detail and a deep understanding of software design principles, '
            'security, and performance. Your reviews are always constructive, aiming to improve '
            'code quality and mentor other developers. You are reviewing a pull request and must '
            'provide your analysis based on the provided git diff.'
        ),
        tools=[code_review_tool],
        allow_delegation=False,
        verbose=True
    )

def create_review_task(agent: Agent, pr_info: Dict[str, Any], diff: str) -> Task:
    """
    Creates a task for the reviewer agent to analyze the code diff.
    """
    return Task(
        description=f"Analyze the git diff for PR #{pr_info.get('number')} and provide a comprehensive code review.",
        agent=agent,
        expected_output="A JSON object containing the code review with keys like 'summary', 'potential_bugs', 'style_issues', etc.",
        inputs={'pr_info': pr_info, 'diff': diff},
        tools=[type(agent.tools[0])]
    )
