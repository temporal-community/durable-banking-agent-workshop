---
slug: durable-bank-assistant-java
id: 9kblqzgsmm3v
type: challenge
title: 'Module 1: A Durable Bank Assistant (Java)'
teaser: An OpenAI-backed activity inside a Temporal workflow. Durable before it has
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

    The workflow calls the OpenAI SDK through a Temporal activity, not
    directly. You get retries, timeouts and a full history of every step.

    In exchange, the call runs under a worker instead of in your terminal.
tabs:
- id: xzcpyttgqn5n
  title: Worker
  type: terminal
  hostname: workshop-java
  workdir: /root/workshop/modules/01-durable-bank-assistant/exercise
- id: fhxb9dbou9my
  title: Starter
  type: terminal
  hostname: workshop-java
  workdir: /root/workshop/modules/01-durable-bank-assistant/exercise
- id: tgxfm1myf56d
  title: Temporal UI
  type: service
  hostname: workshop-java
  path: /
  port: 8233
- id: 10dl6mloiyui
  title: Network Control Panel
  type: service
  hostname: workshop-java
  path: /
  port: 5000
- id: cnuendoqqjmy
  title: Editor
  type: code
  hostname: workshop-java
  path: /root/workshop/modules/01-durable-bank-assistant/exercise
- id: cqzq2zcanwj3
  title: Solution
  type: code
  hostname: workshop-java
  path: /root/workshop/modules/01-durable-bank-assistant/solution
difficulty: basic
timelimit: 1800
enhanced_loading: null
---

# A Durable Bank Assistant

One activity wrapping an OpenAI call, one workflow that awaits it, and an event history that
already knows how to retry it.

> [!NOTE]
> **Your tabs.**
> - [button label="Worker" background="#444CE7"](tab-0) runs the worker. It stays blocked while it polls.
> - [button label="Starter" background="#444CE7"](tab-1) is where you launch workflows.
> - [button label="Temporal UI" background="#444CE7"](tab-2) is the event history.
> - [button label="Network Control Panel" background="#444CE7"](tab-3) turns external services off.
> - [button label="Editor" background="#444CE7"](tab-4) is your working copy.
> - [button label="Solution" background="#444CE7"](tab-5) is the finished code.

## What Changed

Nothing yet. This is the starting point. Files in `modules/01-durable-bank-assistant/exercise`:

- `BankAssistantActivitiesImpl.java` implements `answerQuestion(question)` as an `@ActivityMethod`:
  it calls the OpenAI Java SDK directly and classifies failures so only genuinely transient ones
  (timeouts, 429s, 5xxs) are left for Temporal's default retry policy to handle.
- `BankAssistantWorkflowImpl.java` gets an activity stub and should just call
  `activities.answerQuestion(question)`. That is the whole workflow.
- `Worker.java` registers the workflow and activity implementations and polls task queue
  `durable-bank-assistant-tq-java`.
- `StartWorkflow.java` connects and starts one execution.

## Write the Agent

Open `BankAssistantWorkflowImpl.java` in the [button label="Editor" background="#444CE7"](tab-4)
tab and do the `TODO`.

## Start the Worker

Click the [button label="Worker" background="#444CE7"](tab-0) terminal.

```bash,run
mvn -q exec:java -Dexec.mainClass=bankworkshop.module1.Worker
```

> First run resolves Maven dependencies and can take noticeably longer than a warm run; later
> commands in this workshop reuse the same local repo and are fast.

It prints a line and does not return you to a prompt. That blocked terminal is the worker polling.
Leave it and move on.

## Run It

Click the [button label="Starter" background="#444CE7"](tab-1) terminal.

```bash,run
mvn -q exec:java -Dexec.mainClass=bankworkshop.module1.StartWorkflow -Dexec.args="What is my account balance?"
```

## Watch the Event History

Click the [button label="Temporal UI" background="#444CE7"](tab-2) tab and open your workflow.

`AnswerQuestion` is scheduled, started and completed, like any other activity, with the retry
policy you get by not configuring one at all.

## Break It

Click the [button label="Network Control Panel" background="#444CE7"](tab-3) tab and toggle
**OpenAI** off. Then run another workflow from the
[button label="Starter" background="#444CE7"](tab-1) terminal.

In the [button label="Temporal UI" background="#444CE7"](tab-2) tab the workflow stays **Running**
and the activity shows **Retrying**, attempt count climbing.

> Your workflow is one call to `activities.answerQuestion(...)`. Who is retrying it?

<details>
<summary>Answer</summary>

Temporal. The activity stub carries a retry policy, and `answerQuestion` is simply still awaiting
a call that has not returned. `BankAssistantActivitiesImpl` classifies the failure as retryable
(a connection error, or a 429/5xx from OpenAI), so it never turns into an `ApplicationFailure` in
the first place.
</details>

Toggle **OpenAI** back on. The next attempt succeeds and the same execution finishes.

## Ask It Something It Can't Know

```bash,run
mvn -q exec:java -Dexec.mainClass=bankworkshop.module1.StartWorkflow -Dexec.args="What is the balance of account A?"
```

It either guesses or admits it has no way to look that up. It has no tools yet.

That is module 2.

## Summary

| | Plain script | Inside a Temporal workflow |
|---|---|---|
| Retries on a failed LLM call | You write them | Activity retry policy |
| Where the conversation lives | Process memory | Event history |
| Survives the process dying | No | Yes |
| Extra code you wrote for that | n/a | Failure classification only |
