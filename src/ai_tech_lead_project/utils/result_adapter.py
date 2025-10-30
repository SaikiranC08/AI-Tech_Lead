import json
from typing import Dict, Any


class CrewAIResultAdapter:
    """
    Adapts the raw output from a CrewAI workflow into a structured format
    suitable for the Reviewer Server.
    """

    def transform_crew_results(self, crew_results: Dict[str, Any], pr_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transforms the raw CrewAI results into the final JSON payload.

        Args:
            crew_results: The dictionary containing results from the CrewAI kickoff.
            pr_info: The original pull request information.

        Returns:
            A dictionary formatted for the Reviewer Server.
        """

        review_analysis = self._extract_review_analysis(crew_results)

        # The final payload for the reviewer server
        transformed_payload = {
            "pr_info": {
                "number": pr_info.get("number"),
                "repo_owner": pr_info.get("repo_name", "").split('/')[0],
                "repo_name": pr_info.get("repo_name", "").split('/')[-1],
                "installation_id": pr_info.get("installation_id")
            },
            "analysis": review_analysis
        }

        return transformed_payload

    def _extract_review_analysis(self, crew_results: Dict[str, Any]) -> Dict[str, Any]:
        """Extracts and formats the code review part of the results."""

        review_output = crew_results.get('review_results', {})

        # If review_output is a string, try to parse it as JSON
        if isinstance(review_output, str):
            try:
                review_output = json.loads(review_output)
            except json.JSONDecodeError:
                # If it's not valid JSON, use it as a summary
                return {
                    "summary": "Code review produced an invalid output format.",
                    "raw_output": review_output
                }

        # Structure the analysis based on expected keys from CodeReviewTool
        analysis = {
            "issues": [],
            "recommendations": [],
            "summary": review_output.get("summary", "No summary provided."),
            "quality_score": review_output.get("overall_score", 5)  # Default score
        }

        # Consolidate all issue types into a single 'issues' list
        issue_categories = [
            "style_issues", "documentation_issues", "potential_bugs",
            "error_handling_issues", "security_concerns", "performance_issues"
        ]
        for category in issue_categories:
            if category in review_output and isinstance(review_output[category], list):
                for issue in review_output[category]:
                    analysis["issues"].append({
                        "category": category.replace('_', ' ').title(),
                        "description": issue
                    })

        # Add positive aspects as recommendations
        if "positive_aspects" in review_output and isinstance(review_output["positive_aspects"], list):
            for positive in review_output["positive_aspects"]:
                analysis["recommendations"].append({
                    "category": "Positive Feedback",
                    "description": positive
                })

        return analysis
