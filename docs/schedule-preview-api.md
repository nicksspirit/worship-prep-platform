# Publish a Schedule Preview

The Technical Team publishes the song slides prepared for a service.
The API returns an unlisted browser link. Only include lyrics cleared for sharing
with anyone who has the link.

## Request

`POST /api/v1/schedule-previews` on the API host (`https://api.rccgcm.org` in
production). Send JSON with `Authorization: Bearer <key>` using an Integration
Client key with the `schedule.preview.publish` scope. A superuser issues the key
under **API keys** in Django admin. An existing catalog key needs the publish scope
to use this endpoint.

Save this example as UTF-8 `schedule-preview.json`:

```json
{
  "title": "Sunday Worship",
  "sections": {
    "call_to_worship": [
      { "title": "Opening Song", "slides": [{ "section_label": "Verse", "lines": ["First line", "Second line"] }] }
    ],
    "praise": [
      { "title": "Praise Song", "slides": [{ "section_label": "Chorus", "lines": ["Chorus line"] }] }
    ],
    "worship": [
      { "title": "Worship Song", "slides": [{ "lines": ["Worship line"] }] }
    ]
  }
}
```

New publishes require `sections` with at least one song each in `call_to_worship`,
`praise`, and `worship`. Add `special_song` with the same song array shape when
needed. The preview displays the sections in that order, with Special Song after
Worship when present. Within each section, the arrays follow presentation order.
Previously published previews with a flat song list continue to open.

Send each slide separately and each line as its own string. The preview uses the
platform's 16:9 projection style.

For example, to show a chorus again after the second verse, send it again at
that position. A song can appear more than once. The platform uses the supplied
slides even if a song with the same title exists in the catalog.

Send up to 30 songs across all sections, with 1–50 slides per song. Schedule and song titles must contain text
and are limited to 160 characters. `section_label` is optional and can be up to
80 characters. `lines` is required and can contain 0–10 strings of up to 160
characters each. An empty `lines` array represents a blank slide. Keep each
string on one line; control characters and unknown fields are rejected.

## Response

`201 Created`:

```json
{
  "preview_url": "https://app.rccgcm.org/schedule-previews/a30b2db7-b33a-44c9-99fd-d0791898ac6e/",
  "expires_at": "2026-11-11T15:30:00Z"
}
```

Every successful POST creates a new link. Publish again after a correction and
share the new link; the earlier link keeps showing its own snapshot until it
expires. Unavailable and expired links both return `404`.

Staff can find published previews in Django admin under **Service Preparation →
Schedule Previews**. The list shows creation and expiry times and links to active
previews. Superusers and staff with the Schedule Preview delete permission can
open a preview record by its title and delete it to revoke the link immediately.
Each new record shows the POST path, request ID, source IP as resolved by Bolt,
submitted JSON, and the publishing API key's database ID. The authorization
header is excluded from the stored request details. Earlier records show the
stored preview when the original request payload is unavailable.

| Status | Meaning |
| --- | --- |
| `401` | Missing, invalid, expired, or revoked API key. |
| `403` | Valid key without `schedule.preview.publish`. |
| `422` | Request body does not match the schema. |
| `429` | More than 12 publishes per key in a one-minute window. Honor `Retry-After`. |

See `/api/v1/docs` on the API host for the OpenAPI reference.

## Publish from Windows

With the key available to the process as `WPP_SCHEDULE_PREVIEW_KEY`, run:

```powershell
$preview = Invoke-RestMethod -UseBasicParsing -Method Post -MaximumRedirection 0 `
  -Uri 'https://api.rccgcm.org/api/v1/schedule-previews' `
  -Headers @{ Authorization = "Bearer $env:WPP_SCHEDULE_PREVIEW_KEY" } `
  -ContentType 'application/json; charset=utf-8' `
  -InFile '.\schedule-preview.json'
$preview.preview_url
$preview.expires_at
```

Share `preview_url`, never the publishing key. The URL points to the browser app,
not the API host. Viewers do not need an account. After `expires_at` the page no
longer serves the lyrics.

The JSON file must already contain the arranged song slides. The Catalog Exporter
does not read saved EasyWorship schedules. See Microsoft's
[`Invoke-RestMethod` reference](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.utility/invoke-restmethod?view=powershell-5.1)
for the PowerShell command options.

## Server settings

`SCHEDULE_PREVIEW_TTL_HOURS` sets the lifetime of new links (default `72`). Existing
links keep their original expiry. The API does not accept an expiry override.
`SCHEDULE_PREVIEW_APP_ORIGIN` sets the browser origin returned in `preview_url`
(production default `https://app.rccgcm.org`; local default `http://localhost:8001`).
Expired snapshots are removed from the database on the next successful publish.
