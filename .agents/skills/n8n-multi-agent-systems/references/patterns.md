# Multi-Agent Patterns

Use this file when choosing the workflow topology.

## Selection Rules

Start with the smallest structure that preserves clarity:

| Pattern | Best for | n8n shape | Avoid when |
|---|---|---|---|
| Classifier + branches | Clear intents with mostly independent handling | Trigger -> classifier -> `Switch` -> specialist branches | The request needs cross-domain planning |
| Orchestrator + specialists | One user-facing agent delegating to several domains | Trigger -> orchestrator -> tools or `Execute Workflow` | The orchestrator would need deep domain logic |
| Planner -> executors -> reviewer | Complex tasks needing decomposition and quality control | Planner branch -> executor sub-workflows -> reviewer/validator | The task is simple enough for one specialist |
| Parallel specialists + merge | Independent analyses on the same input | Fan-out branches -> `Merge` -> summarizer | Outputs are highly interdependent |
| Hybrid | Mixed routing plus delegation | Classifier/orchestrator plus branches and reviewers | You have not proven a simpler pattern fails |

## Pattern 1: Classifier + Branches

Use when the main problem is routing, not collaboration.

Typical flow:

1. Receive a request.
2. Classify it into a small intent set.
3. Route with `Switch`.
4. Hand each intent to its own specialist workflow.

Good examples:

- Support triage: billing, scheduling, lyrics, tech booth
- Content pipeline: scripture lookup, slide formatting, announcement drafting
- Intake router: simple domain separation before heavy processing

Design notes:

- Keep the intent list short and mutually exclusive.
- Route to sub-workflows rather than stuffing all behavior into branches.
- Add a default out-of-scope branch.

## Pattern 2: Orchestrator + Specialists

Use when one user-facing agent must coordinate several focused capabilities.

Typical flow:

1. Orchestrator interprets the request.
2. Orchestrator selects one or more specialists.
3. Specialists return structured payloads.
4. Orchestrator integrates and responds.

Good examples:

- Worship planning assistant that can call scripture, lyrics, schedule, and publishing agents
- Internal ops assistant spanning email, docs, and database tasks
- Research assistant that delegates retrieval, synthesis, and QA

Design notes:

- Treat specialists as tools or sub-workflows.
- Keep the orchestrator prompt about delegation, not domain work.
- Give each specialist scoped credentials and data access.

## Pattern 3: Planner -> Executors -> Reviewer

Use when correctness matters more than speed and the task has stages.

Typical flow:

1. Planner decomposes the request.
2. Executors handle the steps.
3. Reviewer or validator checks the result.
4. Approval or escalation occurs if needed.

Good examples:

- Service plan generation with validation before publishing
- Long-form content creation with fact-check or style review
- Workflow-building assistant that plans, implements, then validates

Design notes:

- Make the planner return a structured step list.
- Keep executors focused on one step each.
- Use the reviewer to catch quality or policy issues, not to redo the whole task.

## Pattern 4: Parallel Specialists + Merge

Use when several analyses can run independently over the same input.

Typical flow:

1. Normalize the input once.
2. Fan out into parallel specialist branches.
3. Merge outputs.
4. Summarize or score the combined result.

Good examples:

- Sentiment, classification, and entity extraction
- Multiple candidate rankings or rubric-based evaluations
- Parallel source retrieval before synthesis

Design notes:

- Keep each branch stateless when possible.
- Normalize schemas before merging.
- Define what to do when one branch fails or times out.

## n8n Mapping

Map architectural concepts to concrete nodes:

- **Agent boundary**: `Execute Workflow`
- **Delegation**: orchestrator calling specialist sub-workflows
- **Routing**: `Switch`
- **Deterministic gating**: `IF`, `Switch`, `Code`, standard nodes
- **Parallelism**: separate branches starting from the same upstream node
- **Integration**: `Merge`, summarizer agent, or deterministic formatter
- **Human review**: explicit approval path before side effects

## Default Recommendation

If the user is unsure, start here:

1. Use classifier + branches when intents are obvious.
2. Use orchestrator + specialists when one assistant must compose capabilities.
3. Add reviewer/validator agents only after the core path works.

## Anti-Patterns

Avoid these designs:

- One giant manager agent that plans and executes everything
- Every agent seeing every tool or credential
- Unbounded agent-to-agent chatter
- Business rules encoded only in prompts
- Dynamic creation of many agent types when a stable catalog would work
