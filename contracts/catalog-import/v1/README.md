# Catalog Import Package v1

This contract defines the ZIP file that moves song data from the Catalog Exporter
to the Catalog Importer.

## Package files

- `manifest.json` describes the import run, source files, counts, warnings, and
  the checksum for `songs.ndjson`.
- `songs.ndjson` contains one song record on each line.

The JSON schemas in this folder define both files. The Go exporter writes them.
The valid fixtures in `fixtures/valid/` are used by exporter and importer tests.

## Rules

- The manifest and every song record use `contract_version: catalog-import/v1`.
- Add optional fields to keep this version compatible. Make a new version if a
  field is removed, changes meaning, or accepts fewer values.
- `song_uid` is the stable song identity. Do not match songs by title or source
  row ID.
- The manifest checksum covers the exact bytes in `songs.ndjson`. The ZIP file
  can have its own checksum.
- The package includes source evidence and song content. It does not include
  database IDs, search data, rights decisions, or catalog timestamps.

The importer uses semantic fingerprints to detect changes to song metadata,
lyrics, structure, and presentation. Raw RTF is the source record for lyrics.
Slide UID or marker mismatches appear as warnings.
