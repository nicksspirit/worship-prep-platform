---
name: n8n-multi-agent-systems
description: Design and build effective multi-agent systems in n8n, including classifier routing, orchestrator agents, planner-executor flows, specialist sub-workflows, agent contracts, delegation rules, observability, safety rails, and rollout strategy. Use when creating or refining n8n workflows with multiple AI Agent nodes, Execute Workflow orchestration, validator/reviewer agents, human-in-the-loop approvals, or any request about multi-agent architecture in n8n.
---

# n8n Multi-Agent Systems

Build multi-agent n8n workflows as a small operating model, not as one giant prompt. Prefer a few focused agents with explicit contracts, tight tool scopes, and observable handoffs.

## Quick Start

Follow this sequence whenever the user asks for a multi-agent design or implementation:

1. Confirm that multi-agent is justified.
2. Pick a topology that matches the task shape.
3. Define each agent's contract before wiring nodes.
4. Map the design to n8n primitives.
5. Add guardrails, tracing, and human review.
6. Build and validate one slice at a time.

## 1. Confirm The Need

Use multi-agent only when the task benefits from separation of concerns:

- Different domains need different tools, prompts, or credentials.
- The workflow naturally splits into planning, execution, review, or routing stages.
- Parallel analysis improves throughput.
- A validator or reviewer should check a previous agent's output.

Stay single-agent when one prompt plus a few tools can solve the task cleanly.

## 2. Choose A Topology

Pick the simplest topology that fits:

- **Classifier + branches** for clear intent routing.
- **Orchestrator + specialists** for one user-facing agent delegating to domain workflows.
- **Planner -> executors -> reviewer** for complex tasks with quality gates.
- **Parallel specialists + merge** for independent analyses over the same input.
- **Hybrid** only when a simpler pattern is clearly insufficient.

Read the matching design guidance before building:

- [patterns.md](references/patterns.md) for topology selection and n8n mapping
- [examples.md](references/examples.md) for concrete workflow shapes

## 3. Define The Agent Inventory

For each agent, write a compact contract before touching workflow JSON:

- Responsibility: the single job this agent owns
- Inputs: the fields or schema it receives
- Outputs: the structured payload it must return
- Tools: only the nodes, APIs, or sub-workflows it needs
- Out of scope: what it must not do
- Stop rule: when it should finish, escalate, or fail

Use the templates in [agent-contracts.md](references/agent-contracts.md).

## 4. Map The Design To n8n

Default implementation mapping:

- **Entrypoint**: `Webhook`, chat trigger, or manual trigger
- **Classifier**: `AI Agent` or `Basic LLM Chain`, then `Switch`
- **Specialist agent**: dedicated `AI Agent` node or sub-workflow
- **Delegation boundary**: `Execute Workflow` for strong isolation
- **Parallel work**: separate branches, then `Merge`
- **Deterministic rules**: `IF`, `Switch`, `Code`, or normal nodes outside prompts
- **Approval / escalation**: explicit human review branch

Prefer sub-workflows when an agent needs its own tools, memory, credentials, or lifecycle.

## 5. Add Guardrails First

Every production-oriented multi-agent workflow should define:

- Hop limits or maximum delegation depth
- Timeout and retry policy per agent
- Fallback behavior for partial failure
- Human approval for high-stakes actions
- Request IDs and per-agent trace logging
- Metrics for latency, error rate, and delegation frequency

Read [operations.md](references/operations.md) for the operating checklist.

## 6. Build Iteratively

Do not assemble the full graph in one shot.

Recommended order:

1. Build the smallest useful specialist.
2. Validate its inputs, outputs, and prompt contract.
3. Add the next specialist or routing branch.
4. Add the orchestrator only after specialists are stable.
5. Add reviewer, validator, and approval branches last.

## Output Shape

When helping a user design a multi-agent n8n system, produce these artifacts:

1. Recommended topology and why it fits
2. Agent table with responsibility, tools, inputs, outputs, and failure policy
3. Workflow outline showing triggers, branches, sub-workflows, and merges
4. Safety and observability plan
5. Incremental build order

## Integration With Other Skills

Use nearby project skills instead of duplicating their detail:

- `n8n-workflow-patterns` for general workflow structures
- `n8n-mcp-tools-expert` for node discovery, workflow creation, and validation tooling
- `n8n-node-configuration` for node-specific property dependencies
- `n8n-expression-syntax` for expressions between agents and branches
- `n8n-validation-expert` for interpreting workflow validation issues

## References

- [patterns.md](references/patterns.md) for architecture selection
- [agent-contracts.md](references/agent-contracts.md) for prompts and contracts
- [operations.md](references/operations.md) for safety, testing, and rollout
- [examples.md](references/examples.md) for concrete n8n multi-agent blueprints
