import os
import logging
import requests
import google.generativeai as genai
from crewai.tools import BaseTool
from pydantic import Field, BaseModel, PrivateAttr
from typing import Dict, Any, List, Optional, Type
import re
import json
import subprocess
import tempfile
from crewai import Agent, Task
from dotenv import load_dotenv



# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class UnitTestSchema(BaseModel):
    """Input schema for the Unit Test Tool."""
    pr_info: Dict[str, Any] = Field(..., description="Dictionary containing pull request information like diff_url, repo_name, etc.")

class UnitTestTool(BaseTool):
    name: str = "AI Unit Test Generator"
    description: str = "Generates pytest unit tests for code changes in a pull request."
    args_schema: Type[BaseModel] = UnitTestSchema
    api_key: str = Field(default_factory=lambda: os.getenv('GEMINI_API_KEY'))
    _model: Any = PrivateAttr(default=None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables.")
        genai.configure(api_key=self.api_key)
        self._model = genai.GenerativeModel("gemini-1.5-pro")

    def _run(self, pr_info: Dict[str, Any]) -> Dict[str, Any]:
        """Main execution method, matches args_schema exactly."""
        diff_url = pr_info.get("diff_url")
        if not diff_url:
            return {"test_files": [], "summary": "No diff URL provided"}
        diff_content = self.get_pr_diff(diff_url)
        if not diff_content:
            return {"test_files": [], "summary": "Failed to fetch PR diff"}
        functions = self.extract_functions_from_diff(diff_content)
        return self.generate_tests(functions, pr_info)

    async def _arun(self, *args, **kwargs):
        """Async execution not implemented"""
        # TODO: Async method not implemented yet
        raise NotImplementedError("Async execution not supported")

    def get_pr_diff(self, diff_url: str) -> str:
        try:
            resp = requests.get(diff_url)
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            logger.error(f"Error fetching PR diff: {e}")
            return ""

    def extract_functions_from_diff(self, diff_content: str) -> List[Dict[str, str]]:
        functions = []
        files = re.split(r'^diff --git', diff_content, flags=re.MULTILINE)
        for file_content in files[1:]:
            file_match = re.search(r'a/(.+?) b/(.+)', file_content)
            if not file_match:
                continue
            file_path = file_match.group(2)
            if not file_path.endswith(".py"):
                continue
            added_lines = [line[1:] for line in file_content.splitlines() if line.startswith('+') and not line.startswith('+++')]
            for line in added_lines:
                if re.match(r'^\s*def\s+\w+\s*\(', line):
                    functions.append({"file_path": file_path, "function_code": line, "function_name": re.search(r'def\s+(\w+)', line).group(1)})
        return functions

    def generate_tests(self, functions: List[Dict[str, str]], pr_info: Dict[str, Any]) -> Dict[str, Any]:
        test_results = []
        for func in functions:
            prompt = f"""
Generate pytest tests for {func['function_name']} in {func['file_path']}.
Include normal cases, edge cases, and descriptive test names.
Return JSON: {{'test_filename':'test_{func['function_name']}.py','test_code':'code_here','test_description':'desc'}}
"""
            try:
                response = self._model.generate_content(prompt)
                json_text = response.text.strip()
                if '```json' in json_text:
                    json_start = json_text.find('```json') + 7
                    json_end = json_text.find('```', json_start)
                    json_text = json_text[json_start:json_end].strip()
                test_data = json.loads(json_text)
                test_data.update({"function_name": func['function_name'], "file_path": func['file_path']})
                test_results.append(test_data)
            except Exception as e:
                test_results.append({"function_name": func['function_name'], "file_path": func['file_path'],
                                     "test_filename": f"test_{func['function_name']}.py",
                                     "test_code": "# Failed to generate",
                                     "test_description": str(e),
                                     "error": str(e)})
        return {"test_files": test_results, "summary": f"Generated tests for {len(test_results)} functions"}

    def run_tests(self, test_files: List[Dict[str, Any]]) -> Dict[str, Any]:
        results = []
        for tf in test_files:
            if 'error' in tf:
                results.append({"test_filename": tf['test_filename'], "status": "ERROR", "output": tf['error']})
                continue
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as tmp:
                tmp.write(tf['test_code'])
                tmp_path = tmp.name
            try:
                proc = subprocess.run(["python", "-m", "pytest", tmp_path, "-v", "--tb=short"],
                                      capture_output=True, text=True, timeout=30)
                status = "PASSED" if proc.returncode == 0 else "FAILED"
                results.append({"test_filename": tf['test_filename'], "status": status, "output": proc.stdout + proc.stderr})
            except Exception as e:
                results.append({"test_filename": tf['test_filename'], "status": "ERROR", "output": str(e)})
            finally:
                try: os.unlink(tmp_path)
                except: pass
        overall = "PASSED" if all(r['status'] == "PASSED" for r in results) else "FAILED"
        return {"test_results": results, "overall_status": overall, "summary": f"Executed {len(results)} tests. Overall: {overall}"}

# -----------------------------
# Create agent helpers
# -----------------------------
def create_tester_agent(unit_test_tool: UnitTestTool) -> Agent:
    return Agent(
        role="AI Unit Tester",
        goal="Generate robust unit tests for new code in PRs",
        backstory="You are an AI tester expert in generating pytest tests",
        tools=[unit_test_tool],
        allow_delegation=False,
        verbose=True
    )

def create_testing_task(tester_agent: Agent, pr_info: Dict[str, Any]) -> Task:
    return Task(
        description=f"Generate unit tests for PR #{pr_info.get('number','N/A')} - {pr_info.get('title','N/A')}",
        expected_output="A JSON object with 'test_filename' and 'test_code' for each function",
        agent=tester_agent,
        inputs={'pr_info': pr_info}
    )
