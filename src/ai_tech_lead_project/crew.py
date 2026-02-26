from crewai import Crew, Process
from .agents import create_agents
from .tasks import AITechLeadTasks
from .tools.github_tools import get_pr_filenames
from .utils.validators import validate_output_filenames
import os
import time
import random


class AITechLeadCrew:
    def __init__(self, repo_name: str, pr_number: int):
        self.repo_name = repo_name
        self.pr_number = pr_number
        self.tasks = AITechLeadTasks()

    def run(self):
        # === FRESH AGENTS PER RUN (never reuse) ===
        reviewer_agent, tester_agent, reporter_agent = create_agents()

        review_task = self.tasks.review_pr_task(reviewer_agent, self.repo_name, self.pr_number)
        test_task = self.tasks.test_pr_task(tester_agent, self.repo_name, self.pr_number)

        report_task = self.tasks.report_task(
            reporter_agent,
            self.repo_name,
            self.pr_number,
            context=[review_task, test_task]
        )

        # === STATELESS CREW: memory=False ===
        crew = Crew(
            agents=[reviewer_agent, tester_agent, reporter_agent],
            tasks=[review_task, test_task, report_task],
            process=Process.sequential,
            verbose=True,
            memory=False,
            cache=False
        )

        # Orchestration-level retry for transient LLM 5xx errors
        max_attempts = int(os.environ.get("CREW_KICKOFF_MAX_ATTEMPTS", "2"))
        base_delay = float(os.environ.get("CREW_KICKOFF_BASE_DELAY", "2.0"))
        max_delay = float(os.environ.get("CREW_KICKOFF_MAX_DELAY", "30.0"))

        last_exc = None
        for attempt in range(1, max_attempts + 1):
            try:
                print(f"Crew kickoff attempt {attempt}/{max_attempts} for {self.repo_name}# {self.pr_number}...")
                result = crew.kickoff()

                # === HARD-FAIL OUTPUT VALIDATION ===
                # If invalid filenames are found, ValueError is raised.
                # Comment will NOT be posted.
                self._validate_output(result)

                return result
            except ValueError as e:
                # Hard validation failure — do NOT retry, do NOT post comment
                print(f"\n{'='*60}")
                print(f"❌ HARD VALIDATION FAILURE for {self.repo_name}# {self.pr_number}:")
                print(f"   {e}")
                print(f"   Comment was NOT posted to GitHub.")
                print(f"{'='*60}\n")
                raise
            except Exception as e:
                msg = str(e).lower()
                is_overload = ("503" in msg) or ("overloaded" in msg) or ("unavailable" in msg)
                if attempt < max_attempts and is_overload:
                    delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
                    delay = delay * (0.8 + 0.4 * random.random())
                    print(f"Transient LLM error (attempt {attempt}): {e}. Retrying in {delay:.1f}s...")
                    time.sleep(delay)
                    last_exc = e
                    continue
                last_exc = e
                break

        raise last_exc

    def _validate_output(self, result):
        """
        Post-run validation: raises ValueError if any agent output
        references files NOT in the PR diff.
        If invalid → comment is NOT posted.
        """
        # Get the list of valid filenames from the PR
        valid_filenames = get_pr_filenames(self.repo_name, self.pr_number)
        if not valid_filenames:
            print("⚠️ Could not retrieve PR filenames for validation. Skipping output validation.")
            return

        # Hard-fail validation: raises ValueError if invalid references found
        output_text = str(result)
        validate_output_filenames(output_text, set(valid_filenames))
        print("✅ Output validation passed: all referenced files are in the PR diff.")
