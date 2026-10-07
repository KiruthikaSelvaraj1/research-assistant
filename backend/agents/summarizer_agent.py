"""Per-paper analyst producing a summary and structured findings in one pass."""
from crewai import Agent, LLM


def create_summarizer_agent(llm: LLM) -> Agent:
    return Agent(
        role="Research Paper Analyst",
        goal=(
            "Produce an accurate concise summary and structured evidence findings for an "
            "academic paper in a single response. Preserve exact reported results and distinguish "
            "author evidence from interpretation."
        ),
        backstory=(
            "You are a careful evidence reviewer. You capture the research question, study "
            "design, population or dataset, main results with exact numbers, and limitations. "
            "You never invent details when the paper does not report them, and produce valid "
            "machine-readable JSON so the findings can be compared across papers."
        ),
        llm=llm,
        verbose=False,
        allow_delegation=False,
        max_iter=1,
    )
