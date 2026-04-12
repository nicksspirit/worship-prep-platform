---
workflow_id: "yLfyYiLy9RnTlbUU"
workflow_name: "Schedule Intake Sub-Workflow"
sync_source: "live n8n workflow"
sync_status: "synced"
last_synced: "2026-04-12"
---

```mermaid
flowchart TD
    trigger["Execute Workflow Trigger\n(raw_content, sender_name,\nsender_phone, source_message_id)"]
    parser["Schedule Parser Agent\n⬡ @n8n/n8n-nodes-langchain.agent"]
    gemini["Gemini Model\n(gemini-3.1-flash-lite-preview)"]
    createPost["Create Schedule (POST)\n→ /api/v1/schedules/intake"]
    patchTool["Update Schedule (PATCH)\n→ /api/v1/schedules/intake"]

    trigger --> parser

    gemini -. ai_languageModel .-> parser
    createPost -. ai_tool .-> parser
    patchTool -. ai_tool .-> parser
```

Prompt-bearing nodes:
- `Schedule Parser Agent` → `n8n/prompts/schedule-parser-agent__schedule-intake-sub-workflow.md`

Supporting nodes:
- `Execute Workflow Trigger` — explicit workflow input schema with `raw_content`, `sender_name`, `sender_phone`, and `source_message_id`
- `Create Schedule (POST)` — HTTP POST AI tool; used for brand-new schedules; sends to `/api/v1/schedules/intake`; expects every item to include a valid `item_type`
- `Update Schedule (PATCH)` — HTTP PATCH AI tool; used for corrections or additions to an existing schedule; same endpoint; expects every item to include a valid `item_type`
- Both tools have `neverError: true` and `retryOnFail: true` (max 2 tries)

The parser agent now owns schedule normalization from raw text, including `item_type` resolution and HH:MM time normalization. It decides whether to POST (new) or PATCH (update) based on the intent described in the user prompt, and if the API returns validation details it retries the same method once before returning the final error upstream.
