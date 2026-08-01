# EasyWorship backup corpus profile

## Decision summary

The PostgreSQL Catalog Import should treat `Songs.db` and `SongWords.db` as
the canonical source pair. It should preserve EasyWorship's opaque identifiers,
raw RTF, slide identifiers, and raw revision values before deriving cleaned
lyrics, ordered slides, search documents, and content fingerprints.

`SongKeys.db` is a derived inverted index, not an additional source of song
content. It is not required to build PostgreSQL full-text search. The importer
may use it as an optional diagnostic for source-search coverage, but a missing
or stale `SongKeys.db` should not determine the PostgreSQL Catalog's content.

The strongest observed cross-file relationship is:

```text
Songs.db song.rowid ── 1:1 ── SongWords.db word.song_id
                   └─ 1:0..N ─ SongKeys.db word_key.link_id
```

Do not join `song.rowid` to `word.rowid`; those values coincide for only 188
of 2,283 rows. [S1][S2]

## Sources and safety

This profile used the local EasyWorship backup captured as
`20260705_090643`. Its SQLite files were opened using URI
`mode=ro&immutable=1`; no database was modified. A second capture,
`20260705_090603`, was used only for comparison. All three files in that
capture are byte-for-byte identical to the newer capture, so the corpus
contains one database state rather than two revisions. [S1][S2][S3][S4]

| Source | Role | SHA-256 |
|---|---|---|
| [S1] `20260705_090643/Songs.db` | Song identity and metadata | `b75adb89dbe672335a4883642cd020f23bfd638b0226977ec47db03252457329` |
| [S2] `20260705_090643/SongWords.db` | RTF lyrics and slide metadata | `16f378d098cf106815ec67feab0b269ed623d67e28d6468848f207652f13fd39` |
| [S3] `20260705_090643/SongKeys.db` | EasyWorship token index | `6c3dae26fdf87520ac4e6883f986c061b37f8371afca2b5387e2a44ccc3481c1` |
| [S4] `20260705_090603/*.db` | Earlier capture comparison | Same three hashes as [S1]–[S3] |

The analysis emitted only schema, counts, distributions, hashes, and
structure. It did not copy lyrics, local filesystem locations, song titles,
authors, or opaque identifiers into this note.

## Method

The profile:

1. hashed both capture sets;
2. read `sqlite_master`, `PRAGMA table_info`, index definitions, storage
   classes, database encoding, and integrity metadata;
3. counted nulls, blanks, distinct values, identifier shapes, and duplicate
   groups;
4. compared key sets across databases in memory;
5. scanned RTF for structural control words and escape forms without emitting
   text content;
6. compared slide-marker, slide-UID, and revision-array cardinalities; and
7. tested which source fields contain the indexed terms for each
   `field_flag`, reporting only aggregate match rates.

Representative relationship queries were:

```sql
SELECT rowid, song_item_uid, song_uid, song_rev_uid, title, ...
FROM song NOT INDEXED;

SELECT rowid, song_id, words, slide_uids,
       slide_layout_revisions, slide_revisions
FROM word;

SELECT k.field_flag, k.link_id, w.word
FROM word_key AS k
JOIN word_list AS w ON w.rowid = k.word_list_id;
```

All three databases declare UTF-8 SQLite storage and pass
`PRAGMA quick_check`. `SongKeys.db` also declares a foreign key from
`word_key.word_list_id` to `word_list.rowid`, although foreign-key enforcement
is disabled in the captured connection state. `Songs.db` indexes depend on
EasyWorship's custom `UTF8_U_CI` collation. Because the authentic collation
implementation is not present, a trustworthy full index-level
`integrity_check` of that file cannot be reproduced outside EasyWorship;
registering an approximate collation would test the approximation rather than
the source index. [S1][S2][S3]

## Observed schema and cardinality

### `Songs.db`

`song` has 2,283 rows. `rowid` ranges from 1 to 2,306 with 23 gaps. The schema
contains:

- three identity fields: `song_item_uid`, `song_rev_uid`, and `song_uid`;
- display metadata: `title`, `author`, `copyright`, `administrator`,
  `description`, `tags`, and `reference_number`;
- provider/layout metadata: `provider_id`, `vendor_id`, and
  `presentation_id`; and
- `layout_revision` and `revision`. [S1]

`revision` is a separate table, but contains only one aggregate row for the
`song` table. It is not a per-song history and cannot provide SCD history.
[S1]

### `SongWords.db`

`word` also has 2,283 rows. Every `song_id` is non-null and unique. Every song
has exactly one matching word record and no word record points to a missing
song. Its fields are:

- `words`, stored as RTF text;
- `slide_uids`, stored predominantly as text;
- `slide_layout_revisions`, predominantly an array-like BLOB; and
- `slide_revisions`, predominantly an array-like BLOB. [S2]

### `SongKeys.db`

