---
workflow_id: "YUK-DB69JHvv5w4Z9rodK"
workflow_name: "Worship Prep Platform (dev)"
sync_source: "live n8n workflow"
sync_status: "synced"
last_synced: "2026-04-19"
---

# Attach Chat Context (`Worship Prep Platform (dev)`)

This document defines the contract for a single n8n node placed **after** `Attach Session ID` and **before** `WPP Front Desk Agent`.

## Purpose

Normalize inbound WhatsApp fields and inject **authoritative calendar anchors** so the front desk agent does not guess what "today" or "next Sunday" means.

## Upstream requirement (`Attach Session ID`)

In **Edit Fields (Set)** node **v3.3+**, the default **`Include Other Input Fields`** / `includeOtherFields` is **off**. If you only assign `sessionId`, the node output will contain **only** `{ "sessionId": "..." }` and will **drop** the WhatsApp payload (`messages`, `contacts`, etc.). `Attach Chat Context` then sees no message body.

- **Fix:** turn **Include Other Input Fields** on for `Attach Session ID` so `messages` / `contacts` pass through alongside `sessionId`.

The Code node below also **merges** `$('WhatsApp Trigger').all()` as a safety net when upstream fields are missing.

## Node

- **Name:** `Attach Chat Context`
- **Type:** `n8n-nodes-base.code` (JavaScript)
- **Mode:** Run Once for All Items (or Each Item — either works as long as you return one item per inbound message)

## Output contract (top-level `$json` fields)

The front desk agent prompt expects these fields on the item passed into the LangChain Agent node:

- **`message_text`**: string — the inbound WhatsApp text body (empty string if missing)
- **`sessionId`**: string — pass-through from `Attach Session ID` (typically WhatsApp `wa_id`)
- **`sender_phone`**: string | null — E.164 phone when available
- **`sender_name`**: string | null — display/profile name when available
- **`source_message_id`**: string | null — WhatsApp message id when available
- **`message_received_at`**: string | null — ISO timestamp when available
- **`chat_context`**: object — minimal authoritative calendar keys (see below)

### `chat_context` object

- **`church_timezone`**: IANA timezone string used for all calendar math
- **`today_iso`**: `YYYY-MM-DD` in `church_timezone`
- **`this_sunday_iso`**: the upcoming Sunday **including today if today is Sunday**
- **`next_sunday_iso`**: always **7 days after** `this_sunday_iso` (so if today is Sunday, "next Sunday" is a week later)

## Reference implementation (Code node)

> Note: n8n Code nodes expose Luxon as the global `DateTime` (see n8n Code node docs). The WhatsApp trigger spreads Meta `changes[].value` onto each item (`messages`, `contacts`, `statuses`, …). Use defensive checks for non-text messages and for **status-only** webhooks (delivered/read), which have `statuses` but often no `messages` — those are filtered out so the agent is not called with an empty body.

```javascript
const CHURCH_TZ = 'America/Los_Angeles';

function nextSundayFrom(dt) {
  const d = dt.startOf('day');
  const weekday = d.weekday;
  const daysUntilSunday = (7 - weekday) % 7;
  return d.plus({ days: daysUntilSunday });
}

function extractInboundText(message) {
  if (!message) return '';
  if (message.text?.body) return message.text.body;
  const ib = message.interactive;
  if (ib?.button_reply?.title) return ib.button_reply.title;
  if (ib?.button_reply?.id) return String(ib.button_reply.id);
  if (ib?.list_reply?.title) return ib.list_reply.title;
  if (message.button?.text) return message.button.text;
  if (message.image?.caption) return message.image.caption;
  if (message.video?.caption) return message.video.caption;
  if (message.document?.caption) return message.document.caption;
  return '';
}

let triggerItems = [];
try {
  triggerItems = $('WhatsApp Trigger').all();
} catch (err) {
  triggerItems = [];
}

return items.flatMap((item, index) => {
  const fromUpstream = item.json ?? {};
  const fromTrigger = triggerItems[index]?.json ?? triggerItems[0]?.json ?? {};
  const prev = { ...fromTrigger, ...fromUpstream };

  const statuses = prev.statuses;
  const messagesArr = prev.messages;
  if (
    Array.isArray(statuses) &&
    statuses.length > 0 &&
    (!Array.isArray(messagesArr) || messagesArr.length === 0)
  ) {
    return [];
  }

  const message = Array.isArray(messagesArr) ? messagesArr[0] : undefined;
  const contact = Array.isArray(prev.contacts) ? prev.contacts[0] : undefined;

  const messageText = extractInboundText(message);

  const senderPhone = contact?.wa_id ?? message?.from ?? null;
  const senderName = contact?.profile?.name ?? null;
  const sourceMessageId = message?.id ?? null;
  const messageReceivedAt = message?.timestamp ?? null;

  const sessionId =
    (fromUpstream.sessionId && String(fromUpstream.sessionId)) ||
    (senderPhone && String(senderPhone)) ||
    null;

  const todayStart = DateTime.now().setZone(CHURCH_TZ).startOf('day');
  const thisSunday = nextSundayFrom(todayStart);
  const nextSunday = thisSunday.plus({ days: 7 });

  const chat_context = {
    church_timezone: CHURCH_TZ,
    today_iso: todayStart.toISODate(),
    this_sunday_iso: thisSunday.toISODate(),
    next_sunday_iso: nextSunday.toISODate(),
  };

  return [
    {
      json: {
        ...prev,
        message_text: messageText,
        sessionId,
        sender_phone: senderPhone,
        sender_name: senderName,
        source_message_id: sourceMessageId,
        message_received_at: messageReceivedAt,
        chat_context,
      },
    },
  ];
});
```

## Prompt wiring notes

- Update the front desk **user prompt** to read inbound text from `{{ $json.message_text }}` (not directly from `WhatsApp Trigger`) so intermediate nodes do not break the expression.
- Update the front desk **system prompt** to treat `{{ JSON.stringify($json.chat_context, null, 2) }}` as authoritative for relative date phrases.
