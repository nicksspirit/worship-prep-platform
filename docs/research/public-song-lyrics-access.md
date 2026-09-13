# Public Song Lyrics Access: Licensing Constraints and Product Options

**Status:** Planning research for the Worship Prep Platform pivot  
**Jurisdiction assumed:** United States  
**Last reviewed:** 2026-07-26

> This note is planning research, not legal advice. Copyright ownership, license
> coverage, and contract terms vary by song, source, church, territory, and
> subscription. The church should have its actual agreements reviewed by
> qualified counsel or obtain written confirmation from its licensing provider
> before exposing copyrighted lyrics.

## Decision

Do **not** make complete copyrighted lyrics, lyric-bearing search results, or
Projection Previews publicly accessible in V1 unless the church obtains written
permission that expressly covers an on-demand public web catalog.

The church's ordinary right to project lyrics during a worship service does not,
on the sources reviewed, extend to publishing a permanently available,
searchable public catalog of complete lyrics. The V1 public experience should
therefore be:

- metadata-only search results for copyrighted songs;
- metadata-only Song Detail pages for copyrighted songs;
- complete lyrics and Projection Preview only for songs verified as public
  domain or covered by song-specific permission that includes this web use; and
- no copyrighted lyric text in the API, even behind an API key, until the
  applicable license expressly permits that distribution.

Metadata-only output does not settle whether the application may copy and
full-text-index the underlying copyrighted lyrics. If that internal copying is
not confirmed, V1 search must index only metadata for copyrighted songs and may
index lyric text only for public-domain or directly permitted songs.

If complete copyrighted lyrics are essential to V1, change the product from a
public catalog to a restricted operational tool and obtain written confirmation
that the church's actual licenses cover storage, retrieval, display, and machine
distribution in that design. Authentication reduces exposure; it does not
create copyright permission.

## Sourced facts

### Copyright law distinguishes worship-service display from public web access