`word_list` contains 8,068 unique normalized terms and `word_key` contains
89,673 `(song link, term, field flag)` associations covering 2,282 songs.
There are no null links, null term links, missing referenced terms, duplicate
link/term pairs, or links to nonexistent songs. There are, however, 83
unreferenced terms and one otherwise valid song with no key associations.
[S1][S2][S3]

## Identity and duplicate findings

Both `song_uid` and `song_item_uid` are non-null and unique across all 2,283
songs. They are equal on 2,253 songs and differ on 30. `song_rev_uid` is
present and unique on only 189 songs. Most identifiers have the shape of an
integer-prefixed UUID; 231 songs use a different opaque 44-character form.
[S1]

Consequences:

- Preserve all three identifiers verbatim; do not parse their prefixes into
  domain meaning.
- Use `song_uid` as the leading candidate for imported song identity, while
  retaining `song_item_uid` and source `rowid` for traceability.
- Do not claim that any UID is stable across edits or exports yet. Both
  available captures contain the same state, so cross-revision stability was
  not tested.
- Never use title as identity. There are 92 exact duplicate-title groups and
  150 case-folded duplicate-title groups; the largest group contains five
  songs. [S1][S4]

Titles are always present, but their lengths range from 2 to 452 characters
and 67 exceed 100 characters. The importer must not impose a conventional
short-title limit without reviewing these outliers. [S1]

## Metadata completeness

Metadata is sparse in this corpus:

| Field | Populated rows | Notes |
|---|---:|---|
| `title` | 2,283 | Required and nonblank |
| `author` | 223 | Maximum observed length 50 |
| `copyright` | 222 | One nonblank value in this corpus |
| `administrator` | 0 | Blank except one null |
| `description` | 0 | Blank except one null |
| `tags` | 0 | Blank except one null |
| `reference_number` | 0 | Blank except one null |

`provider_id` is limited to `-1` and `0`; `vendor_id` is predominantly `0`
with 182 `1` values and two nulls; `presentation_id` has 287 distinct values
but is `0` on 1,997 rows. These fields should be retained as nullable/raw
source metadata until their semantics are established rather than exposed as
trusted product concepts. [S1]

## RTF, encoding, and slide structure

Every `words` value is non-null text beginning with an RTF header. RTF length
ranges from 75 to 33,567 characters, with a median of 2,358. All documents
declare `\ansi`, but none declares an explicit `\ansicpg`. The corpus includes
373 documents with `\uN` Unicode escapes, six with literal non-ASCII
characters, and none with RTF hex-byte escapes. A parser must implement RTF
Unicode fallback behavior; deleting control words with a single regular
expression is not a safe general conversion. [S2]

EasyWorship-specific structure is common. Hidden `{\* ...}` groups range from
0 to 444 per document (median 27). Frequent controls include
`\sdslidemarker`, `\sdewtemplatestyle`, `\sdewparatemplatestyle`,
`\sdfsreal`, `\sdfsdef`, `\sdfsauto`, and `\sdasfactor`. The importer should
preserve raw RTF even after deriving cleaned text, both for reparsing and for
future preview fidelity. [S2]

`slide_uids` is text on 2,281 rows and null on two. It encodes ordered,
integer-prefixed UUID-like values. Songs have 0–47 slide UIDs (median 4) and
0–46 explicit slide markers (median 2). On 2,090 rows (91.5%), the number of
slide UIDs is exactly one greater than the marker count, consistent with
markers separating slides. The remaining 193 rows include both surplus UID
entries and three large negative mismatches. Therefore:

- preserve the ordered source UID list;
- derive slides from RTF structure;
- validate but do not hard-require `UID count = marker count + 1`; and
- record parse warnings so anomalous songs can be reviewed without aborting a
  whole otherwise valid import. [S2]

`slide_layout_revisions` is a BLOB on 2,074 rows, null on 208, and an empty
text value on one. Its byte length is divisible by eight for every BLOB, and
its inferred 64-bit element count equals the slide-UID count on 2,069 rows.
`slide_revisions` is a BLOB on 2,273 rows, null on eight, and empty text on
two; its element count does not consistently equal either UID or marker
counts. These values are source metadata with unresolved semantics, not safe
inputs to projection behavior yet. [S2]

## Revision and freshness findings

The numeric values in `song.revision`, `song.layout_revision`, and the slide
revision BLOBs strongly resemble packed timestamps: interpreting the high
bits as milliseconds since the .NET epoch produces plausible dates before
the backup. In particular:

- 2,274 of 2,283 `song.revision` values decode into dates from May 2019
  through July 4, 2026; nine rows contain small/default values;
- 1,275 `layout_revision` values decode into dates from May 2019 through
  July 4, 2026; 1,008 rows contain small/default values;
- `revision` is greater than `layout_revision` on 2,275 rows, equal on eight,
  and never lower; and
- the inferred slide-revision timestamps fall within plausible 2016–2026
  ranges. [S1][S2]

This is compelling structural evidence, but not enough to define a timestamp
contract. The packing scheme, timezone, low-bit meaning, and update triggers
are undocumented in the corpus, and identical backups cannot show which value
changes after which EasyWorship edit.

