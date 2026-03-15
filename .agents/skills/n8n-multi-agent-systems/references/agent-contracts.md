# Agent Contracts And Prompting

Use this file when defining agent boundaries, prompts, and handoff payloads.

## Contract Template

Write a compact contract for every agent:

```markdown
Agent: [name]
Responsibility: [single job]
Use when: [trigger condition]
Inputs: [fields or schema]
Outputs: [structured payload]
Tools: [only required tools]
Out of scope: [what this agent must not do]
Stop rule: [finish, retry, escalate, or fail]
Fallback: [what happens on timeout or low confidence]
```

Keep inputs and outputs structured whenever possible. Prefer JSON-shaped payloads over free-form prose.

## Orchestrator Rules

The orchestrator should:

- Maintain the user goal and workflow state
- Decide whether delegation is needed
- Choose the smallest matching specialist set
- Integrate specialist outputs into the final answer

The orchestrator should not:

- Re-implement domain logic that belongs in specialists
- Hold every credential by default
- Keep delegating without a stop condition

## Specialist Rules

Each specialist should:

- Own one domain or step
- Receive only the context needed for that step
- Return a predictable schema
- Escalate when it is out of scope or uncertain

Each specialist should not:

- Act like a second orchestrator
- Reach into unrelated systems
- Rewrite the upstream plan unless asked

## Prompt Skeleton: Orchestrator

Use a prompt shape like this:

```text
You are the coordinator for this workflow.

Goal:
- Interpret the request
- Decide whether to answer directly or delegate
- Call only the specialist workflows whose descriptions match the task
- Combine results into the final response

Available specialists:
- [name]: [when to use]
- [name]: [when to use]

Rules:
- Do not perform specialist work yourself when a specialist exists
- Keep delegation steps minimal
- Respect hop limits and escalation rules
- If no specialist fits, return an out-of-scope or clarification response
```

## Prompt Skeleton: Specialist

Use a prompt shape like this:

```text
You are the [specialist name].

You own:
- [single responsibility]

You receive:
- [input fields]

You must return:
- [output schema]

Rules:
- Stay within scope
- Use only the provided tools
- Do not delegate unless the workflow explicitly allows it
- If required data is missing, return a clear failure reason
```

## Input / Output Guidance

Prefer contracts like these:

```json
{
  "task_id": "req-123",
  "intent": "scripture_lookup",
  "input": {
    "passage": "Psalm 23",
    "translation": "NIV"
  }
}
```

```json
{
  "task_id": "req-123",
  "status": "success",
  "result": {
    "title": "Psalm 23 (NIV)",
    "verses": ["..."]
  },
  "warnings": []
}
```

Benefits:

- Easier validation in `Code`, `IF`, and `Switch` nodes
- Cleaner merges between branches
- Easier testing of each agent in isolation

## Delegation Rules

Set these explicitly in the workflow design:

- Maximum number of sub-agent hops
- Whether a specialist can call another specialist
- When a reviewer can request a retry
- When the system must stop and ask a human

If a reviewer can loop work back to an executor, cap the loop count.

## Context Control

Prevent context rot by limiting what each agent sees:

- Pass only the fields needed for the current step
- Strip internal reasoning or long histories before handoff
- Keep tool catalogs short and task-specific
- Move hard rules into deterministic nodes where possible

## Where To Put Business Logic

Keep these outside prompts when possible:

- Approval thresholds
- Policy enforcement
- Required field validation
- Permissions and scope checks
- Retry counters and timeouts

Prompts should express strategy, role, and communication constraints. Deterministic nodes should enforce the rules that must not drift.
