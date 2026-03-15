# Example Blueprints

Use these examples when the user asks for a concrete multi-agent n8n design.

## Example 1: Intent Router For Church Ops

Use this when requests fall into clear buckets.

Workflow shape:

1. `Webhook` receives a request.
2. Classifier agent labels it as `schedule`, `scripture`, `lyrics`, `slides`, or `out_of_scope`.
3. `Switch` routes to a dedicated sub-workflow.
4. Each branch returns a structured response.

Why it works:

- Responsibilities are clean.
- Each domain can evolve independently.
- Misroutes are visible and testable.

## Example 2: Worship Planning Orchestrator

Use this when one assistant must coordinate several domains for a single plan.

Agent inventory:

- **Planner agent**: interpret the service goal and decide needed domains
- **Scripture agent**: fetch passages and translation-specific content
- **Lyrics agent**: prepare song/verse payloads
- **Schedule agent**: align order, participants, and timing
- **Reviewer agent**: check completeness and consistency

Workflow shape:

1. User request enters the orchestrator.
2. Orchestrator calls the needed specialists.
3. Specialists return structured payloads.
4. Reviewer checks for missing sections or conflicts.
5. Final summary is assembled for the user.

Why it works:

- The orchestrator stays focused on coordination.
- Domain logic lives in specialists.
- Review is explicit instead of implied.

## Example 3: Planner -> Builder -> Validator For Workflow Creation

Use this when the system is generating or modifying workflows.

Agent inventory:

- **Planner**: turn the request into a small build plan
- **Builder**: create nodes and connections
- **Validator**: inspect structure and required fields
- **Explainer**: summarize what changed

Workflow shape:

1. Planner emits a step list.
2. Builder creates or updates the workflow.
3. Validator checks for structural issues.
4. If validation fails, the builder retries once.
5. Explainer returns the final summary.

Why it works:

- Planning, implementation, and quality control stay separate.
- The retry loop has a hard cap.
- Validation is treated as a first-class stage.

## Example 4: Parallel Analysis With Merge

Use this when the same input needs independent judgments.

Agent inventory:

- **Classifier**
- **Risk scorer**
- **Summarizer**
- **Decision formatter**

Workflow shape:

1. Normalize input.
2. Run specialist analyses in parallel.
3. Merge their outputs.
4. Format a final recommendation.

Why it works:

- Throughput is better than sequential analysis.
- Each branch can be tested alone.
- Merged output can be validated against a shared schema.

## Prompting Shortcuts

If the user is vague, ask for or infer these fields:

- User-facing entrypoint
- Expected agent roles
- Systems or credentials each agent may access
- Required outputs
- Approval requirements
- Failure tolerance

If those answers are missing, default to a small classifier or orchestrator pattern, not a complex hierarchy.
