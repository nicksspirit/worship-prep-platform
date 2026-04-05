Read the prompts in `n8n/prompts` and sync the prompts to the respective agents and chat models specified in the YAML frontmatter.

# General Rules
- Check if the system and user prompt stored in `n8n/prompts` already matches what is configured in the n8n node in order to avoid unnecessary updates to the workflows
- Prompt files names should adhere to following convention of <AGENT_OR_NODE_NAME>__<N8N_WORKFLOW_NAME>.md
- YAML formatter should maintain the following details: workflow_id, workflow_name, node_id, node_name, node_type, and prompt_type
- After making changes to an n8n workflow, make sure to publish it again with appropiate version name and description nodes and prompt files stay in sync