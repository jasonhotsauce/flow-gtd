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


def coach_task(task_title: str) -> Optional[str]:
    """
    For a vague task (e.g. "Fix Bug"), return an AI-suggested actionable phrase.
    Returns None if LLM unavailable.
    """
    prompt = f"{COACH_SYSTEM}\n\nTask: {task_title.strip()}\nSuggested next action:"
    return complete(prompt, sanitize=True)


def are_duplicate(title_a: str, title_b: str) -> Optional[bool]:
    """Return True if duplicate, False if distinct, None if LLM unavailable."""
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
