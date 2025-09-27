
"""
AI Tech Lead - Reporter Agent
Formats analysis results and posts comprehensive reports to GitHub PR comments.
"""

import os
import logging
from typing import Dict, Any, List, Type
from github import Github, Auth
from crewai import Agent, Task
from dotenv import load_dotenv
import jwt
import time
from pydantic import BaseModel, Field, PrivateAttr
from crewai.tools import BaseTool

load_dotenv()
logger = logging.getLogger(__name__)


class GitHubReportSchema(BaseModel):
    """Input schema for the GitHub Report Tool."""
    pr_info: Dict[str, Any] = Field(..., description="Dictionary containing pull request information.")
    review_results: Dict[str, Any] = Field(..., description="The results from the code review agent.")
    test_results: Dict[str, Any] = Field(..., description="The results from the unit testing agent.")


class GitHubReportTool(BaseTool):
    """Tool for posting formatted reports to GitHub PR comments."""
    name: str = "GitHub PR Reporter"
    description: str = "Formats and posts a comprehensive report to a GitHub pull request."
    args_schema: Type[BaseModel] = GitHubReportSchema
    _app_id: str = PrivateAttr()
    _private_key: str = PrivateAttr()
    _webhook_secret: str = PrivateAttr()

    def __init__(self, **kwargs):
        """Initialize GitHub API client with App authentication."""
        super().__init__(**kwargs)
        self._app_id = os.getenv('GITHUB_APP_ID')
        self._private_key = os.getenv('GITHUB_PRIVATE_KEY')
        self._webhook_secret = os.getenv('GITHUB_WEBHOOK_SECRET')
        if self._private_key:
            self._private_key = self._private_key.replace('\\n', '\n')
    
    def get_github_client(self, installation_id: int) -> Github:
        """Authenticates as a GitHub App installation and returns a PyGithub client."""
        auth = Auth.AppAuth(self._app_id, self._private_key)
        installation_auth = auth.get_installation_auth(installation_id)
        return Github(installation_auth.token)
    
    def format_review_report(self, review_results: Dict[str, Any]) -> str:
        """Format code review results into Markdown report."""
        
        report = ["# 🤖 AI Tech Lead - Code Review Report\n"]
        
        # Summary section
        summary = review_results.get('summary', 'Code review completed')
        report.append(f"## 📋 Summary\n{summary}\n")
        
        # Count issues by severity
        all_issues = []
        issue_categories = ['style_issues', 'documentation_issues', 'potential_bugs', 
                          'error_handling_issues', 'security_concerns', 'performance_issues']
        
        for category in issue_categories:
            if category in review_results:
                all_issues.extend(review_results[category])
        
        if not all_issues:
            report.append("## ✅ Great News!\nNo significant issues found in this code review. Good job! 👏\n")
            return '\n'.join(report)
        
        # Issue statistics
        critical_count = len([i for i in all_issues if i.get('severity') == 'critical'])
        high_count = len([i for i in all_issues if i.get('severity') == 'high'])
        medium_count = len([i for i in all_issues if i.get('severity') == 'medium'])
        low_count = len([i for i in all_issues if i.get('severity') == 'low'])
        
        report.append("## 📊 Issue Summary")
        report.append("| Severity | Count |")
        report.append("|----------|--------|")
        if critical_count > 0:
            report.append(f"| 🔴 Critical | {critical_count} |")
        if high_count > 0:
            report.append(f"| 🟠 High | {high_count} |")
        if medium_count > 0:
            report.append(f"| 🟡 Medium | {medium_count} |")
        if low_count > 0:
            report.append(f"| 🟢 Low | {low_count} |")
        report.append("")
        
        # Detailed findings
        category_icons = {
            'style_issues': '🎨 Style & Formatting',
            'documentation_issues': '📚 Documentation',
            'potential_bugs': '🐛 Potential Bugs',
            'error_handling_issues': '⚠️ Error Handling',
            'security_concerns': '🔒 Security Concerns',
            'performance_issues': '⚡ Performance Issues'
        }
        
        for category, icon_title in category_icons.items():
            issues = review_results.get(category, [])
            if issues:
                report.append(f"## {icon_title}")
                for issue in issues:
                    severity = issue.get('severity', 'medium')
                    severity_icon = {'critical': '🔴', 'high': '🟠', 'medium': '🟡', 'low': '🟢'}.get(severity, '🟡')
                    
                    report.append(f"### {severity_icon} Line {issue.get('line', 'N/A')}")
                    report.append(f"**Issue:** {issue.get('issue', 'No description')}")
                    if issue.get('suggestion'):
                        report.append(f"**Suggestion:** {issue.get('suggestion')}")
                    report.append("")
        
        # Positive aspects
        positive_aspects = review_results.get('positive_aspects', [])
        if positive_aspects:
            report.append("## 👏 Positive Aspects")
            for aspect in positive_aspects:
                report.append(f"- {aspect}")
            report.append("")
        
        return '\n'.join(report)
    
    def format_test_report(self, test_results: Dict[str, Any]) -> str:
        """Format unit test results into Markdown report."""
        
        report = ["# 🧪 AI Tech Lead - Unit Testing Report\n"]
        
        # Summary
        summary = test_results.get('summary', 'Testing completed')
        report.append(f"## 📋 Summary\n{summary}\n")
        
        test_files = test_results.get('test_files', [])
        test_execution_results = test_results.get('test_results', [])
        overall_status = test_results.get('overall_status', 'UNKNOWN')
        
        if not test_files:
            report.append("## ℹ️ No Tests Generated\nNo new functions found for testing in the PR diff.\n")
            return '\n'.join(report)
        
        # Test generation results
        report.append("## 🏗️ Test Generation Results")
        report.append("| Function | File | Status |")
        report.append("|----------|------|--------|")
        
        for test_file in test_files:
            function_name = test_file.get('function_name', 'Unknown')
            file_path = test_file.get('file_path', 'Unknown')
            status = "✅ Generated" if 'error' not in test_file else "❌ Failed"
            report.append(f"| `{function_name}` | `{file_path}` | {status} |")
        
        report.append("")
        
        # Test execution results
        if test_execution_results:
            report.append("## 🏃‍♂️ Test Execution Results")
            
            status_icon = {
                'PASSED': '✅',
                'FAILED': '❌', 
                'ERROR': '💥',
                'TIMEOUT': '⏰',
                'MIXED': '⚠️'
            }.get(overall_status, '❓')
            
            report.append(f"**Overall Status:** {status_icon} {overall_status}")
            report.append("")
            
            report.append("| Function | Test File | Status | Details |")
            report.append("|----------|-----------|---------|---------|")
            
            for result in test_execution_results:
                function_name = result.get('function_name', 'Unknown')
                test_filename = result.get('test_filename', 'Unknown')
                status = result.get('status', 'UNKNOWN')
                status_icon = {
                    'PASSED': '✅',
                    'FAILED': '❌',
                    'ERROR': '💥',
                    'TIMEOUT': '⏰'
                }.get(status, '❓')
                
                # Truncate output for table
                output = result.get('output', '')
                details = output[:50] + "..." if len(output) > 50 else output
                details = details.replace('\n', ' ').replace('|', '\\|')
                
                report.append(f"| `{function_name}` | `{test_filename}` | {status_icon} {status} | {details} |")
            
            report.append("")
            
            # Detailed test outputs for failures
            failed_tests = [r for r in test_execution_results if r.get('status') in ['FAILED', 'ERROR', 'TIMEOUT']]
            if failed_tests:
                report.append("## 📝 Detailed Test Output (Failures/Errors)")
                for result in failed_tests:
                    function_name = result.get('function_name', 'Unknown')
                    status = result.get('status', 'UNKNOWN')
                    output = result.get('output', 'No output available')
                    
                    report.append(f"### ❌ {function_name} - {status}")
                    report.append("```")
                    report.append(output)
                    report.append("```")
                    report.append("")
        
        return '\n'.join(report)
    
    def format_combined_report(self, review_results: Dict[str, Any], test_results: Dict[str, Any]) -> str:
        """Create a combined report with both review and test results."""
        
        # Header
        report = ["# 🚀 AI Tech Lead - Complete Analysis Report"]
        report.append("*Automated code review and unit testing powered by AI*\n")
        
        # Executive summary
        review_issues = []
        issue_categories = ['style_issues', 'documentation_issues', 'potential_bugs', 
                          'error_handling_issues', 'security_concerns', 'performance_issues']
        
        for category in issue_categories:
            if category in review_results:
                review_issues.extend(review_results[category])
        
        test_status = test_results.get('overall_status', 'UNKNOWN')
        critical_issues = len([i for i in review_issues if i.get('severity') == 'critical'])
        high_issues = len([i for i in review_issues if i.get('severity') == 'high'])
        
        report.append("## 🎯 Executive Summary")
        if critical_issues > 0 or test_status in ['FAILED', 'ERROR']:
            report.append("⚠️ **Action Required:** This PR has critical issues that should be addressed before merging.")
        elif high_issues > 0 or test_status == 'MIXED':
            report.append("🔍 **Review Recommended:** This PR has some issues that would benefit from attention.")
        else:
            report.append("✅ **Looks Good:** This PR meets quality standards and is ready for review.")
        
        report.append(f"- **Code Review:** {len(review_issues)} issues found")
        report.append(f"- **Unit Tests:** {test_status}")
        report.append("")
        
        # Add individual reports
        review_section = self.format_review_report(review_results)
        test_section = self.format_test_report(test_results)
        
        # Remove headers from individual sections since we have a combined header
        review_section = review_section.replace('# 🤖 AI Tech Lead - Code Review Report\n', '')
        test_section = test_section.replace('# 🧪 AI Tech Lead - Unit Testing Report\n', '')
        
        report.append("---")
        report.append(review_section)
        report.append("---")
        report.append(test_section)
        
        # Footer
        report.append("---")
        report.append("*🤖 This analysis was performed by AI Tech Lead. Please review the suggestions and use your judgment when applying changes.*")
        
        return '\n'.join(report)
    
    def post_pr_comment(self, pr_info: Dict[str, Any], report: str) -> bool:
        """Post the formatted report as a comment on the PR."""
        
        try:
            installation_id = pr_info.get('installation_id')
            if not installation_id:
                logger.error("No installation_id provided")
                return False
            
            # Get authenticated GitHub client
            github = self.get_github_client(installation_id)
            
            # Get repository and PR
            repo_name = pr_info.get('repo_name')
            pr_number = pr_info.get('number')
            
            if not repo_name or not pr_number:
                logger.error("Missing repo_name or pr_number")
                return False
            
            repo = github.get_repo(repo_name)
            pr = repo.get_pull(pr_number)
            
            # Post comment
            comment = pr.create_issue_comment(report)
            logger.info(f"Posted comment {comment.id} to PR #{pr_number}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to post PR comment: {e}")
            return False

    def _run(self, pr_info: Dict[str, Any], review_results: Dict[str, Any], test_results: Dict[str, Any]) -> str:
        """The main execution method for the tool."""
        logger.info(f"Generating report for PR #{pr_info.get('number')}")
        report = self.format_combined_report(review_results, test_results)
        success = self.post_pr_comment(pr_info, report)
        if success:
            return f"Successfully posted report to PR #{pr_info.get('number')}."
        else:
            return f"Failed to post report to PR #{pr_info.get('number')}."


