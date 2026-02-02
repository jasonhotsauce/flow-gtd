"""AI Socratic logic: challenge vague tasks into actionable verbs; clustering."""

from typing import Optional

from flow.utils.llm import complete

COACH_SYSTEM = """You are a GTD coach. Given a vague task title, suggest one concrete \
next action (verb-first, specific).
Reply with only the suggested action phrase, no explanation. Keep it under 15 words."""

DEDUP_SYSTEM = """Are these two tasks the same or about the same thing? \
Reply with exactly one word: duplicate or distinct."""

CLUSTER_SYSTEM = """Given a list of task titles, suggest 1-3 project names that group \
related tasks. For each project, list the 0-based indices of tasks that belong to it. \
Reply in this exact format, one line per project:
ProjectName: 0, 2, 5
Use only the indices given. If no grouping, reply: none"""

DURATION_SYSTEM = """Estimate how long this task will take to complete.
Reply with only a single number from this list: 5, 15, 30, 60, 120 (minutes).
Consider:
- 5 min: trivial tasks (reply to email, quick lookup)
- 15 min: small tasks (review short document, quick fix)
- 30 min: medium tasks (write brief, review PR)
- 60 min: substantial tasks (design doc section, complex debugging)
- 120 min: deep work (architecture design, major feature implementation)
Reply with ONLY the number, nothing else."""


def coach_task(task_title: str) -> Optional[str]:
    """
    For a vague task (e.g. "Fix Bug"), return an AI-suggested actionable phrase.

    Args:
        task_title: The task title to coach.

    Returns:
        Suggested actionable phrase, or None if LLM unavailable or empty input.
    """
    if not task_title or not task_title.strip():
        return None

    prompt = f"{COACH_SYSTEM}\n\nTask: {task_title.strip()}\nSuggested next action:"
    return complete(prompt, sanitize=True)


def are_duplicate(title_a: str, title_b: str) -> Optional[bool]:
    """Return True if duplicate, False if distinct, None if LLM unavailable.

    Args:
        title_a: First task title.
        title_b: Second task title.

    Returns:
        True if duplicate, False if distinct, None if LLM unavailable or empty input.
    """
    if not title_a or not title_a.strip() or not title_b or not title_b.strip():
        return None

    out = complete(
        f"{DEDUP_SYSTEM}\n\nA: {title_a}\nB: {title_b}\nAnswer:",
        sanitize=True,
    )
    if not out:
        return None
    return "duplicate" in (out.strip().lower())


def suggest_clusters(titles: list[str]) -> list[tuple[str, list[int]]]:
    """
    Return suggested (project_name, list of indices) for clustering.
    Empty list if LLM unavailable or no grouping.
    """
    if not titles:
        return []
    numbered = "\n".join(f"{i}: {t}" for i, t in enumerate(titles))
    prompt = f"{CLUSTER_SYSTEM}\n\nTasks:\n{numbered}\n"
    out = complete(prompt, sanitize=True)
    if not out or "none" in out.strip().lower():
        return []
    result: list[tuple[str, list[int]]] = []
    for line in out.strip().splitlines():
        line = line.strip()
        if ":" not in line:
            continue
        name, rest = line.split(":", 1)
        name = name.strip()
        indices = []
        for part in rest.split(","):
            part = part.strip()
            if part.isdigit():
                idx = int(part)
                if 0 <= idx < len(titles):
                    indices.append(idx)
        if name and indices:
            result.append((name, indices))
    return result


# Valid duration values for Focus Mode
VALID_DURATIONS = [5, 15, 30, 60, 120]


def estimate_duration(task_title: str) -> Optional[int]:
    """
    Estimate task duration in minutes using LLM.

    Args:
        task_title: The task title to estimate duration for.

    Returns:
        Estimated duration in minutes (5, 15, 30, 60, or 120),
        or None if LLM unavailable, invalid response, or empty input.
    """
    # Validate input
    if not task_title or not task_title.strip():
        return None

    prompt = f"{DURATION_SYSTEM}\n\nTask: {task_title.strip()}\nEstimate:"
    out = complete(prompt, sanitize=True)

    if not out:
        return None

    # Extract number from response
    out = out.strip()
    try:
        # Try to parse the number directly
        duration = int(out)
        # Validate it's one of the expected values
        if duration in VALID_DURATIONS:
            return duration
        # Round to nearest valid duration
        return min(VALID_DURATIONS, key=lambda x: abs(x - duration))
    except ValueError:
        # Try to extract a number from the text
        import re

        numbers = re.findall(r"\d+", out)
        if numbers:
            duration = int(numbers[0])
            if duration in VALID_DURATIONS:
                return duration
            return min(VALID_DURATIONS, key=lambda x: abs(x - duration))

    return None


def estimate_duration_heuristic(task_title: str) -> int:
    """
    Fast heuristic duration estimation (no LLM call).

    Useful as fallback when LLM is unavailable.

    Args:
        task_title: The task title to estimate.

    Returns:
        Estimated duration in minutes (always returns a value).
        Returns 30 (medium) for empty or invalid input.
    """
    if not task_title or not task_title.strip():
        return 30  # Default to medium for empty input

    title_lower = task_title.lower()

    # Quick tasks (5 min)
    quick_keywords = [
        "reply",
        "respond",
        "check",
        "confirm",
        "send",
        "forward",
        "quick",
    ]
    if any(kw in title_lower for kw in quick_keywords):
        return 5

    # Short tasks (15 min)
    short_keywords = ["review", "read", "update", "fix", "small", "minor", "tweak"]
    if any(kw in title_lower for kw in short_keywords):
        return 15

    # Medium tasks (30 min)
    medium_keywords = ["write", "draft", "prepare", "create", "setup", "configure"]
    if any(kw in title_lower for kw in medium_keywords):
        return 30

    # Long tasks (60 min)
    long_keywords = ["design", "plan", "analyze", "implement", "develop", "build"]
    if any(kw in title_lower for kw in long_keywords):
        return 60

    # Deep work (120 min)
    deep_keywords = ["architect", "refactor", "migrate", "research", "complex"]
    if any(kw in title_lower for kw in deep_keywords):
        return 120

    # Default to medium
    return 30
