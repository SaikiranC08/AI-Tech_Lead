from crewai import Crew, Process
from .agents import reviewer_agent, tester_agent, reporter_agent
from .tasks import AITechLeadTasks
import os
import time
import random


class AITechLeadCrew:
    def __init__(self, repo_name: str, pr_number: int):
        self.repo_name = repo_name
        self.pr_number = pr_number
        self.tasks = AITechLeadTasks()

    def run(self):
        review_task = self.tasks.review_pr_task(reviewer_agent, self.repo_name, self.pr_number)
        test_task = self.tasks.test_pr_task(tester_agent, self.repo_name, self.pr_number)

        report_task = self.tasks.report_task(
            reporter_agent,
            self.repo_name,
            self.pr_number,
            context=[review_task, test_task]
        )

        crew = Crew(
            agents=[reviewer_agent, tester_agent, reporter_agent],
            tasks=[review_task, test_task, report_task],
            process=Process.sequential,
            verbose=True
        )

        # Orchestration-level retry to handle transient LLM 5xx errors (e.g., Vertex 503 overloaded)
        max_attempts = int(os.environ.get("CREW_KICKOFF_MAX_ATTEMPTS", "2"))
        base_delay = float(os.environ.get("CREW_KICKOFF_BASE_DELAY", "2.0"))
        max_delay = float(os.environ.get("CREW_KICKOFF_MAX_DELAY", "30.0"))

        last_exc = None
        for attempt in range(1, max_attempts + 1):
            try:
                print(f"Crew kickoff attempt {attempt}/{max_attempts} for {self.repo_name}# {self.pr_number}...")
                result = crew.kickoff()
                return result
            except Exception as e:
                msg = str(e).lower()
                is_overload = ("503" in msg) or ("overloaded" in msg) or ("unavailable" in msg)
                if attempt < max_attempts and is_overload:
                    # Exponential backoff with jitter
                    delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
                    delay = delay * (0.8 + 0.4 * random.random())
                    print(f"Transient LLM error encountered (attempt {attempt}): {e}. Retrying in {delay:.1f}s...")
                    time.sleep(delay)
                    last_exc = e
                    continue
                # non-retryable or exhausted attempts
                last_exc = e
                break

        raise last_exc
