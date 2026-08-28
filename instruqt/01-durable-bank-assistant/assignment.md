---
slug: durable-bank-assistant
id: xylgyugxvrgl
type: challenge
title: 'Module 1: A Durable Bank Assistant (Python)'
teaser: An OpenAI Agents SDK agent inside a Temporal workflow. Durable before it has
  a single tool.
notes:
- type: text
  contents: |-
    # What if the retry policy came for free?

    A bank assistant is a sequence of network calls, and every one of them can
    fail. The usual fix is a retry wrapper, a backoff, and somewhere to keep
    the conversation while you wait.

    You are about to write none of that.
- type: text
  contents: |-
    # The trade

    The agent runs inside a Temporal workflow, so its LLM calls become
    activities. You get retries, timeouts and a full history of every step.

    In exchange, the loop runs under a worker instead of in your terminal.
tabs:
- id: s1vqjp8uopga
  title: Worker
  type: terminal
  hostname: workshop
  workdir: /root/workshop/modules/01-durable-bank-assistant/exercise
- id: urcthteufc3r
  title: Starter
  type: terminal
  hostname: workshop
  workdir: /root/workshop/modules/01-durable-bank-assistant/exercise
- id: aby1i6vssmt4
  title: Temporal UI
  type: service
  hostname: workshop
  path: /
  port: 8233
- id: sjelycyta92h
  title: Network Control Panel
  type: service
  hostname: workshop
  path: /
  port: 5000
- id: pmynwxuqkiqv
  title: Editor
  type: code
  hostname: workshop
  path: /root/workshop/modules/01-durable-bank-assistant/exercise
- id: msppktnu6w90
  title: Solution
  type: code
  hostname: workshop
  path: /root/workshop/modules/01-durable-bank-assistant/solution
difficulty: basic
timelimit: 1800
enhanced_loading: null
---

# A Durable Bank Assistant

Twelve lines of workflow code, one LLM call, and an event history that already knows how to retry it.

> [!NOTE]
> **Your tabs.**
> - [button label="Worker" background="#444CE7"](tab-0) runs the worker. It stays blocked while it polls.
> - [button label="Starter" background="#444CE7"](tab-1) is where you launch workflows.
> - [button label="Temporal UI" background="#444CE7"](tab-2) is the event history.
> - [button label="Network Control Panel" background="#444CE7"](tab-3) turns external services off.
> - [button label="Editor" background="#444CE7"](tab-4) is your working copy.
> - [button label="Solution" background="#444CE7"](tab-5) is the finished code.

## What Changed

Nothing yet. This is the starting point. Three files in `modules/01-durable-bank-assistant/exercise`:

- `agent_workflow.py` builds an `Agent` and awaits `Runner.run(...)`. That is the whole workflow.
- `worker.py` registers `OpenAIAgentsPlugin`. The plugin turns the SDK's model calls into activities.
- `start_workflow.py` connects with the same plugin and starts one execution.

## Write the Agent

Open `agent_workflow.py` in the [button label="Editor" background="#444CE7"](tab-4) tab and do the `TODO`.

## Start the Worker

Click the [button label="Worker" background="#444CE7"](tab-0) terminal.

```bash,run
uv run python -m worker
```

It prints nothing and does not return you to a prompt. That blocked terminal is the worker polling.
Leave it and move on.

## Run It

Click the [button label="Starter" background="#444CE7"](tab-1) terminal.

```bash,run
uv run python -m start_workflow "What is my account balance?"
```

## Watch the Event History

Click the [button label="Temporal UI" background="#444CE7"](tab-2) tab and open your workflow.

`invoke_model_activity` is scheduled, started and completed, like any other activity. Your workflow
never called `execute_activity`. The plugin did.

## Break It

Click the [button label="Network Control Panel" background="#444CE7"](tab-3) tab and toggle
**OpenAI** off. Then run another workflow from the
[button label="Starter" background="#444CE7"](tab-1) terminal.

In the [button label="Temporal UI" background="#444CE7"](tab-2) tab the workflow stays **Running**
and the model activity shows **Retrying**, attempt count climbing.

> Your workflow is one `await Runner.run(...)`. Who is retrying it?

<details>
<summary>Answer</summary>

Temporal, and the SDK has no idea anything went wrong. The plugin runs each model call as an
activity, and every activity carries a retry policy. `Runner.run` is simply still awaiting a call
that has not returned.
</details>

Toggle **OpenAI** back on. The next attempt succeeds and the same execution finishes.

## Ask It Something It Can't Know

```bash,run
uv run python -m start_workflow "What is the balance of account A?"
```

It either guesses or admits it has no way to look that up. It has no tools yet.

That is module 2.

## Summary

| | Plain script | Inside a Temporal workflow |
|---|---|---|
| Retries on a failed LLM call | You write them | Activity retry policy |
| Where the conversation lives | Process memory | Event history |
| Survives the process dying | No | Yes |
| Extra code you wrote for that | n/a | None |
