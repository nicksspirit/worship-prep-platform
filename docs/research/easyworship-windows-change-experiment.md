# Windows EasyWorship change experiment

## Status and decision

Complete on 2026-07-31 Pacific time for [Issue 19: Validate Windows
EasyWorship change behavior](https://github.com/nicksspirit/worship-prep-platform/issues/19).

The experiment supports the existing decision to import `Songs.db` and
`SongWords.db` as the canonical source pair and to treat `SongKeys.db` as an
optional diagnostic. The Catalog Exporter should preserve source identifiers,
metadata, raw RTF, ordered slide UIDs, and raw revision arrays as evidence, but
it should use a Catalog-owned semantic content fingerprintâ€”not EasyWorship
revision numbers, database file checksums, or `SongKeys.db` rowsâ€”to determine
Song Freshness.

The tested song's `Songs.rowid`, `song_uid`, `song_item_uid`, `SongWords.song_id`,
and both slide UIDs survived every edit. Deletion removed the song and word rows
and all `word_key` associations without leaving a tombstone; the global
`word_list` vocabulary remained. All tested saves changed both per-song numeric
revision fields and the slide-revision arrays, including title and author edits
that left RTF and slide structure unchanged. These revisions are generic source
change evidence, not reliable field-level change detectors.

This report refines rather than repeats the decisions in the
[backup corpus profile](https://github.com/nicksspirit/worship-prep-platform/issues/14),
[Catalog Import mechanism](https://github.com/nicksspirit/worship-prep-platform/issues/8),
[PostgreSQL FTS ADR decision](https://github.com/nicksspirit/worship-prep-platform/issues/5),
[lyrics rights/provenance policy](https://github.com/nicksspirit/worship-prep-platform/issues/17),
and [release and acceptance gates](https://github.com/nicksspirit/worship-prep-platform/issues/6).
The experiment did not introduce section labels, so the existing
`docs/research/easyworship-lyric-section-labels.md` research remains
authoritative for hidden-label parsing.

## Environment and reproducibility

| Condition | Value |
|---|---|
| EasyWorship | Product 8.0; executable file version `8.0.49.0` |
| Windows | Registry-reported `Windows 10 Home`, display version `25H2`, build `26200.8894`, AMD64 |
| Time zone | Pacific Standard Time |
| Disposable profile | `Catalog Experiment`; profile ID `1-28837E3E-44D1-4808-B3B6-FA340D371E13` |
| Profile root | `C:\Users\Public\Documents\Softouch\Easyworship\Catalog Experiment\` |
| Database root | `...\v6.1\Databases\Data\` |
| Operator split | Human operator made and saved each EasyWorship UI change; the agent copied and inspected databases only after full exit |
| Source handling | No direct database writes; no production profile edits; synthetic lyrics only |

The Windows product name above is reported verbatim from
`HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion`. The `25H2` display
version and build are more specific than that legacy product-name string.

The profile was verified pristine before song creation: zero `song`, `word`,
`word_key`, and `word_list` rows. A non-committed copy of each of `Songs.db`,
`SongWords.db`, and `SongKeys.db` was taken after each full EasyWorship exit.
Every comparison uses the immediately preceding capture. `SongWords.db` and
`SongKeys.db` passed `PRAGMA quick_check` in every capture. `Songs.db`
`quick_check` cannot be authenticated outside EasyWorship because its indexes
require the proprietary `UTF8_U_CI` collation; registering an approximation
would test the approximation rather than the source. All source rows remained
readable, and the required `Songs.song.rowid = SongWords.word.song_id` key-set
join was exact in every populated capture and empty on both sides after
deletion. The tables were never joined by their respective row IDs.

The test song used deliberately synthetic, non-corpus text:

```text
WPP Experiment Alpha

Copper lanterns wake
Across the quiet room

Silver footsteps answer
```

Baseline identity and structure:

- `Songs.rowid` / `SongWords.song_id`: `1`
- `song_uid` and `song_item_uid`:
  `1-AD4F3213-2E1A-4B0C-919C-6455936AED3B`
- `song_rev_uid`: null throughout
- slide UIDs, in order:
  `1-551F0800-0FB4-49ED-8DAE-65F3BE12DA8F`,
  `1-B70B62D7-818F-4B86-AEA3-B0D24E36389C`
- two slides represented by one `\sdslidemarker`

## Compact before/after results

| Isolated stage | Rows and opaque identity | Revisions | RTF, normalized lyrics, and slides | `SongKeys.db` | Exporter consequence |
|---|---|---|---|---|---|
| Title: `Alpha` â†’ `Beta` | Same song/word rows and all song/slide UIDs | Both song revisions changed; global revision `2â†’4`; slide arrays changed | Raw RTF, normalized lyrics, marker, and UIDs unchanged | Added `beta`; `alpha` became unreferenced | Fingerprint title; do not infer lyric/slide changes from revisions |
| Lyrics: `wake` â†’ `glow` | Same rows and UIDs | Both song revisions changed; global `4â†’6`; slide arrays changed | RTF and normalized lyrics changed; marker and UIDs unchanged | Added `glow`; `wake` became unreferenced | Fingerprint normalized lyrics separately from structure/formatting |
| Slide break moved | Same rows and UIDs | Both song revisions changed; global `6â†’8`; both slide entries changed | RTF marker moved; normalized lyrics unchanged; 1 marker/2 UIDs retained | Logical rows unchanged although file checksum changed | Include ordered slide boundaries; database checksum is not a content fingerprint |
| Formatting | Same rows and UIDs; `presentation_id 0â†’1` | Both song revisions changed; global `8â†’10`; slide arrays changed | First slide `\fs146â†’\fs150`; text, marker, and UIDs unchanged; no RTF `\b` observed | Logical rows unchanged although file checksum changed | Preserve raw RTF and `presentation_id`; warn on unresolved presentation/style evidence |
| Author: blank â†’ `WPP Experiment Author` | Same rows and UIDs | Both song revisions changed; global `10â†’12`; slide arrays changed | RTF, normalized lyrics, marker, and UIDs unchanged | Added author terms using bit `4`; title+author overlaps became bit `6` | Include source metadata in fingerprint according to product semantics; derive search independently |
| Deletion | Removed `song rowid=1` and joined `word song_id=1`; all opaque song/slide IDs disappeared | No remaining per-song revisions; global `12â†’13` | Entire word/RTF/slide row removed | Removed 14 links but retained all 16 vocabulary rows | Detect deletion by identity absence between complete snapshots; no source tombstone exists |

## Detailed findings

### Identity, joins, and deletion

`song_uid`, `song_item_uid`, source `rowid`, `SongWords.song_id`, and the two
ordered slide UIDs were stable across title, lyric, slide-boundary, formatting,
and author changes. This is strong evidence for preserving them verbatim and
for using `song_uid` as the leading source identity candidate. It is not proof
of stability across backup/restore, import/export, UID collision repair, or
multiple EasyWorship versions; only one newly created song in one profile was
tested.

Deletion physically removed the canonical song and word rows. It also removed
every `word_key` link for `link_id=1`, while retaining all dictionary terms,
including superseded `alpha` and `wake`. There was no deleted-song row,
tombstone, deletion timestamp, or recoverable opaque ID in the three tested
databases. A complete Catalog Import must therefore interpret a previously
known `song_uid` missing from a successfully validated complete snapshot as a
deletion. It must not infer deletion from `word_list` vocabulary.

### Revision behavior

The aggregate `Songs.revision.revision_num` advanced by two for every saved
edit and by one for deletion. Both `song.layout_revision` and `song.revision`
changed on every edit category. The BLOBs `slide_layout_revisions` and
`slide_revisions` also changed on every edit, even when raw RTF, normalized
lyrics, slide boundaries, and slide UIDs were unchanged. Some edits changed
both slide-revision elements; others changed one layout element while changing
both slide-revision elements.

Consequences:

- Preserve the exact raw values for diagnostics and change corroboration.
- Do not use them to classify title versus lyrics versus layout changes.
- Do not expose them as timestamps or use them as authoritative freshness.
- Do not assume that an unchanged slide revision means an unchanged song, or
  that a changed slide revision means slide content changed.
- A monotonic increase was observed, but no no-op save, clock change, restore,
  concurrent edit, or wraparound was tested. No timestamp semantics are
  inferred from this run.

### RTF, normalized lyrics, slide markers, and formatting

Raw RTF differentiated the content categories more accurately than the
revision fields:

- title and author edits left RTF byte-identical;
- lyric text changed RTF and normalized lyrics;
- moving the break changed marker placement while normalized lyrics stayed
  identical;
- formatting changed RTF font-size controls while normalized lyrics and marker
  placement stayed identical.

The slide-break edit preserved both ordered slide UIDs despite moving one line
from slide 1 to slide 2. Therefore, UIDs cannot replace parsing the RTF marker
locations: both must be preserved and validated.

The operator intentionally applied bold and increased the first slide's font
size in one formatting-stage transaction. The stored RTF unambiguously changed
the first slide from `\fs146` (about 72.9 pt) to `\fs150` (about 74.9 pt), and
`presentation_id` changed from `0` to `1`. No `\b` control appeared in the
stored `SongWords.words` RTF. The three captured databases therefore do not
show where the intended bold state lives or whether EasyWorship persisted it.
Because two formatting attributes were applied together, their individual
effects on `presentation_id` and revisions cannot be separated. Font-size
preservation is conclusive; bold preservation is inconclusive. The Exporter
should retain `presentation_id` as opaque evidence and issue an
`unresolved_presentation_reference`-style diagnostic when presentation styling
cannot be reconstructed from the canonical pair. A separate follow-up should
locate the referenced presentation/theme data before promising high-fidelity
bold or theme reconstruction.

### `SongKeys.db`

The experiment confirms the corpus-profile interpretation of `field_flag` as
a bitmask:

- `1`: lyrics
- `2`: title
- `4`: author
- `6`: title + author for a term present in both

The title and lyric edits added new dictionary terms but did not delete the
old terms. The author edit added `author` and combined overlapping `wpp` and
`experiment` terms under flag `6`. Slide and formatting edits caused the
physical `SongKeys.db` checksum to change even though the final logical
`word_key` and `word_list` rows were identical. Deletion removed associations
but retained the full vocabulary.

This makes `SongKeys.db` useful for warnings such as missing-song coverage,
unexpected field-bit coverage, or tokenizer differences. It remains unsuitable
as a Catalog table source or a content-fingerprint input: it is derived,
retains orphans, rewrites row positions, and can change physically without a
logical search change. PostgreSQL title and lyrics documents must be derived
from canonical source fields under the accepted explicit `simple` + `unaccent`
configuration and rights-aware policy. EasyWorship's author bit does not add
author search to the accepted V1 title/lyrics search contract.

## Exporter package and manifest result

No Catalog Exporter executable or `exporter/` implementation was present in
the Windows workspace or the repository code available for this run. The
resolved design in Issue 8 describes a future pure-Go exporter; it is not yet
an executable artifact. Consequently, no authentic Catalog Export Package,
versioned manifest, exporter run ID, parser version, package fingerprint, or
exporter diagnostics could be produced. This is an explicit inconclusive part
of the experiment, not a simulated package result.

The capture SHA-256 manifest below supplies reproducible local evidence but is
not a substitute for the future exporter manifest. The release gate in Issue 6
should rerun these fixtures through the implemented exporter and assert the
expected package-level deltas, including `skipped_source_in_use` while
EasyWorship is running.

## Exporter and importer implications

### Preserve

For every song record, preserve verbatim:

- source capture/run identity and canonical database hashes;
- source `Songs.rowid` for traceability;
- `song_uid`, `song_item_uid`, and nullable `song_rev_uid`;
- title and every supplied metadata field, including opaque numeric fields
  such as `presentation_id`;
- raw `revision` and `layout_revision`;
- raw RTF;
- ordered slide UIDs;
- raw slide-layout and slide-revision arrays.

Preservation does not make every field a Catalog domain field. It keeps the
evidence necessary to diagnose parser behavior, identity conflicts, future
formatting work, and source anomalies.

### Content fingerprinting

Compute a versioned Catalog-owned semantic fingerprint from deterministic,
typed components:

1. exact/normalized title and product-relevant metadata;
2. normalized lyrics;
3. ordered parsed sections and slide boundaries;
4. canonicalized presentation-relevant formatting derived from RTF; and
5. any resolved presentation reference that the V1 preview actually consumes.

Keep component hashes so an import can classify metadata, lyric, structure,
and formatting deltas. Keep a separate source-evidence/package hash for exact
raw RTF and opaque revision values. Exclude whole SQLite file bytes,
`Songs.revision.revision_num`, per-song/slide revisions, `SongKeys.db` rows,
and dictionary row IDs from the semantic fingerprint. Those inputs changed
without corresponding semantic changes or were intentionally derived.

Carry `content_changed_at` forward only when the versioned semantic fingerprint
is unchanged, as already decided by Issue 14. A fingerprint-algorithm version
change requires an explicit migration/reconciliation rule rather than making
every song appear newly changed.

### Import diagnostics and warnings

Add or retain diagnostics for:

- missing/duplicate opaque identity;
- incomplete `Songs.rowid â†’ SongWords.song_id` joins;
- RTF parse failure or normalization loss;
- slide marker/UID/revision-array cardinality anomalies;
- a changed slide UID set with unchanged parsed structure, or unchanged UIDs
  with changed structure (observed here and valid, but diagnostically useful);
- unresolved `presentation_id` or formatting evidence;
- revision changes with no semantic component change;
- `SongKeys.db` missing-song coverage, stale/orphan terms, unknown flag bits,
  or mismatches against derived title/lyrics tokens; and
- disappearance of a previously imported `song_uid` from an otherwise valid
  complete snapshot.

Usable structural or diagnostic anomalies should warn rather than fail the
whole import. Identity conflicts, an unusable canonical pair, or an incomplete
snapshot remain fatal before atomic promotion.

### Search derivation and rights

Derive PostgreSQL title and lyrics documents from the preserved canonical
fields, not from `SongKeys.db`. Keep them separate so selected-field search and
rights filtering cannot cross-match. The experiment did not test multilingual
normalization, section labels, rights evidence, or restricted-content behavior.
Per Issue 17, source author/copyright contents and EasyWorship index flags do
not establish web-display rights; imported songs still default to `unknown`
unless the package carries qualifying provenance evidence.

## Unresolved questions and limitations

- One EasyWorship version, one new song, one profile, and one save sequence
  were tested. Reproduce on the implementation's supported EW7/EW8 range.
- No no-op save was captured, so revision-only churn after an unchanged save
  remains unknown.
- The formatting stage combined bold and font-size changes. Font size is
  visible in RTF; bold is not, and its storage remains unresolved.
- No section label, custom label, copyright, tag, administrator, description,
  or reference-number edit was tested.
- No reorder, slide insertion/deletion, song import/export, backup/restore,
  UID collision, or delete-and-recreate cycle was tested.
- `Songs.db` index integrity cannot be authenticated without EasyWorship's
  real `UTF8_U_CI` collation.
- The Catalog Exporter was not implemented, so package/manifest deltas and
  diagnostics remain future acceptance tests.

## Recommended decision for Issue 19

Close Issue 19 with the following decision:

1. Preserve all previously selected canonical source evidence, including
   opaque revisions and `presentation_id`, but treat it as diagnostic evidence.
2. Use stable source identity plus a versioned, componentized Catalog semantic
   fingerprint for change classification and Song Freshness.
3. Parse raw RTF into independent normalized-lyrics, slide-structure, and
   canonical-formatting components; preserve ordered slide UIDs alongside,
   not instead of, marker-derived structure.
4. Treat deletion as identity absence from a validated complete snapshot; do
   not expect tombstones and do not use the persistent `word_list` vocabulary.
5. Keep `SongKeys.db` optional and diagnostic-only, with field flags interpreted
   as bitmasks and PostgreSQL search documents derived independently.
6. Carry the unresolved presentation/bold question and authentic exporter
   package behavior into implementation acceptance tests rather than blocking
   the planning sequence.

## Non-committed evidence manifest

Raw database copies remain local under `.tmp/issue-19-artifacts/` and must not
be committed. Artifact IDs are safe report references. Hash order in the final
column is `Songs.db`, `SongWords.db`, `SongKeys.db`.

| Artifact ID | Relative local path | State | SHA-256 triplet |
|---|---|---|---|
| `EWX19-00` | `.tmp/issue-19-artifacts/00-pristine/` | Empty profile | `fa56851f0c4228f159a1d050de965af4e41169ce6e11737c8854a2626c2273fd`; `f29e55b937171b7740799a354fcfb061d080e1aa12ca61e8347a0f97547bca0b`; `06fbfbb040e9dc231c39d2b59346a01f83ae81bca5a76401d9827307f9166545` |
| `EWX19-01` | `.tmp/issue-19-artifacts/01-baseline/` | Baseline song | `d0c881c59561031bf4e53e231992a82ffb16ac9e88cd044e35a5f9efe147690e`; `ff48fd4102b5f4eb9853da7b85e09cd0f286b1a449a065ce3698ce1f001a1b71`; `15573005f78c026148e7ef01a299eb8278734a8e0155ec00a75daad8e8f61672` |
| `EWX19-02` | `.tmp/issue-19-artifacts/02-title/` | Title | `1df530ff43590429f8c80319ad528b43f4d889a8b0ab4195a2a8bd10a25d51a4`; `71022fa534bad9ab1f65091a08bc7b1555bc589f783cb48f3027994ba87e93c0`; `d32326202d33c688a64e2fbaf0ae444e949656e256c6280262195aff9c5e0b62` |
| `EWX19-03` | `.tmp/issue-19-artifacts/03-lyrics/` | Lyrics | `a6fa2a5c99a2ad9a968bdd3a45ec63b483e2255e659f98d0159248e9d628a1d2`; `210d64dc3bd474c8daca122090d0d8ac00976a3f30be7b4dfb41a0bc6cf47710`; `ea1b528d434fc4efb667bbd0f8ee3c858cf3978bddbc75515714d58506cc237f` |
| `EWX19-04` | `.tmp/issue-19-artifacts/04-slide-break/` | Slide break | `0ff3f1e3b47c94d6ca1ece5fc4ade14beb5003225f2c3ac8a4e6f44943f026e7`; `237557afe588e8d2e556d8ff3efbd02ed64df1cfd3dfadda84cf3bc14a8bce2b`; `ba224afe3bca4b6826d1e437bfd993a9d166b5713f7d7f9085f57c91d2d78052` |
| `EWX19-05` | `.tmp/issue-19-artifacts/05-formatting/` | Formatting | `e09977c9dce4d5ed4106439a8cb033c4b24ff90f0f6a9e12ba3f4ebae6e46323`; `2b02e9dfa87654f6d00095fb22aba07d62f4c7375708c9a137df6dbbfcb3dc26`; `0c682d07014ddcc93820fc2537d1b9518f43b82720340ec441a28449bfac920c` |
| `EWX19-06` | `.tmp/issue-19-artifacts/06-metadata-author/` | Author metadata | `763b8bef8d99e82a02ad15bfac72688b28defa04633d92ef3da2f6329798b3c9`; `a80572142fa2abb70091e720100e5ba86749e70ad06a11d42c201f0e5da3246d`; `42550964434e976832759de5bac8495cf91239c80533d85607e93d7dc3beb230` |
| `EWX19-07` | `.tmp/issue-19-artifacts/07-deletion/` | Deleted/empty | `c9b3f22d977a7d7501929aaf5ff43dc5d38d21e6dbcb359c91d81379a1cd3352`; `41c1e67692f48387d845c6a2ee9ec7c99a64d38ec23484ae2dfecfd1185ec912`; `f034e95bf39a5400b83172c753215f518cb086c6ac81116add0483b0a8218281` |

