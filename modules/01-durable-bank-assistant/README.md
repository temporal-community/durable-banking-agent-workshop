# Module 1: A Durable Bank Assistant

A plain bank-assistant `Agent` from the OpenAI Agents SDK, running inside a Temporal workflow. No
tools yet, one LLM call, and already durable.

## Architecture

- `agent_workflow.py` builds an `Agent` and calls `Runner.run(...)`. That is the whole workflow.
- `OpenAIAgentsPlugin` (registered on both the client and the worker) turns the SDK's model calls
  into Temporal activities. You never write `execute_activity` yourself.
- `ModelActivityParameters` sets the timeout for each of those model activities.

The pydantic pre-imports at the top of `agent_workflow.py` are there so the workflow sandbox
snapshots pydantic before the first `Agent(...)` is constructed. Without them the sandbox warns
about modules imported after the workflow loaded.

## What to notice

Open the Temporal Web UI and look at the event history. `invoke_model_activity` is its own
activity, with its own retry policy, scheduled and completed like any other. The workflow code has
no retry logic in it. That is what the plugin bought.

The assistant has no tools, so ask it anything account-specific and it can't actually look anything
up. Module 2 gives it a real tool.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- [Temporal CLI](https://docs.temporal.io/cli)
- `OPENAI_API_KEY` in your environment

## Run it

```bash
temporal server start-dev          # once, in its own terminal
cd exercise && uv sync
```

Fill in the `TODO` in `agent_workflow.py`, then:

```bash
uv run python -m worker            # terminal 2, stays running
uv run python -m start_workflow "What is my account balance?"   # terminal 3
```

Stuck? Compare with `solution/`.

Task queue: `durable-bank-assistant-tq`. Traces also land at https://platform.openai.com/traces.