Copyright owners hold exclusive rights to reproduce and distribute copies of a
work and, for musical and literary works, to display the work publicly.
[17 U.S.C. § 106](https://www.copyright.gov/title17/92chap1.html#106)
defines public display broadly enough to include transmitting a display to the
public where recipients may receive it in different places or at different
times.
[17 U.S.C. § 101](https://www.copyright.gov/title17/92chap1.html#101)

The religious-services exemption applies to a performance or display **in the
course of services at a place of worship or other religious assembly**.
[17 U.S.C. § 110(3)](https://www.copyright.gov/title17/92chap1.html#110)
The Copyright Office's explanatory guide likewise describes the exemption as
limited to performances and displays in the course of those services.
[U.S. Copyright Office, General Guide to the Copyright Act of 1976, “Religious
services”](https://www.copyright.gov/reports/guide-to-copyright.pdf)

Fair use is a case-specific four-factor inquiry covering purpose and character,
nature of the work, amount and substantiality used, and market effect. The
statute supplies no universally safe word count or percentage for a lyric
snippet.
[17 U.S.C. § 107](https://www.copyright.gov/title17/92chap1.html#107)

Song titles, names, and short phrases are not protected by copyright, although
other law such as trademark may still apply. Facts are not protected by
copyright, while original expression and some original selection or arrangement
may be.
[U.S. Copyright Office, Circular 33](https://www.copyright.gov/circs/circ33.pdf);
[Copyright in General FAQ](https://www.copyright.gov/help/faq/faq-general.html)

### CCLI's published scope is tied to congregational singing and services

CCLI describes its U.S. Church Copyright License as permission to project
lyrics, print lyrics for a congregation, and reproduce covered worship songs.
Its public product page separately describes the Streaming License as covering
live-streamed or uploaded worship services.
[CCLI, Church Copyright License](https://ccli.com/us/en/church-copyright-license);
[CCLI, Streaming Licenses](https://ccli.com/us/en/streaming)

CCLI's published license summary says the base license permits electronic
storage, retrieval, and use of song files to enable visual projection for
congregational singing. It also says:

- all rights not specified are reserved to the copyright owner;
- copies may not be distributed for use outside church services;
- each song must be validated as covered;
- required title, writer, copyright, permission, and CCLI license information
  must accompany reproductions;
- copying activity must be reported when required; and
- copies made under the program must be destroyed if the agreement expires.

[CCLI, Church Copyright License
Summary](https://ccli.com/global/%EF%BF%BD%27%27%EF%BF%BD%22%22/church-copyright-license-summary)

CCLI describes the Streaming License as covering online worship: live streams
or uploaded services, including lyrics embedded in or behind the service video.
That published scope is different from an independently browsable lyrics
catalog.
[CCLI, Streaming Licenses](https://ccli.com/us/en/streaming)

EasyWorship's official documentation says SongSelect lyrics require a
SongSelect subscription and are imported into the local EasyWorship song
database.
[EasyWorship, How to Import Songs from
SongSelect](https://support.easyworship.com/support/solutions/articles/24000028111-how-to-import-songs-from-songselect)
EasyWorship's FAQ identifies CCLI as the provider covering copying for
congregational singing and says CCLI and SongSelect are independent of
EasyWorship.
[EasyWorship FAQ, “What Is
CCLI?”](https://support.easyworship.com/support/solutions/articles/6000085139)
EasyWorship also tracks song projection/printing activity for copyright
reporting and directs customers to CCLI for the reporting rules.
[EasyWorship, Songs: Printing &
Reporting](https://support.easyworship.com/support/solutions/articles/24000020414-songs-printing-reporting)

## Inferences for this product

The conclusions below are architectural and product-planning inferences from
the sourced facts. They are not claims that a court or licensor has ruled on
this exact application.

### Complete public lyrics

**Risk: unacceptable without additional permission.**

A public Song Detail page containing complete lyrics creates a server-side copy
and transmits the lyrics for viewing on demand. A public Projection Preview does
the same while also presenting the lyrics as slides. Neither use is limited to
the course of a worship service, and neither appears in CCLI's published list of
permitted base-license activities.

The Streaming License is not a substitute: its published use is a worship
service stream or recording, not a standalone searchable lyrics repository.

### Search snippets

**Risk: unresolved; omit copyrighted lyric snippets in V1.**

There is no statutory “N words is always safe” rule. A short excerpt could be a
fair use in a particular context, but song lyrics are creative, often compact
works, and even a short refrain may be qualitatively important. A snippet
generated to help users find or consume the song could also affect the same
discovery market served by licensed lyric providers.

If snippets are later required, obtain a song-catalog license or legal review
for the exact snippet algorithm, maximum length, purpose, attribution, caching,
and audience. Do not infer safety from search-engine conventions.

### Authenticated access

**Risk: lower operational exposure, but permission still required.**

Restricting access to invited church administrators is materially different
from publishing to the public and is closer to CCLI's described computer
storage/retrieval for projection. It does not, by itself, expand a license.
The church must verify whether its current agreement and the terms attached to
the source of each lyric allow:

- copying the EasyWorship database into PostgreSQL;
- access by church staff and volunteers outside the EasyWorship software;
- full-text indexing and retrieval for service preparation;
- browser-based Projection Preview;
- remote access away from the licensed church location; and
- retention after a CCLI or SongSelect subscription expires.

Authentication should be treated as a control required by a permission, not as
the source of permission.

### API-key access

**Risk: treat as distribution, not merely authentication.**

An API key identifies a machine client but can still cause copies of lyrics to
be transmitted, stored, or redistributed. V1 API responses should contain only
metadata unless the church obtains terms expressly covering machine access and
downstream use. If lyric-bearing API access is later licensed, scope keys to
approved clients, prohibit onward redistribution, log access, rate-limit
downloads, and make license expiry enforceable.

### Metadata-only access

**Risk: generally lowest and recommended for copyrighted songs.**

Titles and names are not copyrightable as such, and factual fields are
generally outside copyright protection. Public results can therefore be built
around fields such as:

- song title;
- alternate title;
- author/writer names;
- copyright owner and year as factual attribution;
- CCLI song number;
- public-domain/permission status;
- catalog freshness and source record identifiers; and
- links or calls to action that do not expose lyrics.

Avoid copying any provider-authored descriptions, thematic summaries, curated
taxonomy, artwork, or other expressive material without confirming permission.
Do not assume that every field in EasyWorship is a fact merely because it is
called metadata.

Metadata-only **output** is distinct from lyric full-text **indexing**. Building
a PostgreSQL index requires the application to copy the lyric text. The public
interface can remain metadata-only while that backend copy still needs a
license or another legal basis. Without written confirmation, index only
metadata for copyrighted songs.

### Projection Preview

Use a rights-aware policy:

1. **Public domain:** public complete lyrics and public Projection Preview,
   after verifying public-domain status for the exact words/version.
2. **Direct web permission:** public complete lyrics and preview only within
   the permission's song, territory, audience, attribution, and term limits.
3. **CCLI-covered copyrighted song without web-catalog permission:** public
   metadata only. A staff-only preview may be considered only after the church
   confirms that its actual agreement covers the operational use.
4. **Unknown or conflicting rights:** suppress lyrics and preview.

For UI development and visual tuning, use synthetic lyrics written for the
project or verified public-domain material. A “preview” button should not reveal
copyrighted text merely because the same layout resembles EasyWorship.

## Required license and data verification

Before implementation enables any copyrighted lyric display, the church must
collect and verify:

1. **Actual agreements:** the current signed/accepted Church Copyright License,
   SongSelect terms, Streaming License terms if any, and any publisher-specific
   or direct permissions. The public CCLI summary says the master agreement
   controls if they conflict.
2. **Licensed entity and territory:** legal church name, campus/location,
   territory, church-size category, license numbers, effective dates, and
   renewal/termination dates.
3. **Covered repertoire:** whether each song and publisher catalog is covered;
   do not infer coverage solely from presence in an EasyWorship backup.
4. **Lyric provenance:** whether each record came from SongSelect,
   user-entered text, a hymnal, a website, EasyWorship demo data, or another
   source, and the terms attached to that source.
5. **Permitted digital acts:** written confirmation covering PostgreSQL copies,
   full-text indexes, internal browser retrieval, previews, public display,
   snippets, API delivery, backups, and disaster-recovery copies.
6. **Audience and location:** whether permission covers public visitors,
   invited staff/volunteers, remote users, contractors, and machine clients.
7. **Attribution:** the exact title, writers, copyright notice, permission
   wording, CCLI license number, and placement required for every display or
   copy.
8. **Reporting:** which imports, projections, previews, prints, streams, or
   other uses count as reportable copying/activity and how usage must be
   retained.
9. **Expiry and deletion:** what must be disabled or destroyed when a license,
   subscription, song authorization, or direct permission ends.
10. **Public-domain status:** status of the exact lyrical version, including
    later translations, adaptations, or arrangements that may remain
    protected.
11. **EasyWorship terms:** the installed product's actual license agreement,
    including any restrictions on extracting, transforming, or hosting its
    database. EasyWorship's website terms do not establish the rights governing
    a locally installed version and its user-supplied song records.

Ask CCLI or the relevant rights holder the product-specific question in writing:

> Does our current agreement permit us to copy the lyrics stored in our
> EasyWorship database into a PostgreSQL full-text index and expose complete
> lyrics, lyric search snippets, and slide previews (a) publicly on demand,
> (b) to invited church staff, and (c) to authenticated machine clients?

Retain the written answer with the agreement version and effective dates.

## Implementation-ready policy recommendation

Model rights as data rather than a one-time launch assumption:

```text
rights_status:
  public_domain
  direct_permission
  internal_use_confirmed
  metadata_only
  unknown
```

Each imported song should record provenance, the governing permission or
license reference, coverage verification time, permitted audiences, required
attribution, and expiry date. The Catalog Search module should return a
rights-filtered representation; Reactivated and Django-Bolt should not decide
independently whether lyric text is visible.

Recommended V1 interface behavior:

| Surface | Copyrighted, no web permission | Public domain/direct permission |
|---|---|---|
| Public search | Metadata fields only; no lyric indexing or snippet unless internal indexing is confirmed | Metadata; optional lyric snippet |
| Public detail | Metadata and attribution only | Complete lyrics if permitted |
| Public Projection Preview | Hidden | Available if permitted |
| API-key search | Metadata only | Lyrics only if machine distribution is permitted |
| Staff-only operational view | Disabled pending written confirmation | Available within permission |

This keeps a metadata search launchable without betting the product on an
unverified interpretation of church projection rights. Lyric-content search
itself becomes available only where the internal PostgreSQL copy and index are
permitted. The model leaves a clean path to richer access as permissions are
documented song by song or catalog by catalog.
