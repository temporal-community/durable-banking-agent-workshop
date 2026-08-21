from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.contrib.openai_agents.workflow import activity_as_tool

with workflow.unsafe.imports_passed_through():
    # Pre-imported so the workflow sandbox snapshots pydantic before the first Agent(...).
    import annotated_types  # noqa: F401
    import pydantic_core  # noqa: F401
    import pydantic_core.core_schema  # noqa: F401

    from agents import Agent, Runner

    from tool_activities import get_account_balance

INSTRUCTIONS = """
You are a concise bank assistant. Use the provided tools to answer the user's question.
Always use a tool when it would make the answer more accurate.
"""

TOOL_TIMEOUT = timedelta(seconds=30)


@workflow.defn
class BankAssistantWorkflow:
    @workflow.run
    async def run(self, question: str) -> str:
        agent = Agent(
            name="Bank Assistant",
            instructions=INSTRUCTIONS,
            model="gpt-4o",
            tools=[
                activity_as_tool(get_account_balance, start_to_close_timeout=TOOL_TIMEOUT),
            ],
        )
        result = await Runner.run(agent, input=question)
        return result.final_output