def create_reporter_agent(github_report_tool: BaseTool) -> Agent:
    """Create and configure the Reporter Agent."""
    
    return Agent(
        role="Technical Communication Specialist",
        goal="Create clear, comprehensive reports and communicate findings effectively to development teams",
        backstory="""You are an expert Technical Writer and Communication Specialist with extensive 
        experience in creating developer-friendly documentation and reports. You excel at taking 
        complex technical analysis and presenting it in a clear, actionable format. You understand 
        the importance of prioritizing issues, providing context, and making recommendations that 
        help developers improve their code quality efficiently.""",
        verbose=True,
        allow_delegation=False,
        tools=[github_report_tool]
    )

def create_reporting_task(agent: Agent, pr_info: Dict[str, Any], context: list) -> Task:
    """
    Creates a task for the reporter agent to format and post the final report.
    """
    return Task(
        description=f"Format the code review and test results for PR #{pr_info.get('number')} and post it to GitHub.",
        agent=agent,
        context=context,
        expected_output="A confirmation message indicating the report has been posted to GitHub.",
        inputs={
            "pr_info": pr_info,
            "review_results": None,  # This will be populated by the crew
            "test_results": None     # This will be populated by the crew
        },
        tools=[type(agent.tools[0])]
    )

def create_report_task(agent: Agent, pr_info: Dict[str, Any], context: list) -> Task:
    """
    Create a task for the reporter agent to compile and format the final review report.
    """
    return Task(
        description=(
            "Compile a comprehensive code review report in Markdown format. "
            "The report should summarize findings from the code analysis and unit testing phases. "
            "Use the context provided from the reviewer and tester agents' tasks."
        ),
        expected_output=(
            "A single, well-formatted Markdown string containing the complete review report. "
            "The report should include sections for overall summary, positive aspects, "
            "style issues, potential bugs, security concerns, and other relevant findings. "
            "If unit tests were generated, include the test code in a collapsible section."
        ),
        agent=agent,
        context=context,
        inputs={'pr_info': pr_info}
    )
