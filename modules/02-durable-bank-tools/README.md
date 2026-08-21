# Module 2: Durable Bank Tools

Module 1's assistant, now with a real tool: `get_account_balance`, wired in as a Temporal activity.

## What's different from module 1

- `tool_activities.py` adds `get_account_balance`, a plain `@activity.defn` returning a canned
  balance for account `A` or `B`.
- `agent_workflow.py` passes it to the `Agent` via `activity_as_tool(...)` instead of leaving the
  agent tool-less.
- `worker.py` registers the new activity alongside the workflow.

## Architecture

- `tool_activities.get_account_balance(account_id)`: the tool. Its docstring is what the model
  sees, so it reads like documentation aimed at an LLM: one line plus an `Args:` block.
- `activity_as_tool(get_account_balance, start_to_close_timeout=...)`: turns that activity into a
  tool the `Agent` can call, with its own Temporal retry policy and timeout.
- Everything else is unchanged from module 1.

## What to notice

Ask about a specific account's balance and watch the Temporal Web UI event history: a model
activity, then a `get_account_balance` activity, then another model activity that turns the tool
result into a sentence. That three-step shape (call, act, respond) is the agentic loop, and every
step in it is now retryable on its own.

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
uv run python -m start_workflow "What is the balance of account A?"   # terminal 3
```

Stuck? Compare with `solution/`.

Task queue: `durable-bank-tools-tq`.
