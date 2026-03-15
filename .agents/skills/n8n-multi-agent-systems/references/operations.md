# Operations, Safety, And Rollout

Use this file when the user asks about observability, testing, failure handling, or productionizing a multi-agent workflow.

## Minimum Operating Checklist

Before calling a multi-agent design production-ready, define:

- Request ID propagation across all branches and sub-workflows
- Per-agent logging for inputs, outputs, tool calls, and errors
- Timeout, retry, and fallback behavior per agent
- Human approval steps for high-stakes actions
- Metrics for latency, failure rate, and delegation frequency

## Observability

Capture enough data to debug handoffs:

- Workflow ID and execution ID
- Agent name and stage
- Chosen route or delegated specialist
- Input summary and output summary
- Tool or sub-workflow invoked
- Error category and retry count
- Final outcome

Good practice in n8n:

- Add a normalized trace object early
- Enrich it at each stage
- Persist key events to a log destination or database

## Failure Handling

Design for partial failure instead of assuming every branch succeeds.

For each agent, decide:

- What counts as a retryable error
- How many retries are allowed
- Whether a fallback agent exists
- Whether the flow should continue with partial results
- When to escalate to a human

Common fallback patterns:

- Reviewer rejects output -> send back once for correction
- Specialist times out -> use cached data, alternate branch, or human review
- Classifier uncertain -> route to clarification or manual triage

## Human In The Loop

Require approval when the workflow may:

- Trigger sensitive communications
- Update important records
- Spend money or create commitments
- Publish externally
- Access sensitive data outside normal boundaries

Have agents prepare proposals, drafts, or recommended actions rather than acting autonomously in those cases.

## Testing Strategy

Test bottom-up:

1. Test one specialist with representative inputs.
2. Test deterministic validation around that specialist.
3. Test routing decisions.
4. Test orchestration and end-to-end summaries.
5. Test failure and timeout paths deliberately.

Use small fixtures and stable schemas so regressions are obvious.

## Metrics

Track metrics that reveal system shape, not just uptime:

- Per-agent latency
- Per-agent success rate
- Retry frequency
- Delegation frequency
- Token or model cost per request if available
- Human approval rate
- Reviewer rejection rate

These metrics help identify prompt drift, orchestration bottlenecks, and unnecessary delegation.

## Environment Separation

Keep dev, staging, and production behavior separate:

- Use different credentials or projects per environment
- Test new prompts and routing logic before production activation
- Keep side effects disabled or sandboxed in lower environments
- Roll out new agent contracts incrementally

## Rollout Sequence

Prefer this progression:

1. Single specialist workflow
2. Multiple specialists without orchestration
3. Classifier or orchestrator
4. Reviewer or validator
5. Human approval and production monitoring

This order keeps failures local while the design is still moving.

## Red Flags

Reconsider the design if you see:

- The orchestrator prompt growing into a policy manual
- Specialists returning inconsistent shapes
- Frequent retries caused by unclear ownership
- Agents needing the same broad toolset
- Loops that depend on "it usually stops"

Those are signs the contracts or topology need to be simplified.
