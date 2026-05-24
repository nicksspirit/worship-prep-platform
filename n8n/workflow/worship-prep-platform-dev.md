---

## workflow_id: "YUK-DB69JHvv5w4Z9rodK"

workflow_name: "Worship Prep Platform (dev)"
sync_source: "live n8n workflow"
sync_status: "synced"
last_synced: "2026-04-19"

```mermaid
flowchart TD
    whatsapp["WhatsApp Trigger"]
    attachId["Attach Session ID\n(Set — extract wa_id as sessionId)"]
    attachCtx["Attach Chat Context\n(Code — inject calendar + sender fields)"]
    frontDesk["WPP Front Desk Agent\n⬡ @n8n/n8n-nodes-langchain.agent"]
    gemini["Gemini Model\n(gemini-3.1-flash-lite-preview)"]
    scheduleLookup["Schedule Lookup\n(HTTP GET /api/v1/schedules/...)"]
    scheduleIntakeTool["Schedule Intake Tool\n(toolWorkflow → Schedule Intake Sub-Workflow)"]
    lyricsIntakeTool["Song Lyrics Intake Tool\n(toolWorkflow → Song Lyrics Intake Sub-Workflow)"]
    sendMsg["Send message\n(WhatsApp)"]
    chatTrigger["Chat Trigger (disabled)"]
    shimNode["WhatsApp Shim (disabled)"]

    whatsapp --> attachId --> attachCtx --> frontDesk --> sendMsg

    gemini -. ai_languageModel .-> frontDesk
    scheduleLookup -. ai_tool .-> frontDesk
    scheduleIntakeTool -. ai_tool .-> frontDesk
    lyricsIntakeTool -. ai_tool .-> frontDesk

    chatTrigger -. disabled .-> shimNode
```



Prompt-bearing nodes:

- `WPP Front Desk Agent` → `n8n/prompts/wpp-front-desk-agent__worship-prep-platform-dev.md`

Supporting nodes:

- `Attach Session ID` — extracts `wa_id` from the WhatsApp payload and attaches it as `sessionId` for the reply node; **must** keep **Include Other Input Fields** enabled (Set v3.3+) so `messages` / `contacts` are not stripped before `Attach Chat Context`
- `Attach Chat Context` — normalizes inbound WhatsApp fields and injects authoritative calendar anchors for the front desk agent prompt (see `n8n/workflow/attach-chat-context__worship-prep-platform-dev.md`)
- `WPP Front Desk Agent` runs without attached conversation memory to avoid stale carry-over answers (for example, outdated dates or unsolicited verse references).
- `Schedule Lookup` — HTTP GET tool; calls `/api/v1/schedules/{date}` or `?upcoming=true` on behalf of the agent
- `Schedule Intake Tool` — delegates to the Schedule Intake Sub-Workflow (`yLfyYiLy9RnTlbUU`); passes `raw_content`, `sender_name`, `sender_phone`, and `source_message_id`; the front desk agent now routes raw schedule text instead of parsed agenda items
- `Song Lyrics Intake Tool` — delegates to the Song Lyrics Intake Sub-Workflow (`oQdiLHbdYm7wGgbD`); passes `raw_lyrics`, `schedule_date`, `item_type`
- `Chat Trigger` + `WhatsApp Shim` — disabled dev-testing shim nodes; not part of the live execution path

