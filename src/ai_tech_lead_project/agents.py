import os
from crewai import Agent, LLM
from .tools.github_tools import github_tool

# Model catalog and validation utilities

def list_models():
    """
    Function to list available Gemini models with their specifications
    """
    available_models = {
        "models/gemini-2.5-pro-preview-03-25": {
            "version": "2.5-preview-03-25",
            "display_name": "Gemini 2.5 Pro Preview 03-25",
            "description": "Gemini 2.5 Pro Preview 03-25",
            "input_token_limit": 1048576,
            "output_token_limit": 65536,
            "supported_methods": ["generateContent", "countTokens", "createCachedContent", "batchGenerateContent"],
            "temperature": 1,
            "top_p": 0.95,
            "top_k": 64,
            "max_temperature": 2,
            "thinking": True
        },
        "models/gemini-2.5-pro": {
            "version": "2.5",
            "display_name": "Gemini 2.5 Pro",
            "description": "Stable release (June 17th, 2025) of Gemini 2.5 Pro",
            "input_token_limit": 1048576,
            "output_token_limit": 65536,
            "supported_methods": ["generateContent", "countTokens", "createCachedContent", "batchGenerateContent"],
            "temperature": 1,
            "top_p": 0.95,
            "top_k": 64,
            "max_temperature": 2,
            "thinking": True
        },
        "models/gemini-2.0-flash": {
            "version": "2.0",
            "display_name": "Gemini 2.0 Flash",
            "description": "Latest Gemini 2.0 Flash model",
            "input_token_limit": 1048576,
            "output_token_limit": 65536,
            "supported_methods": ["generateContent", "countTokens", "createCachedContent", "batchGenerateContent"],
            "temperature": 1,
            "top_p": 0.95,
            "top_k": 64,
            "max_temperature": 2,
            "thinking": True
        },
        "models/gemini-2.5-flash": {
            "version": "001",
            "display_name": "Gemini 2.5 Flash",
            "description": "Stable version of Gemini 2.5 Flash, our mid-size multimodal model",
            "input_token_limit": 1048576,
            "output_token_limit": 65536,
            "supported_methods": ["generateContent", "countTokens", "createCachedContent", "batchGenerateContent"],
            "temperature": 1,
            "top_p": 0.95,
            "top_k": 64,
            "max_temperature": 2,
            "thinking": True
        },
        "models/embedding-gecko-001": {
            "version": "001",
            "display_name": "Embedding Gecko",
            "description": "Obtain a distributed representation of a text.",
            "input_token_limit": 1024,
            "output_token_limit": 1,
            "supported_methods": ["embedText", "countTextTokens"]
        }
    }
    return available_models


def get_available_model_names():
    """Get list of available model names for CrewAI configuration"""
    models = list_models()
    return list(models.keys())


def validate_model_compatibility(model_name):
    """Validate if a model is compatible with CrewAI requirements."""
    models = list_models()
    core_id = model_name
    if model_name.startswith("models/"):
        core_id = model_name[len("models/"):]
    if model_name.startswith("gemini/"):
        core_id = model_name[len("gemini/"):]

    candidate_keys = [model_name, f"models/{core_id}", f"gemini/{core_id}"]
    model_key = next((k for k in candidate_keys if k in models), None)
    if model_key is None:
        return False

    model_info = models[model_key]
    required_methods = ["generateContent", "countTokens"]
    return all(method in model_info.get("supported_methods", []) for method in required_methods)


def _normalize_model_name(raw: str) -> str:
    core = raw
    if raw.startswith("models/"):
        core = raw[len("models/"):]
    if raw.startswith("gemini/"):
        core = raw[len("gemini/"):]
    return f"gemini/{core}"


# Configure LLM once at module level
_raw_model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip()
model_name = _normalize_model_name(_raw_model)

if not os.environ.get("GEMINI_API_KEY"):
    raise ValueError("GEMINI_API_KEY is not set. Please set it in your environment or .env file.")

if validate_model_compatibility(model_name):
    gemini_llm = LLM(
        model=model_name,
        api_key=os.environ.get("GEMINI_API_KEY"),
        temperature=0.5,
        num_retries=int(os.environ.get("LITELLM_NUM_RETRIES", "4")),
        request_timeout=int(os.environ.get("LITELLM_REQUEST_TIMEOUT", "120"))
    )
else:
    raise ValueError(f"Model {model_name} is not compatible. Set GEMINI_MODEL to one of: {', '.join(get_available_model_names())}")


# ============================================================
# STRICT DIFF-ONLY CONSTRAINT (exact text as specified)
# ============================================================
_CRITICAL_RULE = (
    "\n\nCRITICAL RULE:\n"
    "You MUST analyze ONLY the files listed in the FILES_IN_THIS_PR section.\n"
    "If a file is not listed there, you MUST ignore it.\n"
    "Referencing any file not listed is strictly forbidden.\n"
    "If unsure, do not assume existence of any other file."
)


def create_agents():
    """
    Factory function: creates FRESH agent instances for each PR run.
    Prevents any context/memory leakage between webhook runs.
    No global singletons. No agent reuse.
    """
    reviewer_agent = Agent(
        role='Expert AI Code Reviewer',
        goal='Perform a thorough, line-by-line code review ONLY on files present in the PR diff.',
        backstory=(
            "You are a Senior Software Engineer with a meticulous eye for detail. "
            "You ONLY review the exact code changes provided in the pull request diff. "
            "You never reference files that are not in the diff. "
            "You never make up or hallucinate file names."
            + _CRITICAL_RULE
        ),
        llm=gemini_llm,
        tools=[github_tool],
        verbose=True,
        allow_delegation=False,
        memory=False
    )

    tester_agent = Agent(
        role='Expert Python QA Engineer',
        goal='Generate a comprehensive suite of pytest unit tests ONLY for functions found in the PR diff.',
        backstory=(
            "You are a Quality Assurance Engineer who specializes in the pytest framework. "
            "You have a knack for identifying edge cases and ensuring complete code coverage. "
            "You follow a strict 'generate and verify' protocol. "
            "You ONLY write tests for code that appears in the PR diff. "
            "You never reference files that are not in the diff."
            + _CRITICAL_RULE
        ),
        llm=gemini_llm,
        tools=[github_tool],
        verbose=True,
        allow_delegation=False,
        memory=False
    )

    reporter_agent = Agent(
        role='AI Tech Lead Reporter',
        goal='Synthesize the code review and test results into a Markdown report and post it to the GitHub PR.',
        backstory=(
            "You are the communication hub for the AI Tech Lead team. "
            "You excel at taking complex technical data and presenting it clearly. "
            "You ONLY report on files that were present in the PR diff. "
            "You never reference files that are not in the diff."
            + _CRITICAL_RULE
        ),
        llm=gemini_llm,
        tools=[github_tool],
        verbose=True,
        allow_delegation=False,
        memory=False
    )

    return reviewer_agent, tester_agent, reporter_agent
