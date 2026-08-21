---
slug: durable-bank-tools
id: qmgtq1hq57vf
type: challenge
title: 'Module 2: Durable Bank Tools'
teaser: One real tool, wired in as an activity. Watch the agentic loop show up in
  event history.
notes:
- type: text
  contents: |-
    # A tool is just another activity

    Module 1's assistant could talk, but not look anything up. A tool call is
    one more network hop, and network hops are exactly what activities are
    for.
- type: text
  contents: |-
    # Call, act, respond

    Ask about a balance and the event history grows a third step: a model
    call, a tool call, then a model call that turns the number into a
    sentence. Each step retries on its own.
tabs:
- id: vwpxknyokgzj
  title: Worker
  type: terminal
  hostname: workshop
  workdir: /root/workshop/modules/02-durable-bank-tools/exercise
- id: 4wwhy4yudpup
  title: Starter
  type: terminal
  hostname: workshop
  workdir: /root/workshop/modules/02-durable-bank-tools/exercise
- id: pbywloxkftmi
  title: Temporal UI
  type: service
  hostname: workshop
  path: /
  port: 8233
- id: ywljjy0ylme9
  title: Network Control Panel
  type: service
  hostname: workshop
  path: /
  port: 5000
- id: jxsjm01qnpti
  title: Editor
  type: code
  hostname: workshop
  path: /root/workshop/modules/02-durable-bank-tools/exercise
- id: p9yixrmuws5a
  title: Solution
  type: code
  hostname: workshop
  path: /root/workshop/modules/02-durable-bank-tools/solution
difficulty: basic
timelimit: 1800
enhanced_loading: null
---

# Durable Bank Tools

Module 1's assistant, now with a real tool: `get_account_balance`, wired in as a Temporal activity.

> [!NOTE]
> **Your tabs.**
> - [button label="Worker" background="#444CE7"](tab-0) runs the worker.
> - [button label="Starter" background="#444CE7"](tab-1) launches workflows.
> - [button label="Temporal UI" background="#444CE7"](tab-2) is the event history.
> - [button label="Network Control Panel" background="#444CE7"](tab-3) turns external services off.
> - [button label="Editor" background="#444CE7"](tab-4) is your working copy.
> - [button label="Solution" background="#444CE7"](tab-5) is the finished code.

## What Changed

- `tool_activities.py` adds `get_account_balance(account_id)`, a plain `@activity.defn` returning a
  canned balance for account `A` or `B`.
- `agent_workflow.py` passes it to the `Agent` via `activity_as_tool(...)` instead of leaving the
  agent tool-less.

## Write the Agent

Open `agent_workflow.py` in the [button label="Editor" background="#444CE7"](tab-4) tab and do the
`TODO`. It looks the same as module 1, plus one `tools=[...]` argument.

## Start the Worker

Click the [button label="Worker" background="#444CE7"](tab-0) terminal.

```bash,run
uv run python -m worker
```

## Ask It Something It Can Now Answer

Click the [button label="Starter" background="#444CE7"](tab-1) terminal.

```bash,run
uv run python -m start_workflow "What is the balance of account A?"
```

## Watch the Event History

Click the [button label="Temporal UI" background="#444CE7"](tab-2) tab and open your workflow.

Three steps: a model activity, then `get_account_balance`, then another model activity that turns
the number into a sentence. That call-act-respond shape is the agentic loop, and every step in it
is independently retryable.

## Break It

Click the [button label="Network Control Panel" background="#444CE7"](tab-3) tab and toggle
**OpenAI** off mid-run. The model activity retries; the tool activity, once it gets there, is
unaffected by an OpenAI outage, since it talks to nothing external at all.

Toggle **OpenAI** back on and let the run finish.

## Summary

| | Module 1 | Module 2 |
|---|---|---|
| Tools | None | `get_account_balance` |
| Event history steps for one question | 1 model activity | model, tool, model |
| New retry surface | none | the tool activity, independently |
