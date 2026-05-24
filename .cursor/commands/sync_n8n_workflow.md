Read the n8n workflow, keep the prompts in `n8n/prompts` synced with the AI nodes defined in the workflow, and keep the workflow diagram in `n8n/workflow` synced with the workflow architecture and node flow.

# General Rules
- Treat every n8n workflow change as a three-way sync: the workflow itself, the prompt files in `n8n/prompts`, and the Mermaid diagram in `n8n/workflow`
- Fail early if n8n authentication or MCP connectivity is unavailable; do not continue with prompt syncing, workflow syncing, or diagram syncing in a degraded state
- If authentication or MCP access fails, stop immediately and tell the user to check the n8n init, connection, credentials, or MCP server configuration before continuing
- Check whether the system and user prompts stored in `n8n/prompts` already match what is configured in the n8n node before making prompt updates so you avoid unnecessary workflow changes
- Prompt file names should follow `<AGENT_OR_NODE_NAME>__<N8N_WORKFLOW_NAME>.md`
- Prompt YAML frontmatter should keep `workflow_id`, `workflow_name`, `node_id`, `node_name`, `node_type`, and `prompt_type`
- Workflow diagram files should live in `n8n/workflow` and use one Mermaid-backed Markdown file per workflow, named with a lowercase kebab-case workflow slug such as `song-lyrics-intake-sub-workflow.md`
- Every workflow diagram must show the current node architecture, the important branches or handoffs, and the prompt-bearing AI nodes that are represented in `n8n/prompts`
- When a workflow changes, update the Mermaid diagram even if the prompt text itself did not change
- When a prompt-bearing node changes, update the corresponding prompt file and confirm the diagram still matches the latest flow
- If a workflow has multiple prompt-bearing nodes, make sure each prompt file stays in sync and the shared workflow diagram reflects how those nodes connect
- If you cannot verify the live workflow structure directly for reasons other than an auth or MCP failure, do not invent hidden nodes as facts; preserve what is known and clearly mark anything that still needs verification
- After making changes to an n8n workflow, make sure to publish it again with an appropriate version name and description so the workflow, prompts, and diagram stay in sync