For V1:

- preserve every raw revision value;
- compute a stable Catalog-owned content fingerprint;
- carry `content_changed_at` forward when that fingerprint is unchanged;
- use the successful import's `completed_at` for Catalog Freshness; and
- treat a decoded `source_revision_at` as experimental or omit it from the
  public interface until a controlled changed-backup experiment validates the
  encoding and semantics.

This retains SCD Type 1 behavior without claiming that an inferred source
timestamp is authoritative.

## What `SongKeys.db` contributes

The term list is already normalized: terms are lowercase, contain no spaces
or punctuation, have lengths from 1 to 30, and include 99 terms with
non-ASCII characters. `field_flag` behaves like a bit mask:

- bit `1` corresponds to lyrics;
- bit `2` corresponds to title;
- bit `4` corresponds to author;
- bit `8` corresponds to copyright; and
- observed values `3`, `5`, `7`, and `9` combine those fields.

This inference is supported by aggregate containment: flag `1` terms occur in
raw word content for 97.1% of associations, flag `2` terms occur in titles
for 96.6%, flag `4` terms occur in authors for 100%, flag `8` terms occur in
copyright for 100%, and combined flags occur in the corresponding combined
fields. Differences are expected from RTF, tokenization, normalization, and
substring matching. Flags `64` and `66` occur only 16 times across four songs
and could not be mapped to the available metadata. [S1][S2][S3]

This index is useful evidence about EasyWorship's own searchable fields and
tokenization, but it is unsuitable as the PostgreSQL search source:

- it contains no ordering, frequency, or position data for ranking/snippets;
- it omits one song and retains 83 unused terms;
- its tokens can be regenerated from canonical song fields; and
- PostgreSQL needs its own language configuration, normalization, weighting,
  and positional document representation.

The import should therefore exclude `word_list` and `word_key` from Catalog
tables. A diagnostic mode may compare PostgreSQL-token coverage with
`SongKeys.db`, especially for multilingual and non-ASCII cases.

## Collation implications

Several `Songs.db` text columns use EasyWorship's custom `UTF8_U_CI`
collation. Its implementation and precise case/accent behavior are not stored
in SQLite. PostgreSQL cannot promise sorting or equality parity from the name
alone. [S1]

The Catalog should:

- preserve source strings verbatim;
- define explicit normalized search fields separately;
- choose and test PostgreSQL collation, case folding, accent handling, and
  full-text configuration deliberately; and
- include multilingual, diacritic, apostrophe, punctuation, and duplicate
  title fixtures before declaring search parity.

## Required import preservation and invariants

### Preserve verbatim

- source capture identifier and file hashes;
- `song.rowid` for traceability;
- `song_item_uid`, `song_uid`, and `song_rev_uid`;
- title and all optional metadata fields, including unknown numeric fields;
- raw `revision` and `layout_revision`;
- raw RTF `words`;
- ordered `slide_uids`;
- raw `slide_layout_revisions` and `slide_revisions`.

### Derive under Catalog ownership

- normalized title and metadata;
- cleaned plain lyrics;
- ordered parsed slides and parse warnings;
- weighted PostgreSQL search document;
- stable content fingerprint;
- `content_changed_at`, carried forward when the fingerprint is unchanged;
- Catalog Import status, counts, hashes, warnings, and `completed_at`.

### Validate before atomic promotion

1. Both canonical databases are readable SQLite files from the same capture.
2. File hashes are recorded before extraction.
3. `song_uid` and `song_item_uid` are non-null and unique.
4. Titles and RTF are non-null and nonblank.
5. `song.rowid` and `word.song_id` form a complete one-to-one relationship.
6. Every RTF document parses to a deterministic result; structural anomalies
   become warnings unless content is unusable.
7. Derived content fingerprints and search documents are present.
8. Counts and warning thresholds pass before the staged Catalog replaces the
   active version.

`SongKeys.db` presence or parity should be a diagnostic, not a promotion
requirement.

## Unknowns requiring follow-up

The corpus cannot answer:

- whether `song_uid`, `song_item_uid`, or source `rowid` remains stable after
  edits, deletions, reimports, or EasyWorship backup/restore;
- the exact opaque 44-character identifier semantics;
- the revision packing algorithm, timezone, low bits, and which edits update
  each revision field;
- the meaning of `song_rev_uid`, provider/vendor/presentation identifiers,
  slide revision arrays, and `field_flag` bit `64`;
- EasyWorship's actual `UTF8_U_CI` comparison rules;
- whether the 193 slide-cardinality anomalies are intentional layout states,
  legacy formats, or damaged metadata;
- which RTF formatting must survive for a near-pixel preview; and
- deletion/change behavior, because the two available captures are identical.

The most valuable next evidence is a controlled Windows experiment: capture a
backup, make one isolated edit at a time (title, lyric text, slide break,
formatting, metadata, delete), then capture again. That experiment should
compare identifiers, raw revisions, RTF, slide arrays, and `SongKeys.db`
without writing directly to any database.
