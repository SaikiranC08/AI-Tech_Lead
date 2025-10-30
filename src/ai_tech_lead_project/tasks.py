from crewai import Task
from textwrap import dedent
from .tools.github_tools import github_tool

class AITechLeadTasks():
    def review_pr_task(self, agent, repo_name, pr_number):
        return Task(
            description=dedent(f"""
                Analyze the code changes in the pull request #{pr_number} from the repository '{repo_name}'.
                You MUST use the 'GitHub Tool' to fetch the code diff before you begin your analysis.
                
                **Follow these steps:**
                1. Use the `get_pr_diff` command with the GitHub tool to get the code changes.
                2. Perform a thorough, line-by-line code review on the diff.
                3. Analyze the code against these criteria: Potential Bugs, Style & Formatting, Optimization, and Documentation.
                4. Consolidate all findings into a single, well-formed JSON object.

                **Example of Desired JSON Output:**
                ```json
                {{
                  "style_issues": [
                    {{"line": 5, "description": "Variable 'x' is too generic. Consider renaming to 'user_count'."}}
                  ],
                  "potential_bugs":,
                  "documentation_issues":,
                  "optimization_recommendations":
                }}
                ```
                Your final answer MUST be only the JSON object.
            """),
            expected_output="A single JSON object containing categorized code review feedback.",
            agent=agent,
            tools=[github_tool],
            async_execution=True
        )

    def test_pr_task(self, agent, repo_name, pr_number):
        return Task(
            description=dedent(f"""
                Analyze the code changes in Pull Request #{pr_number} from repository '{repo_name}'.
                Your task is to generate a comprehensive suite of unit tests.
                Assume the code is Python and the testing framework is pytest.

                **Follow these steps:**
                1. Use the `get_pr_diff` command with the GitHub tool to get the code changes.
                2. Identify the new or modified functions in the diff.
                3. For each function, write a valid, executable pytest test suite that covers the happy path, edge cases, and error conditions.

                Your final answer MUST be a single string containing the raw Python code for the tests.
                If you cannot generate tests (e.g., the code is not Python or has severe syntax errors),
                your output should be the single line: "Tests SKIPPED due to non-testable code."
            """),
            expected_output="A string containing the raw Python code for a pytest test suite, or a skip message.",
            agent=agent,
            tools=[github_tool],
            async_execution=True
        )

    def report_task(self, agent, repo_name, pr_number, context):
        return Task(
            description=dedent(f"""
                Synthesize the code review analysis and unit test results from the context into a single,
                well-formatted Markdown report.

                **Report Structure:**
                1.  Start with the main heading: `## AI Tech Lead Analysis`.
                2.  Provide a brief, one-sentence executive summary.
                3.  Create a "Code Review" section with subheadings for each category of issue (e.g., ### Potential Bugs).
                4.  Under each subheading, list the issues as bullet points.
                5.  Create a "Unit Tests" section. If tests were generated, add `### Generated Pytest Suite` and place the test code inside a Python code block. If skipped, state the reason.

                After generating the report, use the `post_pr_comment` command with the GitHub tool to post it
                on Pull Request #{pr_number} in repository '{repo_name}'.
            """),
            expected_output="A confirmation message stating that the report has been successfully posted.",
            agent=agent,
            context=context,
            tools=[github_tool]
        )