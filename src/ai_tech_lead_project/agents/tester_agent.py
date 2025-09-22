"""
AI Tech Lead - Tester Agent
AI-powered unit test generation and execution agent using Gemini API.
"""

import os
import json
import re
import logging
import tempfile
import subprocess
from typing import Dict, Any, List, Tuple
import google.generativeai as genai
from crewai import Agent, Task
from dotenv import load_dotenv
import requests

load_dotenv()
logger = logging.getLogger(__name__)

class UnitTestTool:
    """Tool for generating and running AI-powered unit tests using Gemini API."""
    
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
    
    def extract_functions_from_diff(self, diff_content: str) -> List[Dict[str, str]]:
        """Extract function definitions and their context from diff content."""
        functions = []
        
        # Split diff into files
        files = re.split(r'^diff --git', diff_content, flags=re.MULTILINE)
        
        for file_content in files[1:]:  # Skip first empty split
            # Extract file path
            file_match = re.search(r'a/(.+?) b/(.+)', file_content)
            if not file_match:
                continue
            
            file_path = file_match.group(2)
            
            # Only process Python files for now
            if not file_path.endswith('.py'):
                continue
            
            # Extract added lines (lines starting with +)
            added_lines = []
            lines = file_content.split('\n')
            current_context = []
            
            for line in lines:
                if line.startswith('@@'):
                    # Line number context
                    current_context.append(line)
                elif line.startswith('+') and not line.startswith('+++'):
                    # Added line
                    clean_line = line[1:]  # Remove + prefix
                    added_lines.append(clean_line)
                    current_context.append(clean_line)
                elif not line.startswith('-') and not line.startswith('+++') and not line.startswith('---'):
                    # Context line
                    current_context.append(line[1:] if line.startswith(' ') else line)
            
            # Look for function definitions in added lines
            for i, line in enumerate(added_lines):
                if re.match(r'^\s*def\s+\w+\s*\(', line):
                    # Extract function definition
                    func_lines = [line]
                    
                    # Try to get the complete function
                    indent_level = len(line) - len(line.lstrip())
                    
                    # Get surrounding context for better understanding
                    context_start = max(0, i - 5)
                    context_end = min(len(current_context), i + 20)
                    context_lines = current_context[context_start:context_end]
                    
                    functions.append({
                        'file_path': file_path,
                        'function_code': '\n'.join(func_lines),
                        'context': '\n'.join(context_lines),
                        'function_name': re.search(r'def\s+(\w+)', line).group(1) if re.search(r'def\s+(\w+)', line) else 'unknown'
                    })
        
        return functions
    
    def generate_tests(self, functions: List[Dict[str, str]], pr_info: Dict[str, Any]) -> Dict[str, Any]:
        """Generate pytest unit tests for extracted functions."""
        
        if not functions:
            return {
                "test_files": [],
                "summary": "No new functions found to test in the PR diff."
            }
        
        test_results = []
        
        for func_info in functions:
            prompt = f"""
Generate comprehensive pytest unit tests for the following Python function.

**Repository:** {pr_info.get('repo_name', 'N/A')}
**File:** {func_info['file_path']}
**Function:** {func_info['function_name']}

**Function Code and Context:**
```python
{func_info['context']}
```

**Instructions:**
1. Create a complete pytest test file that can be executed independently
2. Include necessary imports (pytest, unittest.mock if needed)
3. Test normal cases, edge cases, and error conditions
4. Use descriptive test method names following pytest conventions
5. Add docstrings to test methods explaining what they test
6. Mock external dependencies appropriately
7. Test both positive and negative scenarios
8. Include parameterized tests where applicable

**Requirements:**
- Test file should be named test_{func_info['function_name']}.py
- Use pytest fixtures where appropriate
- Include setup and teardown if needed
- Test should be runnable with: pytest test_filename.py
- Follow Python testing best practices

**Output Format:**
Return a JSON object with the following structure:
{{
    "test_filename": "test_{func_info['function_name']}.py",
    "test_code": "complete_pytest_test_code_here",
    "test_description": "description_of_what_the_tests_cover",
    "dependencies": ["list", "of", "required", "imports", "or", "packages"]
}}

Generate comprehensive tests that thoroughly exercise the function's behavior.
"""

            try:
                response = self.model.generate_content(prompt)
                response_text = response.text.strip()
                
                # Extract JSON from response
                if '```json' in response_text:
                    json_start = response_text.find('```json') + 7
                    json_end = response_text.find('```', json_start)
                    json_text = response_text[json_start:json_end].strip()
                elif response_text.startswith('{'):
                    json_text = response_text
                else:
                    json_start = response_text.find('{')
                    json_end = response_text.rfind('}') + 1
                    json_text = response_text[json_start:json_end] if json_start >= 0 else '{}'
                
                test_data = json.loads(json_text)
                
                # Validate required fields
                required_fields = ['test_filename', 'test_code', 'test_description']
                for field in required_fields:
                    if field not in test_data:
                        test_data[field] = f"Generated for {func_info['function_name']}"
                
                test_data['function_name'] = func_info['function_name']
                test_data['file_path'] = func_info['file_path']
                test_results.append(test_data)
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse test generation response for {func_info['function_name']}: {e}")
                test_results.append({
                    'function_name': func_info['function_name'],
                    'file_path': func_info['file_path'],
                    'test_filename': f"test_{func_info['function_name']}.py",
                    'test_code': f"# Test generation failed for {func_info['function_name']}",
                    'test_description': f"Failed to generate tests: {str(e)}",
                    'dependencies': [],
                    'error': str(e)
                })
            except Exception as e:
                logger.error(f"Error generating tests for {func_info['function_name']}: {e}")
                test_results.append({
                    'function_name': func_info['function_name'],
                    'file_path': func_info['file_path'],
                    'test_filename': f"test_{func_info['function_name']}.py",
                    'test_code': f"# Test generation error for {func_info['function_name']}",
                    'test_description': f"Error during test generation: {str(e)}",
                    'dependencies': [],
                    'error': str(e)
                })
        
        return {
            "test_files": test_results,
            "summary": f"Generated tests for {len(test_results)} functions"
        }
    
    def run_tests(self, test_files: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Execute generated tests using pytest."""
        
        if not test_files:
            return {
                "test_results": [],
                "overall_status": "SKIPPED",
                "summary": "No tests to run"
            }
        
        results = []
        
        for test_file in test_files:
            if 'error' in test_file:
                results.append({
                    'test_filename': test_file['test_filename'],
                    'status': 'ERROR',
                    'output': f"Test generation failed: {test_file['error']}",
                    'function_name': test_file['function_name']
                })
                continue
            
            # Create temporary test file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as temp_file:
                temp_file.write(test_file['test_code'])
                temp_file_path = temp_file.name
            
            try:
                # Run pytest on the temporary file
                result = subprocess.run(
                    ['python', '-m', 'pytest', temp_file_path, '-v', '--tb=short'],
                    capture_output=True,
                    text=True,
                    timeout=30  # 30 second timeout
                )
                
                status = "PASSED" if result.returncode == 0 else "FAILED"
                output = result.stdout + result.stderr
                
                results.append({
                    'test_filename': test_file['test_filename'],
                    'function_name': test_file['function_name'],
                    'status': status,
                    'output': output,
                    'return_code': result.returncode
                })
                
            except subprocess.TimeoutExpired:
                results.append({
                    'test_filename': test_file['test_filename'],
                    'function_name': test_file['function_name'],
                    'status': 'TIMEOUT',
                    'output': 'Test execution timed out after 30 seconds',
                    'return_code': -1
                })
            except Exception as e:
                results.append({
                    'test_filename': test_file['test_filename'],
                    'function_name': test_file['function_name'],
                    'status': 'ERROR',
                    'output': f'Error executing tests: {str(e)}',
                    'return_code': -1
                })
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_file_path)
                except:
                    pass
        
        # Determine overall status
        statuses = [r['status'] for r in results]
        if 'ERROR' in statuses or 'TIMEOUT' in statuses:
            overall_status = 'ERROR'
        elif 'FAILED' in statuses:
            overall_status = 'FAILED'
        elif all(s == 'PASSED' for s in statuses):
            overall_status = 'PASSED'
        else:
            overall_status = 'MIXED'
        
        return {
            "test_results": results,
            "overall_status": overall_status,
            "summary": f"Executed {len(results)} test suites. Status: {overall_status}"
        }

def create_tester_agent() -> Agent:
    """Create and configure the Tester Agent."""
    
    return Agent(
        role="AI Testing Specialist",
        goal="Generate comprehensive unit tests for new code and ensure proper test coverage",
        backstory="""You are an expert Software Testing Engineer with extensive experience in 
        test-driven development, unit testing, and quality assurance. You specialize in creating 
        comprehensive test suites that cover edge cases, error conditions, and ensure code 
        reliability. You're proficient with pytest, unittest, and mocking frameworks, and you 
        understand the importance of maintainable, readable tests that serve as documentation 
        for the code they test.""",
        verbose=True,
        allow_delegation=False,
        tools=[]
    )

def create_testing_task(agent: Agent, pr_info: Dict[str, Any]) -> Task:
    """Create a unit testing task for the Tester Agent."""
    
    return Task(
        description=f"""
        Generate and execute comprehensive unit tests for Pull Request #{pr_info.get('number')} 
        in repository {pr_info.get('repo_name')}.
        
        **Task Details:**
        - Analyze the code diff from: {pr_info.get('diff_url')}
        - Extract new or modified functions from the diff
        - Generate pytest unit tests for each identified function
        - Execute the generated tests and report results
        - Ensure comprehensive test coverage including edge cases
        
        **PR Information:**
        - Title: {pr_info.get('title')}
        - Author: {pr_info.get('pr_author')}
        - Branch: {pr_info.get('head_branch')} → {pr_info.get('base_branch')}
        
        Use the UnitTestTool to:
        1. Fetch and parse the PR diff
        2. Extract function definitions from added/modified code
        3. Generate appropriate pytest tests for each function
        4. Execute the tests and capture results
        """,
        expected_output="""A comprehensive testing report containing:
        1. List of functions identified for testing
        2. Generated test code for each function
        3. Test execution results (PASSED/FAILED/ERROR)
        4. Coverage analysis and recommendations
        5. Summary of test quality and completeness
        
        The output should include both the generated test code and execution results,
        with clear indication of any failures or issues encountered during testing.""",
        agent=agent
    )