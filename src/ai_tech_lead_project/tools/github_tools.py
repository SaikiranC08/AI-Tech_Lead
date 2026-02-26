from github import Github, GithubException
from crewai.tools import BaseTool
from dotenv import load_dotenv
import os
from pydantic import BaseModel, Field, PrivateAttr


class GithubToolInput(BaseModel):
    command: str = Field(description="Command to execute: 'get_pr_diff' or 'post_pr_comment'")
    repo_name: str = Field(description="Repository name in format 'owner/repo'")
    pr_number: int = Field(description="Pull request number")
    comment_body: str = Field(default="", description="Comment body text to post (required for post_pr_comment)")


class GithubTools(BaseTool):
    name: str = "GitHub Tool"
    description: str = "A tool for interacting with GitHub repositories to fetch pull request diffs and post comments."
    args_schema: type[BaseModel] = GithubToolInput

    _github_client: Github | None = PrivateAttr(default=None)
    _enabled: bool = PrivateAttr(default=False)

    def __init__(self):
        super().__init__()
        load_dotenv()
        token = os.environ.get("GITHUB_ACCESS_TOKEN")
        if not token:
            self._github_client = None
            self._enabled = False
        else:
            self._github_client = Github(token)
            self._enabled = True

    def _run(self, command: str, repo_name: str, pr_number: int, comment_body: str = "", **kwargs):
        if not self._enabled or self._github_client is None:
            return (
                "GitHub tool is disabled: GITHUB_ACCESS_TOKEN is not set. "
                "Set it in your environment or .env file to enable GitHub operations."
            )
        try:
            repo = self._github_client.get_repo(repo_name)
            pr = repo.get_pull(pr_number)
        except GithubException as e:
            return f"Error accessing GitHub repository or pull request: {e}"

        if command == 'get_pr_diff':
            try:
                comparison = repo.compare(pr.base.sha, pr.head.sha)

                diff_content = []

                # === STRICT FILENAME MANIFEST ===
                filenames = [f.filename for f in comparison.files]
                diff_content.append("FILES_IN_THIS_PR:")
                for fname in filenames:
                    diff_content.append(f"- {fname}")
                diff_content.append("")
                diff_content.append("IMPORTANT: You MUST ONLY analyze the files listed above.")
                diff_content.append("Do NOT reference, invent, or hallucinate any other files.")
                diff_content.append("If you reference a file outside this manifest, the result is INVALID.")
                diff_content.append("")

                # === RAW DIFF WITH MARKERS ===
                diff_content.append("RAW_DIFF_START")
                diff_content.append(f"Comparing {pr.base.sha[:7]}...{pr.head.sha[:7]}")
                diff_content.append(f"Files changed: {len(comparison.files)}")
                diff_content.append("")

                for file in comparison.files:
                    diff_content.append(f"--- a/{file.filename}")
                    diff_content.append(f"+++ b/{file.filename}")
                    diff_content.append(f"@@ Status: {file.status} | Changes: +{file.additions} -{file.deletions} @@")
                    if file.patch:
                        diff_content.append(file.patch)
                    else:
                        diff_content.append("Binary file or no patch content available")
                    diff_content.append("")

                diff_content.append("RAW_DIFF_END")

                return "\n".join(diff_content)

            except GithubException as e:
                return f"Error getting PR diff: {e}"

        elif command == 'post_pr_comment':
            if not comment_body:
                return "Error: comment_body is required to post a comment."
            try:
                pr.create_issue_comment(comment_body)
                return "Comment posted successfully."
            except GithubException as e:
                return f"Error posting comment: {e}"
        else:
            return "Invalid command. Available commands: get_pr_diff, post_pr_comment"


# Create an instance of the tool to be used by agents
github_tool = GithubTools()


def get_pr_filenames(repo_name: str, pr_number: int) -> list[str]:
    """
    Returns list of filenames in the PR diff.
    Standalone function used for post-run output validation.
    """
    if not github_tool._enabled or github_tool._github_client is None:
        return []
    try:
        repo = github_tool._github_client.get_repo(repo_name)
        pr = repo.get_pull(pr_number)
        comparison = repo.compare(pr.base.sha, pr.head.sha)
        return [f.filename for f in comparison.files]
    except GithubException:
        return []
