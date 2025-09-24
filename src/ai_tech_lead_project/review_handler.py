"""
Review Handler Module
Transforms CrewAI analysis results into structured GitHub review comments and feedback.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class ReviewHandler:
    """Handles transformation of CrewAI analysis into GitHub review format."""
    
    def __init__(self):
        """Initialize the review handler."""
        self.severity_mapping = {
            'critical': '🔴 Critical',
            'high': '🟠 High',
            'medium': '🟡 Medium', 
            'low': '🟢 Low',
            'info': 'ℹ️ Info'
        }
        
        self.category_emojis = {
            'security': '🔐',
            'performance': '⚡',
            'maintainability': '🔧',
            'readability': '📖',
            'testing': '🧪',
            'documentation': '📝',
            'best_practices': '✅',
            'code_style': '💅',
            'logic': '🤔',
            'architecture': '🏗️'
        }
    
    def process_analysis(self, analysis: Dict[str, Any], pr_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process CrewAI analysis results and transform them into GitHub review format.
        
        Args:
            analysis: CrewAI analysis results
            pr_info: Pull request information
            
        Returns:
            Dict containing review data for GitHub API
        """
        try:
            logger.info(f"Processing analysis for PR #{pr_info.get('number')}")
            
            # Extract analysis components
            issues = analysis.get('issues', [])
            recommendations = analysis.get('recommendations', [])
            quality_score = analysis.get('quality_score', 0)
            summary = analysis.get('summary', '')
            
            # Generate review body (main comment)
            review_body = self._generate_review_body(issues, recommendations, quality_score, summary)
            
            # Generate line-specific comments
            line_comments = self._generate_line_comments(issues, recommendations)
            
            # Determine review event type
            review_event = self._determine_review_event(issues, quality_score)
            
            review_data = {
                'body': review_body,
                'event': review_event,
                'comments': line_comments
            }
            
            logger.info(f"Generated review with {len(line_comments)} line comments and event: {review_event}")
            return review_data
            
        except Exception as e:
            logger.error(f"Error processing analysis: {str(e)}")
            # Return a basic error review
            return {
                'body': '❌ **Error Processing Review**\n\nThere was an error processing the automated code review. Please check the analysis results manually.',
                'event': 'COMMENT',
                'comments': []
            }
    
    def _generate_review_body(self, issues: List[Dict], recommendations: List[Dict], 
                            quality_score: float, summary: str) -> str:
        """Generate the main review body comment."""
        
        # Header with quality score
        score_emoji = self._get_score_emoji(quality_score)
        body = f"## 🤖 Automated Code Review\n\n"
        body += f"{score_emoji} **Quality Score: {quality_score}/10**\n\n"
        
        # Summary section
        if summary:
            body += f"### 📋 Summary\n{summary}\n\n"
        
        # Issues summary
        if issues:
            critical_issues = [i for i in issues if i.get('severity') == 'critical']
            high_issues = [i for i in issues if i.get('severity') == 'high']
            
            body += f"### 🔍 Issues Found\n"
            body += f"- **Total Issues:** {len(issues)}\n"
            
            if critical_issues:
                body += f"- **Critical Issues:** {len(critical_issues)} 🔴\n"
            if high_issues:
                body += f"- **High Priority Issues:** {len(high_issues)} 🟠\n"
            
            # Group issues by category
            categories = {}
            for issue in issues:
                category = issue.get('category', 'general')
                if category not in categories:
                    categories[category] = []
                categories[category].append(issue)
            
            body += f"\n**Issues by Category:**\n"
            for category, cat_issues in categories.items():
                emoji = self.category_emojis.get(category, '🔸')
                body += f"- {emoji} {category.title()}: {len(cat_issues)} issues\n"
        else:
            body += f"### ✅ No Issues Found\nGreat job! No significant issues were detected in this pull request.\n"
        
        # Recommendations summary
        if recommendations:
            body += f"\n### 💡 Key Recommendations\n"
            for i, rec in enumerate(recommendations[:5], 1):  # Show top 5 recommendations
                body += f"{i}. {rec.get('description', 'No description')}\n"
            
            if len(recommendations) > 5:
                body += f"\n*...and {len(recommendations) - 5} more recommendations in the detailed comments below.*\n"
        
        # Footer
        body += f"\n---\n"
        body += f"🤖 *Generated by AI Tech Lead at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC*\n"
        body += f"💬 This review was automatically generated based on code analysis. Please review the suggestions and apply them as needed."
        
        return body
    
    def _generate_line_comments(self, issues: List[Dict], recommendations: List[Dict]) -> List[Dict]:
        """Generate line-specific comments for files."""
        comments = []
        
        # Process issues that have file/line information
        for issue in issues:
            if issue.get('file') and issue.get('line'):
                comment = self._format_issue_comment(issue)
                if comment:
                    comments.append(comment)
        
        # Process recommendations that have file/line information
        for rec in recommendations:
            if rec.get('file') and rec.get('line'):
                comment = self._format_recommendation_comment(rec)
                if comment:
                    comments.append(comment)
        
        # Remove duplicates based on file and line
        seen = set()
        unique_comments = []
        for comment in comments:
            key = (comment['path'], comment['line'])
            if key not in seen:
                seen.add(key)
                unique_comments.append(comment)
        
        return unique_comments
    
    def _format_issue_comment(self, issue: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """Format an issue into a line comment."""
        try:
            severity = issue.get('severity', 'medium')
            severity_label = self.severity_mapping.get(severity, '🔸 Issue')
            category = issue.get('category', 'general')
            category_emoji = self.category_emojis.get(category, '🔸')
            
            body = f"{severity_label} {category_emoji} **{issue.get('title', 'Code Issue')}**\n\n"
            
            if issue.get('description'):
                body += f"{issue['description']}\n\n"
            
            if issue.get('suggestion'):
                body += f"**💡 Suggested Fix:**\n{issue['suggestion']}\n\n"
            
            if issue.get('code_example'):
                body += f"**Example:**\n```python\n{issue['code_example']}\n```\n\n"
            
            # Add references if available
            if issue.get('references'):
                body += f"**📚 References:** {issue['references']}\n"
            
            return {
                'path': issue['file'],
                'line': int(issue['line']),
                'body': body.strip()
            }
            
        except Exception as e:
            logger.error(f"Error formatting issue comment: {str(e)}")
            return None
    
    def _format_recommendation_comment(self, rec: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """Format a recommendation into a line comment."""
        try:
            category = rec.get('category', 'general')
            category_emoji = self.category_emojis.get(category, '💡')
            
            body = f"💡 {category_emoji} **Recommendation: {rec.get('title', 'Code Improvement')}**\n\n"
            
            if rec.get('description'):
                body += f"{rec['description']}\n\n"
            
            if rec.get('benefits'):
                body += f"**✨ Benefits:**\n{rec['benefits']}\n\n"
            
            if rec.get('example'):
                body += f"**Example Implementation:**\n```python\n{rec['example']}\n```\n\n"
            
            # Add priority if available
            priority = rec.get('priority', 'medium')
            if priority in ['high', 'critical']:
                body = f"⚠️ **High Priority** - " + body
            
            return {
                'path': rec['file'],
                'line': int(rec['line']),
                'body': body.strip()
            }
            
        except Exception as e:
            logger.error(f"Error formatting recommendation comment: {str(e)}")
            return None
    
    def _determine_review_event(self, issues: List[Dict], quality_score: float) -> str:
        """Determine the review event type based on issues and quality score."""
        
        # Check for critical issues
        critical_issues = [i for i in issues if i.get('severity') == 'critical']
        if critical_issues:
            return 'REQUEST_CHANGES'
        
        # Check for high severity issues
        high_issues = [i for i in issues if i.get('severity') == 'high']
        if len(high_issues) >= 3:  # Multiple high issues
            return 'REQUEST_CHANGES'
        
        # Check quality score
        if quality_score < 6.0:
            return 'REQUEST_CHANGES'
        elif quality_score >= 8.5 and not high_issues:
            return 'APPROVE'
        else:
            return 'COMMENT'  # Neutral feedback
    
    def _get_score_emoji(self, score: float) -> str:
        """Get emoji representation of quality score."""
        if score >= 9.0:
            return "🏆"
        elif score >= 8.0:
            return "✨"
        elif score >= 7.0:
            return "👍"
        elif score >= 6.0:
            return "👌"
        elif score >= 4.0:
            return "⚠️"
        else:
            return "🔴"
    
    def validate_analysis(self, analysis: Dict[str, Any]) -> bool:
        """Validate that analysis contains required fields."""
        try:
            # Check for required top-level fields
            if not isinstance(analysis, dict):
                return False
            
            # At minimum, we expect some form of feedback
            has_issues = 'issues' in analysis and isinstance(analysis['issues'], list)
            has_recommendations = 'recommendations' in analysis and isinstance(analysis['recommendations'], list)
            has_summary = 'summary' in analysis and analysis['summary']
            
            return has_issues or has_recommendations or has_summary
            
        except Exception as e:
            logger.error(f"Error validating analysis: {str(e)}")
            return False
    
    def sanitize_github_comment(self, comment: str) -> str:
        """Sanitize comment content for GitHub API."""
        # Remove potentially problematic characters or patterns
        # Limit comment length to avoid GitHub API limits
        max_length = 65536  # GitHub's maximum comment length
        
        if len(comment) > max_length:
            comment = comment[:max_length - 100] + "\n\n*Comment truncated due to length limits.*"
        
        # Ensure proper markdown formatting
        comment = comment.strip()
        
        return comment