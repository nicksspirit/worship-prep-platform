# Catalog Import Package v1

`catalog-import/v1` is the storage-neutral boundary between the Catalog Exporter
and Catalog Importer. A package is a ZIP archive containing exactly:

- `manifest.json`: run identity, versions, source file evidence, diagnostics,
  counts, warnings, and the `songs.ndjson` checksum.
- `songs.ndjson`: one complete `SongRecord` JSON object per physical line.

The schemas in this directory are authoritative for shape. The Go types under
`exporter/internal/contract` are the emitting implementation. The redacted
`fixtures/valid` files are shared behavioral fixtures for both Go exporter tests
and the Django Catalog Importer introduced in slice 3.

## Compatibility

- `contract_version` is exactly `catalog-import/v1` in the manifest and every
  song record.
- Compatible additions require a new optional field. Removing a field, changing
  its meaning, or tightening accepted data requires a new contract version.
- `parser_version` and `semantic_fingerprint.version` change independently when
  their algorithms change.
- The package remains PostgreSQL-neutral. Search documents, catalog timestamps,
  and database identifiers are not package fields.

## Integrity and identity

- `run_id` is generated before source acquisition and identifies the complete
  Catalog Import attempt across retries.
- `song_uid` is the only stable catalog identity. Titles and source row IDs must
  never be used to merge songs.
- Every source database is hashed while it is copied. The source fingerprint is
  the SHA-256 of the ordered file evidence.
- `records.sha256` authenticates the exact `songs.ndjson` bytes. The same value is
  the V1 package-content fingerprint; the ZIP file itself may have a separate
  transport checksum.
- Semantic fingerprints are componentized so the importer can distinguish
  metadata, lyric, structure, and presentation changes without trusting opaque
  EasyWorship revision values.

## Source evidence and diagnostics

Raw RTF, opaque IDs, revisions, ordered slide UIDs, revision arrays, and selected
source metadata remain in the private package. SQLite values use a tagged
`SourceValue`; BLOB values are base64 encoded. `SongKeys.db` is optional and
contributes diagnostics only.

Recognized numbered labels normalize to a common label without source numbering.
Unknown, blank, misspelled, or custom labels remain exact. The raw RTF is the
authoritative source evidence. Slide UID/marker mismatches are warnings because
the profiled EasyWorship Library contains usable structural anomalies.
