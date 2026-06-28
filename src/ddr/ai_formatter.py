"""Format free-text work description into clean task list via LLM."""

from .llm_router import RouterResult, complete


def _build_prompt(description: str, count: int) -> str:
    return f"""You are a technical report formatter for a software development daily report.

Convert the following work description into exactly {count} concise task items.

Rules:
- Each task: one line, max 80 chars
- Format: "<Module/Feature> — <what was done>"
- Use past tense action verbs (Fixed, Added, Built, Refactored, Implemented, etc.)
- Be specific and technical — no vague phrases like "worked on" or "did stuff"
- Return ONLY the {count} tasks, one per line, no numbering, no bullets, no extra text

Work description:
{description}"""


def format_tasks(description: str, count: int = 5) -> list[str]:
    result: RouterResult = complete(
        _build_prompt(description, count),
        max_tokens=512,
        temperature=0.3,
    )
    tasks = [line.strip() for line in result.text.splitlines() if line.strip()]
    if len(tasks) < count:
        tasks.extend(["(no task)"] * (count - len(tasks)))
    return tasks[:count]
