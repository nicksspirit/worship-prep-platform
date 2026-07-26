# PostgreSQL search primitives for the Song Catalog

Research date: 2026-07-26

## Decision

V1 should use PostgreSQL full-text search as its primary retrieval path:

- One stored generated `tsvector` column containing title lexemes at weight `A`
  and cleaned-lyrics lexemes at weight `D`.
- One GIN index on that column.
- One explicit, project-owned text-search configuration copied from `simple` and
  extended with the `unaccent` filtering dictionary.
- `websearch_to_tsquery` for public input, with an explicit query-length limit and
  rejection of empty or non-indexable queries.
- `ts_rank_cd` for the first ranking baseline, ordered deterministically by rank,
  normalized title, and stable song identifier.
- `ts_headline` only after the result page has been bounded, with output treated as
  untrusted markup.
- A separately normalized title column with a `pg_trgm` index as a title-only
  fallback for incomplete or misspelled input. It should not fuzzy-search lyrics
  or be blended into the primary rank until corpus evaluation establishes useful
  thresholds.

This keeps the Catalog Search module's interface small: callers supply a query and
page cursor; the implementation owns parsing, retrieval strategy, ranking,
highlighting, and stable pagination.

## Why this is the V1 shape

### Store one weighted search document

PostgreSQL supports assigning `A` through `D` weights to different document
sections and concatenating their vectors. Its own structured-document example
uses this mechanism to distinguish title-like fields from body text, and it
recommends `coalesce` for nullable fields. The default ranking weights are
`D=0.1`, `C=0.2`, `B=0.4`, and `A=1.0`.
([PostgreSQL: parsing documents and ranking](https://www.postgresql.org/docs/16/textsearch-controls.html))

The conceptual expression is:

```sql
setweight(to_tsvector('song_catalog', coalesce(title, '')), 'A')
||
setweight(to_tsvector('song_catalog', coalesce(cleaned_lyrics, '')), 'D')
```

Use a stored generated column rather than only a functional index. PostgreSQL
documents both approaches, but specifically shows a stored generated `tsvector`
plus GIN as the automatically maintained alternative. A generated value is
recomputed on row writes and cannot be independently overwritten, preventing the
stored vector from drifting from title or lyrics.
([PostgreSQL: text-search tables and indexes](https://www.postgresql.org/docs/16/textsearch-tables.html),
[PostgreSQL: generated columns](https://www.postgresql.org/docs/16/ddl-generated-columns.html))

This choice also helps ranking: a GIN full-text index stores lexemes but not their
weight labels, so weighted queries require a table-row recheck. Keeping the
vector as a column avoids rebuilding the title-plus-lyrics expression for every
matched row.
([PostgreSQL: preferred text-search indexes](https://www.postgresql.org/docs/16/textsearch-indexes.html))

The Django representation can use `SearchVectorField` as the generated column's
output type and a `GinIndex` on the field. Django 5.2 exposes `SearchVector`,
weighted vector composition, `SearchRank`, and `SearchHeadline`; its documentation
also notes that a functional GIN index must match the queried vector.
([Django 5.2: PostgreSQL full-text search](https://docs.djangoproject.com/en/5.2/ref/contrib/postgres/search/))

An implementation spike should verify that the exact `GeneratedField` expression
serializes cleanly in this project's Django migration. If it does not, use a
small `RunSQL` migration for the generated column rather than replacing generated
maintenance with application callbacks or signals.

### Prefer GIN

PostgreSQL calls GIN the preferred full-text index type. It is an inverted index
with one entry per lexeme and compressed posting lists of matching rows; GiST
text-search indexes are lossy and require false-match rechecks.
([PostgreSQL: preferred text-search indexes](https://www.postgresql.org/docs/16/textsearch-indexes.html))

V1 therefore needs:

```sql
CREATE INDEX catalog_song_search_vector_gin
ON catalog_song
USING GIN (search_vector);
```

Do not create separate title and lyrics full-text indexes initially. One weighted
vector lets one indexed match cover both fields and leaves their relative
importance in the ranking implementation.

### Parse public input with `websearch_to_tsquery`

`websearch_to_tsquery` accepts unformatted user input, supports quoted phrases,
`OR`, and `-` negation, ignores other punctuation, and is documented never to
raise a syntax error. `plainto_tsquery` is also forgiving but always combines
surviving terms with `AND`. Raw `to_tsquery` accepts more operators and prefix
labels but raises syntax errors for malformed input.
([PostgreSQL: parsing queries](https://www.postgresql.org/docs/16/textsearch-controls.html))

Use Django's:

```python
SearchQuery(user_query, config="song_catalog", search_type="websearch")
```

The ORM or bound parameters are still required; "never raises syntax errors" is
not a substitute for normal SQL-injection protection. Do not pass public text to
`search_type="raw"`.

Apply product limits before constructing the query (a proposed starting point is
200 Unicode code points, at most 20 parsed terms, and a page size no greater than
50). Also reject a query with no searchable nodes or no indexable positive
portion. PostgreSQL provides `numnode()` to detect empty/stop-word-only queries
and `querytree()` to identify portions usable with an index.
([PostgreSQL: manipulating queries](https://www.postgresql.org/docs/16/textsearch-features.html))

### Rank with cover density first, then test it

`ts_rank` ranks primarily by matching-lexeme frequency. `ts_rank_cd` also
considers proximity and requires positional information; the proposed generated
vector retains positions. Django selects it with `SearchRank(...,
cover_density=True)`.
([PostgreSQL: ranking search results](https://www.postgresql.org/docs/16/textsearch-controls.html),
[Django 5.2: `SearchRank`](https://docs.djangoproject.com/en/5.2/ref/contrib/postgres/search/#searchrank))

Start with `ts_rank_cd` because queries containing lyric phrases should benefit
from nearby terms. Do not present rank as a percentage. PostgreSQL states that
its ranking functions have no global collection information; normalization flag
32 only maps the score to zero-to-one and does not change ordering.
([PostgreSQL: ranking search results](https://www.postgresql.org/docs/16/textsearch-controls.html))

The complete ordering must be unique:

```text
rank descending, normalized_title ascending, source_song_id ascending
```

PostgreSQL warns that `LIMIT`/`OFFSET` without a unique ordering can return
unpredictable subsets, and that large offsets still compute skipped rows.
([PostgreSQL: LIMIT and OFFSET](https://www.postgresql.org/docs/16/queries-limit.html))

Prefer cursor pagination containing the catalog version, query fingerprint, rank,
normalized title, and stable source song ID. Including the catalog version
prevents a cursor created against one full replacement from silently continuing
through another. Offset pagination is acceptable for an initial bounded UI, but
the external endpoint should expose a cursor-shaped contract so the
implementation can remain stable.

### Generate snippets only for the bounded page

`ts_headline` can select fragments and wrap matching terms, but PostgreSQL warns
that:

- its output is not safe for direct inclusion in a web page;
- it can highlight query words even when their positions do not satisfy all query
  restrictions; and
- it reads the original document rather than the `tsvector`, so it can be slow.

([PostgreSQL: highlighting results](https://www.postgresql.org/docs/16/textsearch-controls.html))

Use a two-step query if needed: retrieve and rank the page of IDs first, then run
`SearchHeadline` only for those rows. Use inert delimiter tokens rather than
trusting generated HTML, escape the returned text, and let React render explicit
highlight elements. Cleaned EasyWorship lyrics should still be treated as
untrusted input.

## Case, accents, and French-English content

The `simple` dictionary lowercases tokens. PostgreSQL dictionaries normalize
different word forms into lexemes, while language-specific Snowball dictionaries
also stem and remove language-specific stop words.
([PostgreSQL: dictionaries](https://www.postgresql.org/docs/16/textsearch-dictionaries.html))

The `unaccent` extension supplies a filtering dictionary that removes diacritics
and passes its output to the next dictionary. PostgreSQL shows it placed before a
French stemmer so `Hôtel` and `Hotels` match.
([PostgreSQL: `unaccent`](https://www.postgresql.org/docs/16/unaccent.html))

For V1, define a project-owned configuration such as `song_catalog` by copying
`simple` and placing `unaccent` before `simple` for word token mappings. This
gives:

- case-insensitive lexeme matching;
- accent-insensitive matching (`grâce` and `grace`);
- the same predictable normalization for English, French, and mixed-language
  lyrics;
- no incorrect assumption that each song has exactly one language.

Always name `song_catalog` explicitly in both vector and query construction.
PostgreSQL requires the query expression to use the same explicit configuration
as the indexed expression, and warns that relying on
`default_text_search_config` can make index contents inconsistent.
([PostgreSQL: creating text-search indexes](https://www.postgresql.org/docs/16/textsearch-tables.html))

This intentionally postpones stemming. English stemming can improve matches such
as singular/plural variants but is not a neutral choice for French or bilingual
songs. PostgreSQL can index a configuration stored per row, and Django can use a
field expression as the vector/query configuration, so per-language
configurations remain a supported future design.
([PostgreSQL: per-row configurations](https://www.postgresql.org/docs/16/textsearch-tables.html),
[Django 5.2: changing search configuration](https://docs.djangoproject.com/en/5.2/ref/contrib/postgres/search/#changing-the-search-configuration))

Do not add per-row English/French stemming until the imported corpus provides
reliable language metadata and relevance tests show it beats the shared
accent-insensitive configuration.

## Prefixes and typo tolerance

Full-text prefix matching exists through the `:*` label accepted by
`to_tsquery`, but neither `plainto_tsquery` nor `websearch_to_tsquery` recognizes
prefix labels in public input.
([PostgreSQL: text-search types](https://www.postgresql.org/docs/16/datatype-textsearch.html),
[PostgreSQL: parsing queries](https://www.postgresql.org/docs/16/textsearch-controls.html))

Do not construct raw `to_tsquery` syntax by appending `:*` to user text in V1.
Correctly tokenizing, normalizing, quoting, and combining arbitrary public input
would create a second query language and weaken the chosen safe-input behavior.

Use `pg_trgm` only on a canonical `normalized_title` column for:

- incomplete title input such as `amazi`;
- minor title misspellings;
- optional title autocomplete.

`pg_trgm` provides case-insensitive similarity operators and GIN/GiST operator
classes. GiST supports efficient nearest-neighbor ordering with distance and
`LIMIT`, while both GiST and GIN support threshold similarity searches.
([PostgreSQL: `pg_trgm`](https://www.postgresql.org/docs/16/pgtrgm.html))

For the V1 fallback, a GiST trigram index is the better starting shape because
the operation is "give me the nearest few titles" rather than "retrieve every
title over a settled threshold":

```sql
CREATE INDEX catalog_song_normalized_title_trgm
ON catalog_song
USING GIST (normalized_title gist_trgm_ops);
```

Populate `normalized_title` during the import with the same case and accent
normalization policy. This makes the indexed value explicit and testable.
Django exposes trigram similarity and distance expressions and can install the
`pg_trgm` and `unaccent` extensions through migration operations.
([Django 5.2: trigram similarity](https://docs.djangoproject.com/en/5.2/ref/contrib/postgres/search/#trigram-similarity),
[Django 5.2: PostgreSQL extension operations](https://docs.djangoproject.com/en/5.2/ref/contrib/postgres/operations/))

Keep this as a fallback when full-text search returns no useful match, or as a
separate suggestion lane. Do not fuzzy-match the full lyrics: repeated lines and
long documents make character similarity difficult to explain, and the product
need is title recovery. Do not blend trigram and full-text scores until a labeled
corpus can establish a meaningful formula.

## Atomic full replacement and index operations

The search design must not publish rows before their generated vectors and
indexes are usable. The Catalog Import should load and validate a non-active
catalog version, make it query-ready, run `ANALYZE`, and only then atomically
change the active-version pointer. Search requests must constrain every query to
the active version.

For a modest EasyWorship catalog, inserting the inactive version through the
existing GIN index is the simplest implementation. GIN's `fastupdate` mode
batches new entries in a pending list, but a large pending list can slow searches
and foreground cleanup can cause latency spikes.
([PostgreSQL: GIN fast update](https://www.postgresql.org/docs/16/gin.html))

If measured import time or query latency is unacceptable, graduate to a physical
staging table or catalog-version partition: bulk load first, build its GIN index,
run `ANALYZE`, then attach/publish it. PostgreSQL advises dropping and recreating
a GIN index for bulk insertion and notes that GIN build time is sensitive to
`maintenance_work_mem`.
([PostgreSQL: GIN tips](https://www.postgresql.org/docs/16/gin.html#GIN-TIPS),
[PostgreSQL: examining index usage](https://www.postgresql.org/docs/16/indexes-examine.html))

Do not tune `fastupdate`, `gin_pending_list_limit`, `maintenance_work_mem`, or
partitioning in V1 without measured need. These are deployment/workload
decisions, not part of the Catalog Search interface.

## Decisions that require corpus evidence

Build a small relevance set from real EasyWorship backups before locking these
values:

1. **Language strategy:** compare shared `simple`+`unaccent` against English and
   French configurations using bilingual and monolingual songs.
2. **Weights:** compare title `A` / lyrics `D` defaults against stronger or weaker
   title emphasis.
3. **Rank function and normalization:** compare `ts_rank` and `ts_rank_cd`,
   especially on songs with repeated choruses.
4. **Query semantics:** measure whether implicit `AND` from web-search input causes
   too many zero-result queries and whether a controlled fallback is necessary.
5. **Trigram behavior:** set minimum query length, nearest-neighbor candidate
   count, and any similarity threshold from labeled misspellings and partial
   titles.
6. **Snippet options:** tune fragment count and word limits against real cleaned
   lyrics and verify that verse/chorus structure remains understandable.
7. **Operations:** record row count, vector/index size, import duration, GIN
   pending-list behavior, `ANALYZE` duration, and `EXPLAIN (ANALYZE, BUFFERS)`
   plans on representative searches. PostgreSQL recommends testing indexes with
   real data and running `ANALYZE` before judging plans.
   ([PostgreSQL: examining index usage](https://www.postgresql.org/docs/16/indexes-examine.html))

An acceptance corpus should contain at least:

- exact and partial titles;
- title misspellings;
- lyric-only phrases;
- punctuation and apostrophes;
- accented and unaccented French;
- English, French, and bilingual songs;
- repeated chorus terms;
- short/common-word and stop-word-only input;
- quotes, `OR`, negation, and malformed punctuation;
- multiple equally ranked songs to verify stable pagination.

## Optional refinements, not V1 commitments

- Per-row English/French configurations after reliable language classification.
- Safe last-token prefix query construction if title trigram fallback proves
  insufficient.
- A blended full-text/trigram scoring model derived from labeled relevance data.
- Synonym or thesaurus dictionaries for church-specific terminology.
- Version partitions or blue/green physical tables for larger catalogs.
- Precomputed result snippets or application-side structural snippets if
  `ts_headline` is too slow or damages lyric structure.
- Query analytics and relevance tuning based on anonymized searches.

None of these should enlarge the initial Catalog Search interface.
