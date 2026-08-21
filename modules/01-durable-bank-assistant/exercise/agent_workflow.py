from __future__ import annotations

from temporalio import workflow
from temporalio.exceptions import ApplicationError

with workflow.unsafe.imports_passed_through():
    # Pre-imported so the workflow sandbox snapshots pydantic before the first Agent(...).
    import annotated_types  # noqa: F401
    import pydantic_core  # noqa: F401
    import pydantic_core.core_schema  # noqa: F401

    from agents import Agent, Runner

INSTRUCTIONS = "You are a concise bank assistant."


@workflow.defn
class BankAssistantWorkflow:
    @workflow.run
    async def run(self, question: str) -> str:
        # TODO: Uncomment the block below.
        # agent = Agent(
        #     name="Bank Assistant",
        #     instructions=INSTRUCTIONS,
        #     model="gpt-4o",
        # )
        # result = await Runner.run(agent, input=question)
        # return result.final_output
        raise ApplicationError("TODO not implemented", non_retryable=True)
