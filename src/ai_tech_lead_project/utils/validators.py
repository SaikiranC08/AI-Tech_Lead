"""
Output validation utilities for the AI Tech Lead PR reviewer.
Hard-fail validation: raises ValueError if agent output references
files NOT present in the PR diff.
"""
import re
from typing import Set


def extract_filenames_from_diff(diff_text: str) -> set:
    """
    Extract filenames from FILES_IN_THIS_PR section.
    """
    lines = diff_text.splitlines()
    filenames = set()
    capture = False
    for line in lines:
        if line.strip() == "FILES_IN_THIS_PR:":
            capture = True
            continue
        if capture:
            stripped = line.strip()
            if not stripped.startswith("-"):
                break
            filenames.add(stripped.lstrip("- ").strip())
    return filenames


def validate_output_filenames(output_text: str, valid_filenames: set):
    """
    Ensure agent output references only allowed filenames.
    Raises ValueError if any invalid file references are detected.
    """
    # Match anything that looks like a filename with extension
    referenced = set(re.findall(r'\b[\w\-./]+\.(?:py|js|ts|java|go|rs|rb|c|cpp|h|hpp|cs|swift|kt|sh|yaml|yml|json|xml|html|css|md|txt|toml|cfg|ini|sql)\b', output_text, re.IGNORECASE))

    # Normalize: strip leading path prefixes like a/ or b/
    def normalize(f: str) -> str:
        f = f.replace("\\", "/")
        if f.startswith(("a/", "b/")):
            f = f[2:]
        return f

    # Build the set of valid names (full paths + basenames)
    valid_normalized = {normalize(f) for f in valid_filenames}
    valid_basenames = set()
    for f in valid_normalized:
        parts = f.rsplit("/", 1)
        valid_basenames.add(parts[-1])

    # Check every referenced file
    invalid = set()
    for raw_file in referenced:
        norm = normalize(raw_file)
        basename = norm.rsplit("/", 1)[-1]
        # Skip common test/example filenames that are part of the prompt template itself
        if basename in ("calculator.py", "user_count.py") and basename not in valid_basenames:
            # These appear in prompt examples, not actual references
            continue
        if norm not in valid_normalized and basename not in valid_basenames:
            invalid.add(raw_file)

    if invalid:
        raise ValueError(
            f"❌ VALIDATION FAILED: Output references files NOT in the PR diff: {invalid}. "
            f"Valid files were: {valid_filenames}. Comment will NOT be posted."
        )
