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
        },        "models/gemini-2.0-flash": {
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

# Modified usage example that's more relevant to your CrewAI setup
def get_available_model_names():
    """Get list of available model names for CrewAI configuration"""
    models = list_models()
    return list(models.keys())


def validate_model_compatibility(model_name):
    """Validate if a model is compatible with CrewAI requirements.
    Accepts both Google API-style ids (e.g., 'models/gemini-2.5-pro') and
    LiteLLM-style ids (e.g., 'gemini/gemini-2.5-pro').
    """
    models = list_models()

    # Build candidate keys to look up in our catalog
    core_id = model_name
    if model_name.startswith("models/"):
        core_id = model_name[len("models/") :]
    if model_name.startswith("gemini/"):
        core_id = model_name[len("gemini/") :]

    candidate_keys = [
        model_name,  # as-is
        f"models/{core_id}",
        f"gemini/{core_id}",
    ]

    # Find the first match in our catalog
    model_key = next((k for k in candidate_keys if k in models), None)
    if model_key is None:
        return False

    model_info = models[model_key]
    required_methods = ["generateContent", "countTokens"]
    return all(method in model_info.get("supported_methods", []) for method in required_methods)


# Configure the LLM once, then use it for all agents
# Prefer env var GEMINI_MODEL; accept 'models/...' or 'gemini/...', normalize to 'gemini/<core>' for LiteLLM

def _normalize_model_name(raw: str) -> str:
    core = raw
    if raw.startswith("models/"):
        core = raw[len("models/"):]
    if raw.startswith("gemini/"):
        core = raw[len("gemini/"):]
    return f"gemini/{core}"

# Default to a stable model instead of preview
_raw_model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip()
model_name = _normalize_model_name(_raw_model)

if not os.environ.get("GEMINI_API_KEY"):
    raise ValueError("GEMINI_API_KEY is not set. Please set it in your environment or .env file.")

if validate_model_compatibility(model_name):
    # Fixed LLM configuration - removed explicit provider parameter
    gemini_llm = LLM(
        model=model_name,
        api_key=os.environ.get("GEMINI_API_KEY"),
        temperature=0.5,
        # LiteLLM retry configuration to mitigate transient 5xx (e.g., Vertex 503 overloaded)
        num_retries=int(os.environ.get("LITELLM_NUM_RETRIES", "4")),
        request_timeout=int(os.environ.get("LITELLM_REQUEST_TIMEOUT", "120"))
    )
else:
    raise ValueError(f"Model {model_name} is not compatible with CrewAI requirements. Set GEMINI_MODEL to one of: {', '.join(get_available_model_names())}")


# Agents
reviewer_agent = Agent(
    role='Expert AI Code Reviewer',
    goal='Perform a thorough, line-by-line code review',
    backstory="You are a Senior Software Engineer with a meticulous eye for detail.",
    llm=gemini_llm,
    tools=[github_tool],
    verbose=True,
    allow_delegation=False
)


tester_agent = Agent(
    role='Expert Python QA Engineer',
    goal='Generate a comprehensive suite of pytest unit tests for the given code.',
    backstory=(
        "You are a Quality Assurance Engineer who specializes in the pytest framework. You have a knack for identifying "
        "edge cases and ensuring complete code coverage. You follow a strict 'generate and verify' protocol to ensure "
        "the tests you produce are valid and executable."
    ),
    llm=gemini_llm,  # Pass the LLM object
    tools=[github_tool],
    verbose=True,
    allow_delegation=False
)


reporter_agent = Agent(
    role='AI Tech Lead Reporter',
    goal='Synthesize the code review and test results into a single, well-formatted Markdown report and post it to the GitHub pull request.',
    backstory=(
        "You are the communication hub for the AI Tech Lead team. You excel at taking complex technical data "
        "and presenting it in a clear, concise, and actionable format for human developers."
    ),
    llm=gemini_llm,  # Pass the LLM object
    tools=[github_tool],
    verbose=True,
    allow_delegation=False
)
