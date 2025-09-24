"""
Result Adapter Module
Transforms CrewAI analysis results into the format expected by the Reviewer Server.
"""

import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class CrewAIResultAdapter:
    """Adapts CrewAI workflow results to Reviewer Server format."""
    
    def __init__(self):
        """Initialize the adapter."""
        self.severity_mapping = {
            'low': 'low',
            'medium': 'medium', 
            'high': 'high',
            'critical': 'critical'
        }
        
        self.category_mapping = {
            'style_issues': 'code_style',
            'documentation_issues': 'documentation',
            'potential_bugs': 'logic',
            'error_handling_issues': 'best_practices',
            'security_concerns': 'security',
            'performance_issues': 'performance'
        }
    
    def transform_crew_results(self, crew_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform CrewAI workflow results into Reviewer Server format.
        
        Args:
            crew_results: Results from CrewAI kickoff method
            
        Returns:
            Dict in format expected by Reviewer Server
        """
        try:
            # Extract PR info and results
            pr_info = crew_results.get('pr_info', {})
            review_results = crew_results.get('review_results', {})
            test_results = crew_results.get('test_results', {})
            
            # Transform the analysis
            analysis = self._transform_analysis(review_results, test_results)
            
            # Create the Reviewer Server payload
            reviewer_payload = {
                'pr_info': {
                    'number': pr_info.get('number'),
                    'repo_owner': pr_info.get('repo_owner'),
                    'repo_name': pr_info.get('repo_name'),
                    'installation_id': pr_info.get('installation_id')
                },
                'analysis': analysis
            }
            
            logger.info(f"Transformed CrewAI results for PR #{pr_info.get('number')}")
            return reviewer_payload
            
        except Exception as e:
            logger.error(f"Error transforming CrewAI results: {str(e)}")
            # Return minimal payload on error
            return {
                'pr_info': crew_results.get('pr_info', {}),
                'analysis': {
                    'quality_score': 5.0,
                    'summary': f'Analysis transformation failed: {str(e)}',
                    'issues': [],
                    'recommendations': []
                }
            }
    
    def _transform_analysis(self, review_results: Dict[str, Any], test_results: Dict[str, Any]) -> Dict[str, Any]:
        """Transform review and test results into analysis format."""
        
        # Calculate quality score
        quality_score = self._calculate_quality_score(review_results, test_results)
        
        # Generate summary
        summary = self._generate_summary(review_results, test_results, quality_score)
        
        # Transform issues
        issues = self._transform_issues(review_results)
        
        # Transform recommendations
        recommendations = self._transform_recommendations(review_results, test_results)
        
        return {
            'quality_score': quality_score,
            'summary': summary,
            'issues': issues,
            'recommendations': recommendations
        }
    
    def _calculate_quality_score(self, review_results: Dict[str, Any], test_results: Dict[str, Any]) -> float:
        """Calculate a quality score based on the analysis results."""
        
        # Start with base score
        score = 10.0
        
        # Deduct points for issues
        critical_issues = 0
        high_issues = 0
        medium_issues = 0
        low_issues = 0
        
        # Count issues by severity
        for category in ['style_issues', 'documentation_issues', 'potential_bugs', 
                        'error_handling_issues', 'security_concerns', 'performance_issues']:
            issues = review_results.get(category, [])
            for issue in issues:
                severity = issue.get('severity', 'medium')
                if severity == 'critical':
                    critical_issues += 1
                elif severity == 'high':
                    high_issues += 1
                elif severity == 'medium':
                    medium_issues += 1
                else:
                    low_issues += 1
        
        # Apply score reductions
        score -= (critical_issues * 2.0)  # -2 points per critical issue
        score -= (high_issues * 1.0)      # -1 point per high issue
        score -= (medium_issues * 0.5)    # -0.5 points per medium issue
        score -= (low_issues * 0.2)       # -0.2 points per low issue
        
        # Factor in test results
        test_status = test_results.get('overall_status', 'UNKNOWN')
        if test_status == 'ERROR':
            score -= 1.0
        elif test_status == 'FAILED':
            score -= 0.5
        elif test_status == 'PASSED':
            score += 0.5  # Bonus for passing tests
        
        # Consider positive aspects
        positive_count = len(review_results.get('positive_aspects', []))
        score += (positive_count * 0.1)  # Small bonus for good practices
        
        # Ensure score is between 0 and 10
        return max(0.0, min(10.0, round(score, 1)))
    
    def _generate_summary(self, review_results: Dict[str, Any], test_results: Dict[str, Any], quality_score: float) -> str:
        """Generate a summary of the analysis."""
        
        # Count total issues
        total_issues = 0
        critical_issues = 0
        
        for category in ['style_issues', 'documentation_issues', 'potential_bugs', 
                        'error_handling_issues', 'security_concerns', 'performance_issues']:
            issues = review_results.get(category, [])
            total_issues += len(issues)
            critical_issues += len([i for i in issues if i.get('severity') == 'critical'])
        
        # Get base summary from review results
        base_summary = review_results.get('summary', '')
        
        # Generate comprehensive summary
        if quality_score >= 8.5:
            quality_desc = "excellent quality"
        elif quality_score >= 7.0:
            quality_desc = "good quality"
        elif quality_score >= 5.0:
            quality_desc = "acceptable quality with improvements needed"
        else:
            quality_desc = "significant quality concerns"
            
        summary_parts = [
            f"This pull request demonstrates {quality_desc} (Score: {quality_score}/10)."
        ]
        
        if total_issues > 0:
            summary_parts.append(f"Found {total_issues} issues that should be addressed")
            if critical_issues > 0:
                summary_parts.append(f"including {critical_issues} critical security or bug concerns")
            summary_parts.append("before merging.")
        else:
            summary_parts.append("No significant issues were identified.")
        
        # Add test results summary
        test_status = test_results.get('overall_status', 'UNKNOWN')
        if test_status == 'PASSED':
            summary_parts.append("All generated tests are passing.")
        elif test_status == 'FAILED':
            summary_parts.append("Some generated tests are failing.")
        elif test_status == 'ERROR':
            summary_parts.append("Test generation encountered errors.")
        elif test_status == 'SKIPPED':
            summary_parts.append("No new functions found for testing.")
        
        # Add original summary if available and meaningful
        if base_summary and base_summary != "Analysis completed":
            summary_parts.append(f"Additional context: {base_summary}")
        
        return " ".join(summary_parts)
    
    def _transform_issues(self, review_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Transform CrewAI issues into Reviewer Server format."""
        
        issues = []
        
        for category_key, category_name in self.category_mapping.items():
            category_issues = review_results.get(category_key, [])
            
            for issue in category_issues:
                try:
                    transformed_issue = {
                        'title': self._generate_issue_title(issue, category_name),
                        'description': issue.get('issue', 'Issue detected'),
                        'severity': self.severity_mapping.get(issue.get('severity', 'medium'), 'medium'),
                        'category': category_name,
                        'suggestion': issue.get('suggestion', 'Please review this issue'),
                    }
                    
                    # Try to extract file and line information from the line field
                    line_info = issue.get('line', '')
                    if line_info:
                        # Handle different line formats: "file.py:123", "123-125", "file.py", etc.
                        if ':' in line_info:
                            file_part, line_part = line_info.rsplit(':', 1)
                            transformed_issue['file'] = file_part
                            try:
                                transformed_issue['line'] = int(line_part.split('-')[0])
                            except (ValueError, IndexError):
                                transformed_issue['line'] = 1
                        elif line_info.isdigit():
                            transformed_issue['line'] = int(line_info)
                        elif '-' in line_info and line_info.replace('-', '').isdigit():
                            # Handle range like "123-125"
                            try:
                                transformed_issue['line'] = int(line_info.split('-')[0])
                            except (ValueError, IndexError):
                                transformed_issue['line'] = 1
                    
                    issues.append(transformed_issue)
                    
                except Exception as e:
                    logger.warning(f"Failed to transform issue: {str(e)}")
                    continue
        
        return issues
    
    def _transform_recommendations(self, review_results: Dict[str, Any], test_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Transform CrewAI results into recommendations."""
        
        recommendations = []
        
        # Add positive aspects as low-priority recommendations for improvement
        positive_aspects = review_results.get('positive_aspects', [])
        for aspect in positive_aspects:
            recommendations.append({
                'title': 'Continue Good Practices',
                'description': f"Continue the good practice: {aspect}",
                'category': 'best_practices',
                'priority': 'low',
                'benefits': 'Maintains code quality and consistency'
            })
        
        # Add testing recommendations based on test results
        test_status = test_results.get('overall_status', 'UNKNOWN')
        if test_status in ['FAILED', 'ERROR']:
            recommendations.append({
                'title': 'Review Test Results',
                'description': f"The automated testing workflow completed with status: {test_status}",
                'category': 'testing',
                'priority': 'high' if test_status == 'FAILED' else 'medium',
                'benefits': 'Ensures code reliability and prevents regressions',
                'example': 'Review the test output and fix any failing tests before merging'
            })
        elif test_status == 'SKIPPED':
            recommendations.append({
                'title': 'Add Unit Tests',
                'description': 'No new functions were found for testing. Consider adding unit tests for the new functionality.',
                'category': 'testing',
                'priority': 'medium',
                'benefits': 'Improves code coverage and reliability'
            })
        
        # Generate general improvement recommendations based on issues
        issue_categories = set()
        for category in ['style_issues', 'documentation_issues', 'potential_bugs', 
                        'error_handling_issues', 'security_concerns', 'performance_issues']:
            if review_results.get(category):
                issue_categories.add(self.category_mapping.get(category, 'general'))
        
        if 'security' in issue_categories:
            recommendations.append({
                'title': 'Security Review',
                'description': 'Security concerns were identified. Consider a dedicated security review.',
                'category': 'security',
                'priority': 'high',
                'benefits': 'Prevents security vulnerabilities in production'
            })
        
        if 'performance' in issue_categories:
            recommendations.append({
                'title': 'Performance Testing',
                'description': 'Performance issues were identified. Consider performance testing and optimization.',
                'category': 'performance',
                'priority': 'medium',
                'benefits': 'Ensures optimal system performance and user experience'
            })
        
        return recommendations
    
    def _generate_issue_title(self, issue: Dict[str, Any], category: str) -> str:
        """Generate a descriptive title for an issue."""
        
        issue_text = issue.get('issue', '')
        severity = issue.get('severity', 'medium')
        
        # Try to extract a meaningful title from the issue description
        if len(issue_text) > 50:
            # Use first sentence or meaningful phrase
            sentences = issue_text.split('.')
            title = sentences[0].strip()
            if len(title) > 80:
                title = title[:77] + "..."
        else:
            title = issue_text
        
        # Add category context if title is generic
        generic_phrases = ['issue', 'problem', 'concern', 'found', 'detected']
        if any(phrase in title.lower() for phrase in generic_phrases):
            title = f"{category.title()} Issue: {title}"
        
        return title or f"{category.title()} Issue Detected"