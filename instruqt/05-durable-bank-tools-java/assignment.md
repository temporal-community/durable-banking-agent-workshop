---
slug: durable-bank-tools-java
id: 00kg4lammmhv
type: challenge
title: 'Module 2: Durable Bank Tools (Java)'
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
- id: cwx05sl0qjei
  title: Worker
  type: terminal
  hostname: workshop-java
  workdir: /root/workshop/modules/02-durable-bank-tools/exercise
- id: hsyyjg1d76oe
  title: Starter
  type: terminal
  hostname: workshop-java
  workdir: /root/workshop/modules/02-durable-bank-tools/exercise
- id: vo2b28h1lcgp
  title: Temporal UI
  type: service
  hostname: workshop-java
  path: /
  port: 8233
- id: b6sbijobolj4
  title: Network Control Panel
  type: service
  hostname: workshop-java
  path: /
  port: 5000
- id: nvpcorxdvq8y
  title: Editor
  type: code
  hostname: workshop-java
  path: /root/workshop/modules/02-durable-bank-tools/exercise
- id: oojuejk8e0vl
  title: Solution
  type: code
  hostname: workshop-java
  path: /root/workshop/modules/02-durable-bank-tools/solution
difficulty: basic
timelimit: 1800
enhanced_loading: null
---

# Durable Bank Tools

Module 1's assistant, now with a real tool: `getAccountBalance`, wired in as a Temporal activity.

> [!NOTE]
> **Your tabs.**
> - [button label="Worker" background="#444CE7"](tab-0) runs the worker.
> - [button label="Starter" background="#444CE7"](tab-1) launches workflows.
> - [button label="Temporal UI" background="#444CE7"](tab-2) is the event history.
> - [button label="Network Control Panel" background="#444CE7"](tab-3) turns external services off.
> - [button label="Editor" background="#444CE7"](tab-4) is your working copy.
> - [button label="Solution" background="#444CE7"](tab-5) is the finished code.

## What Changed

- `BankToolsActivitiesImpl.java` adds `decideNextStep(question)` (asks the model, offering
  `getAccountBalance` as a tool via `addTool(GetAccountBalanceArgs.class)`), a plain
  `getAccountBalance(accountId)` returning a canned balance for account `A` or `B`, and
  `composeFinalAnswer(...)` that turns the number into a sentence.
- `BankAssistantWorkflowImpl.java` should call `decideNextStep`, and if it asks for an account,
  call `getAccountBalance` then `composeFinalAnswer` - instead of leaving the assistant tool-less.

## Write the Agent

Open `BankAssistantWorkflowImpl.java` in the [button label="Editor" background="#444CE7"](tab-4)
tab and do the `TODO`. It looks the same as module 1, plus the tool-call branch.

## Start the Worker

Click the [button label="Worker" background="#444CE7"](tab-0) terminal.

```bash,run
mvn -q compile exec:java -Dexec.mainClass=bankworkshop.module2.Worker
```

> First run resolves Maven dependencies and can take noticeably longer than a warm run.

## Ask It Something It Can Now Answer

Click the [button label="Starter" background="#444CE7"](tab-1) terminal.

```bash,run
mvn -q compile exec:java -Dexec.mainClass=bankworkshop.module2.StartWorkflow -Dexec.args="What is the balance of account A?"
```

## Watch the Event History

Click the [button label="Temporal UI" background="#444CE7"](tab-2) tab and open your workflow.

Three steps: a `DecideNextStep` activity, then `GetAccountBalance`, then `ComposeFinalAnswer`.
That call-act-respond shape is the agentic loop, and every step in it is independently retryable.

## Break It

Click the [button label="Network Control Panel" background="#444CE7"](tab-3) tab and toggle
**OpenAI** off mid-run. The model activities retry; `GetAccountBalance`, once it gets there, is
unaffected by an OpenAI outage, since it talks to nothing external at all.

Toggle **OpenAI** back on and let the run finish.

## Summary

| | Module 1 | Module 2 |
|---|---|---|
| Tools | None | `getAccountBalance` |
| Event history steps for one question | 1 model activity | model, tool, model |
| New retry surface | none | the tool activity, independently |
