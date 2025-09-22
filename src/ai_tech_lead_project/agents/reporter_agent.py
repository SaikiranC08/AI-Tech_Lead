"""
AI Tech Lead - Reporter Agent
Formats analysis results and posts comprehensive reports to GitHub PR comments.
"""

import os
import logging
from typing import Dict, Any, List
from github import Github, Auth
from crewai import Agent, Task
from dotenv import load_dotenv
import jwt
import time

load_dotenv()
logger = logging.getLogger(__name__)

class GitHubReportTool:
    """Tool for posting formatted reports to GitHub PR comments."""
    
    def __init__(self):
        """Initialize GitHub API client with App authentication."""
        self.app_id = os.getenv('GITHUB_APP_ID')
        self.private_key = os.getenv('GITHUB_APP_PRIVATE_KEY')
        
        if not self.app_id or not self.private_key:
            raise ValueError("GITHUB_APP_ID and GITHUB_APP_PRIVATE_KEY environment variables are required")
        
        # Handle private key formatting
        if '\\n' in self.private_key:
            self.private_key = self.private_key.replace('\\n', '\n')
    
    def get_github_client(self, installation_id: int) -> Github:
        """Get GitHub client authenticated as the app installation."""
        
        # Generate JWT for GitHub App
        payload = {
            'iat': int(time.time()),
            'exp': int(time.time()) + 600,  # 10 minutes
            'iss': self.app_id
        }
        
        jwt_token = jwt.encode(payload, self.private_key, algorithm='RS256')
        
        # Get installation access token
        auth = Auth.AppAuth(self.app_id, self.private_key)
        gi = Github(auth=auth)
        
        # Get the installation and create access token
        installation = gi.get_app_installation(installation_id)
        installation_auth = installation.get_access_token()
        
        # Create client with installation token
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

def create_reporter_agent() -> Agent:
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
        tools=[]
    )

def create_reporting_task(agent: Agent, pr_info: Dict[str, Any]) -> Task:
    """Create a reporting task for the Reporter Agent."""
    
    return Task(
        description=f"""
        Create and publish a comprehensive analysis report for Pull Request #{pr_info.get('number')} 
        in repository {pr_info.get('repo_name')}.
        
        **Task Details:**
        - Compile results from code review and unit testing analysis
        - Format findings into a clear, professional Markdown report
        - Prioritize issues by severity and impact
        - Provide actionable recommendations
        - Post the report as a comment on the GitHub PR
        
        **PR Information:**
        - Title: {pr_info.get('title')}
        - Author: {pr_info.get('pr_author')}
        - URL: {pr_info.get('pr_url')}
        
        The report should include:
        1. Executive summary with overall assessment
        2. Code review findings organized by category and severity
        3. Unit testing results and coverage analysis
        4. Specific recommendations for improvement
        5. Recognition of good practices found in the code
        """,
        expected_output="""A professionally formatted Markdown report posted as a GitHub PR comment containing:
        1. Clear executive summary indicating if action is required
        2. Detailed breakdown of all identified issues with severity levels
        3. Unit test generation and execution results
        4. Specific, actionable recommendations for each issue
        5. Professional formatting with appropriate use of emoji and styling
        6. Successful posting to the GitHub PR as a comment
        
        The report should be comprehensive yet concise, helping developers understand
        what needs attention and providing clear guidance on how to address issues.""",
        agent=agent
    )