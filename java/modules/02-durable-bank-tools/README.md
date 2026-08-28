# Module 2 (Java): Durable Bank Tools

Module 1's assistant, now with a real tool: `getAccountBalance`, wired in as a Temporal activity.

## What's different from module 1

- `BankToolsActivitiesImpl.getAccountBalance` returns a canned balance for account `A` or `B`.
- The model call itself becomes two activities instead of one: `decideNextStep` (does the model
  need the tool?) and, if it does, `composeFinalAnswer` (turn the balance into a reply). There's no
  Java equivalent of Python's `activity_as_tool`, so the loop between them is written by hand in
  `BankAssistantWorkflowImpl` instead of hidden inside a plugin.

## Architecture

- `BankToolsActivities.decideNextStep(question)`: offers the model the `getAccountBalance` tool
  (via `@JsonClassDescription`/`@JsonPropertyDescription` on a small args class - that's what the
  model sees, so it's written like documentation aimed at an LLM). Returns either a final answer or
  a requested account ID.
- `BankToolsActivities.getAccountBalance(accountId)`: the tool itself, a plain activity.
- `BankToolsActivities.composeFinalAnswer(...)`: a second model call, given the looked-up balance.
- `BankAssistantWorkflowImpl`: three sequential activity calls, each independently retryable.

## What to notice

Ask about a specific account's balance and watch the Temporal Web UI event history: a
`decideNextStep` activity, then a `getAccountBalance` activity, then a `composeFinalAnswer`
activity. Every step in that chain is now retryable on its own - a flaky call to OpenAI on step one
doesn't lose the fact that the workflow is mid-conversation.

## Prerequisites

- Java 17+
- [Maven](https://maven.apache.org/)
- [Temporal CLI](https://docs.temporal.io/cli)
- `OPENAI_API_KEY` in your environment

## Run it

```bash
temporal server start-dev          # once, in its own terminal
cd exercise
```

Fill in the `TODO` in `BankAssistantWorkflowImpl.java`, then:

```bash
mvn -q exec:java -Dexec.mainClass=bankworkshop.module2.Worker           # terminal 2, stays running
mvn -q exec:java -Dexec.mainClass=bankworkshop.module2.StartWorkflow \
    -Dexec.args="What is the balance of account A?"                    # terminal 3
```

Stuck? Compare with `solution/`.

Task queue: `durable-bank-tools-tq-java`.
