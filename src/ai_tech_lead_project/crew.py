"""
AI Tech Lead - CrewAI Orchestration
Main workflow coordinating Reviewer, Tester, and Reporter agents.
"""

import os
import logging
from typing import Dict, Any
from crewai import Crew, Process
from dotenv import load_dotenv

# Import our agents and tools
from agents.reviewer_agent import (
    create_reviewer_agent, 
    create_review_task, 
    CodeReviewTool
)
from agents.tester_agent import (
    create_tester_agent, 
    create_testing_task, 
    UnitTestTool
)
from agents.reporter_agent import (
    create_reporter_agent, 
    create_reporting_task, 
    GitHubReportTool
)

load_dotenv()
logger = logging.getLogger(__name__)

class AITechLeadCrew:
    """Main CrewAI workflow orchestrating all AI Tech Lead agents."""
    
    def __init__(self):
        """Initialize the crew with all agents and tools."""
        
        # Verify required environment variables
        required_vars = [
            'GEMINI_API_KEY',
            'GITHUB_APP_ID', 
            'GITHUB_APP_PRIVATE_KEY',
            'GITHUB_WEBHOOK_SECRET'
        ]
        
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {missing_vars}")
        
        # Initialize tools
        self.code_review_tool = CodeReviewTool()
        self.unit_test_tool = UnitTestTool()
        self.github_report_tool = GitHubReportTool()
        
        # Create agents
        self.reviewer_agent = create_reviewer_agent()
        self.tester_agent = create_tester_agent()
        self.reporter_agent = create_reporter_agent()
        
        logger.info("AI Tech Lead Crew initialized successfully")
    
    def create_tasks(self, pr_info: Dict[str, Any]):
        """Create tasks for all agents based on PR information."""
        
        # Create individual agent tasks
        review_task = create_review_task(self.reviewer_agent, pr_info)
        testing_task = create_testing_task(self.tester_agent, pr_info) 
        reporting_task = create_reporting_task(self.reporter_agent, pr_info)
        
        # Set up task dependencies (sequential execution)
        testing_task.context = [review_task]  # Tester waits for reviewer
        reporting_task.context = [review_task, testing_task]  # Reporter waits for both
        
        return [review_task, testing_task, reporting_task]
    
    def execute_code_review(self, pr_info: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the code review workflow."""
        
        logger.info(f"Starting code review for PR #{pr_info.get('number')}")
        
        try:
            # Fetch PR diff
            diff_content = self.code_review_tool.get_pr_diff(pr_info.get('diff_url', ''))
            
            # Analyze the code
            review_results = self.code_review_tool.analyze_code(diff_content, pr_info)
            
            logger.info("Code review analysis completed")
            return review_results
            
        except Exception as e:
            logger.error(f"Error during code review: {e}")
            return {
                "style_issues": [],
                "documentation_issues": [],
                "potential_bugs": [],
                "error_handling_issues": [],
                "security_concerns": [],
                "performance_issues": [],
                "positive_aspects": [],
                "summary": f"Code review failed: {str(e)}"
            }
    
    def execute_unit_testing(self, pr_info: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the unit testing workflow."""
        
        logger.info(f"Starting unit test generation for PR #{pr_info.get('number')}")
        
        try:
            # Fetch PR diff
            diff_content = self.unit_test_tool.get_pr_diff(pr_info.get('diff_url', ''))
            
            # Extract functions from diff
            functions = self.unit_test_tool.extract_functions_from_diff(diff_content)
            
            if not functions:
                return {
                    "test_files": [],
                    "test_results": [],
                    "overall_status": "SKIPPED",
                    "summary": "No new functions found for testing in the PR diff."
                }
            
            # Generate tests
            test_generation_results = self.unit_test_tool.generate_tests(functions, pr_info)
            
            # Execute tests
            test_execution_results = self.unit_test_tool.run_tests(
                test_generation_results.get('test_files', [])
            )
            
            # Combine results
            combined_results = {
                **test_generation_results,
                **test_execution_results
            }
            
            logger.info("Unit testing workflow completed")
            return combined_results
            
        except Exception as e:
            logger.error(f"Error during unit testing: {e}")
            return {
                "test_files": [],
                "test_results": [],
                "overall_status": "ERROR", 
                "summary": f"Unit testing failed: {str(e)}"
            }
    
    def execute_reporting(self, pr_info: Dict[str, Any], review_results: Dict[str, Any], test_results: Dict[str, Any]) -> bool:
        """Execute the reporting workflow."""
        
        logger.info(f"Creating report for PR #{pr_info.get('number')}")
        
        try:
            # Format combined report
            report = self.github_report_tool.format_combined_report(review_results, test_results)
            
            # Post to GitHub
            success = self.github_report_tool.post_pr_comment(pr_info, report)
            
            if success:
                logger.info("Report posted successfully to GitHub PR")
            else:
                logger.error("Failed to post report to GitHub PR")
            
            return success
            
        except Exception as e:
            logger.error(f"Error during reporting: {e}")
            return False
    
    def kickoff(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main workflow execution method.
        
        Args:
            inputs: PR information dictionary containing:
                - number: PR number
                - repo_name: Repository name
                - diff_url: URL to fetch PR diff
                - installation_id: GitHub App installation ID
                - Other PR metadata
        
        Returns:
            Dict containing execution results and status
        """
        
        pr_number = inputs.get('number')
        repo_name = inputs.get('repo_name')
        
        logger.info(f"Starting AI Tech Lead workflow for PR #{pr_number} in {repo_name}")
        
        try:
            # Execute code review
            review_results = self.execute_code_review(inputs)
            
            # Execute unit testing  
            test_results = self.execute_unit_testing(inputs)
            
            # Execute reporting
            reporting_success = self.execute_reporting(inputs, review_results, test_results)
            
            # Compile final results
            final_results = {
                'pr_info': inputs,
                'review_results': review_results,
                'test_results': test_results,
                'reporting_success': reporting_success,
                'status': 'completed' if reporting_success else 'partial_failure',
                'message': 'AI Tech Lead workflow completed successfully' if reporting_success 
                          else 'Workflow completed but reporting failed'
            }
            
            logger.info(f"AI Tech Lead workflow completed for PR #{pr_number}")
            return final_results
            
        except Exception as e:
            logger.error(f"Workflow execution failed for PR #{pr_number}: {e}")
            
            # Try to post an error report
            try:
                error_report = self._create_error_report(str(e))
                self.github_report_tool.post_pr_comment(inputs, error_report)
            except:
                pass  # Don't let error reporting failure crash the main workflow
            
            return {
                'pr_info': inputs,
                'status': 'error',
                'error': str(e),
                'message': f'AI Tech Lead workflow failed: {str(e)}'
            }
    
    def _create_error_report(self, error_message: str) -> str:
        """Create an error report for posting to GitHub."""
        
        return f"""# ❌ AI Tech Lead - Workflow Error

## Error Report

Unfortunately, the AI Tech Lead analysis encountered an error and could not complete successfully.

**Error Details:**
```
{error_message}
```

## What to do:

1. **Check the logs** - The development team has been notified and will investigate
2. **Manual review** - Please conduct a manual code review for this PR
3. **Retry later** - You can try closing and reopening the PR to trigger analysis again

## Contact

If this error persists, please contact the development team or check the project's issue tracker.

---
*🤖 AI Tech Lead encountered an error during analysis. Sorry for the inconvenience!*
"""

# Convenience function for direct usage
def create_ai_tech_lead_crew() -> AITechLeadCrew:
    """Factory function to create a new AI Tech Lead crew instance."""
    return AITechLeadCrew()

# Example usage and testing
if __name__ == "__main__":
    # This section can be used for testing the crew locally
    import sys
    
    # Example PR info for testing
    test_pr_info = {
        'number': 1,
        'title': 'Test PR',
        'repo_name': 'test/repo',
        'repo_owner': 'test',
        'pr_author': 'testuser',
        'pr_url': 'https://github.com/test/repo/pull/1',
        'base_branch': 'main',
        'head_branch': 'feature/test',
        'diff_url': 'https://github.com/test/repo/pull/1.diff',
        'patch_url': 'https://github.com/test/repo/pull/1.patch',
        'installation_id': 12345
    }
    
    if len(sys.argv) > 1 and sys.argv[1] == 'test':
        print("Testing AI Tech Lead Crew...")
        
        try:
            crew = AITechLeadCrew()
            print("✅ Crew initialized successfully")
            
            # You can uncomment the line below to test with real API calls
            # result = crew.kickoff(test_pr_info)
            # print(f"✅ Test workflow result: {result.get('status')}")
            
        except Exception as e:
            print(f"❌ Test failed: {e}")
            sys.exit(1)
    
    print("AI Tech Lead Crew module loaded successfully")