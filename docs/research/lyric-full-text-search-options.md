# Lyric full-text search options

## Recommendation

For lyric lookup, the best default is a **layered lexical search**, not a
semantic-only search:

1. Normalize Unicode, case, and diacritics; preserve the original lyric text
   and positions for display.
2. Use an inverted-index lexical ranker (BM25 when using Lucene/OpenSearch;
   PostgreSQL's native ranked full-text search for the existing V1 design) as
   the primary retrieval path.
3. Strongly boost an exact quoted phrase and near-phrase match. This is the
   most dependable behavior when someone remembers a lyric line.
4. Run character-trigram/typo expansion only as a constrained fallback, then
   re-run the lexical query. Do not let fuzzy matching dominate ordinary
   results.
5. Add a separate transliterated field only for languages/scripts present in
   the catalog. Add phonetic fields only after query evidence demonstrates a
   spoken/heard-lyric need.
6. Treat embeddings and hybrid rank fusion as an optional **second retrieval
   channel** for conceptual queries (for example, “a song about God’s
   faithfulness”), not as the authority for a remembered lyric fragment.

This is an engineering recommendation, inferred from the documented mechanics
below and the product's lyric-recall use case; it is not a claim that one
algorithm is universally best. It aligns with the project's accepted
[PostgreSQL search ADR](../adr/0005-postgres-search-and-pinned-read-api.md):
keep PostgreSQL for V1, retain the lyric vector separately, and use bounded
trigram fallback rather than introducing another search service before measured
need.

## Options and fit for lyrics

| Technique | What it is good at | Lyric-search guidance |
| --- | --- | --- |
| Lexical inverted index + BM25-style ranking | Terms that occur in the remembered fragment; downweights ubiquitous words and accommodates document length. Lucene provides BM25 with tunable `k1` and `b` parameters. | Primary candidate if adopting Lucene/OpenSearch/Elasticsearch. Index title, writer, and lyrics separately so a title does not swamp a lyric lookup. [Lucene BM25 API](https://lucene.apache.org/core/7_6_0/core/org/apache/lucene/search/similarities/BM25Similarity.html) |
| Native PostgreSQL full-text ranking | Existing-stack lexical search, positional information, weighted fields, and two built-in rank functions that consider lexical, proximity, and structural information. | The current project choice. Use its `simple`-derived, unaccented configuration for mixed/contemporary worship vocabulary rather than assuming English stemming suits every song. [PostgreSQL text-search controls](https://www.postgresql.org/docs/current/textsearch-controls.html) |
| Exact phrase and bounded proximity | A line remembered in order; quoted phrases; words remembered with a small gap. | Essential. PostgreSQL's `phraseto_tsquery` creates phrase tests, and `tsquery_phrase` can require an exact lexeme distance. Keep vector positions; stripping them disables proximity ranking. [PostgreSQL text-search functions](https://www.postgresql.org/docs/current/functions-textsearch.html), [phrase controls](https://www.postgresql.org/docs/current/textsearch-features.html) |
| Character trigrams / n-grams | Misspellings, partial words, lyric spellings such as `hallelujah`/`halleluya`, and substring-like recall. | Use as a fallback or suggestion generator with a threshold and small candidate set. PostgreSQL `pg_trgm` supports fast similarity and misspelling integration; Lucene also supplies character n-gram tokenizers/filters. Fuzzy expansion necessarily increases false positives. [PostgreSQL `pg_trgm`](https://www.postgresql.org/docs/current/pgtrgm.html), [Lucene n-grams](https://lucene.apache.org/core/9_1_0/analysis/common/org/apache/lucene/analysis/ngram/package-summary.html) |
| Edit-distance fuzzy terms | A typo in one sufficiently long token. Lucene's `FuzzyQuery` uses Damerau-Levenshtein/Levenshtein distance. | A useful narrowly scoped fallback, but do not apply it indiscriminately to short lyric terms. Lucene caps this query at two edits and notes short terms can fail to match. [Lucene `FuzzyQuery`](https://lucene.apache.org/core/8_1_1/core/org/apache/lucene/search/FuzzyQuery.html) |
| Accent folding, multilingual analysis, transliteration | `café` versus `cafe`; lyrics in multiple scripts; Latin-script queries for non-Latin lyrics. | Make accent-insensitive matching baseline. PostgreSQL `unaccent` can be placed before a language stemmer. If a dedicated engine is later needed, OpenSearch ICU analysis supplies Unicode segmentation, folding, and transforms such as `Any-Latin`; index a separate transformed field and retain exact-script search. [PostgreSQL `unaccent`](https://www.postgresql.org/docs/current/unaccent.html), [OpenSearch ICU analyzer](https://docs.opensearch.org/latest/analyzers/language-analyzers/icu/), [ICU transform](https://docs.opensearch.org/latest/analyzers/token-filters/icu-transform/) |
| Phonetic encoding | Heard-but-not-seen spellings, principally names and select language-specific sound systems. | Optional and experimental for lyrics: phonetic encoders are language-dependent and can produce broad collisions. OpenSearch exposes several encoders and can retain the original token alongside the encoding (`replace: false`). PostgreSQL also has Soundex, Metaphone, Daitch-Mokotoff, and Levenshtein functions, but its docs specifically caution that the phonetic functions do not work well with multibyte encodings. [OpenSearch phonetic token filter](https://docs.opensearch.org/latest/analyzers/token-filters/phonetic/), [PostgreSQL `fuzzystrmatch`](https://www.postgresql.org/docs/current/fuzzystrmatch.html) |
| Semantic vectors + hybrid fusion | Intent or theme discovery when exact words are unknown. | Add only with evaluation data. OpenSearch hybrid search combines keyword and neural clauses and supports score normalization or rank fusion, but requires an embedding model and ingestion/search pipeline. Exact phrase/proximity should remain separately boosted and explainable. [OpenSearch hybrid search](https://docs.opensearch.org/latest/vector-search/ai-search/hybrid-search/) |

## What “best results” should mean here

Judge alternatives against a held-out set of actual congregation/staff queries,
not a generic web-search benchmark. Include: exact lines; partial lines; wrong
word order; one typo; punctuation/apostrophe variants; diacritic variants;
repeated chorus wording; code-switched songs; transliterated queries; and
theme-only queries. Measure recall at 1/3/10, time to a usable result, and
false positives. Keep exact/phrase, lexical, fuzzy, and semantic scores visible
in logs while tuning so a relevant song can be explained and corrected.

## Practical implementation order

1. Ship/validate the already-decided PostgreSQL `simple` + `unaccent` lyric
   vector with a GIN index and deterministic tie-breaker.
2. Parse quoted input as phrase search, with a safe plain-text fallback; use
   proximity-aware rank for unquoted multiword input.
3. Add a strict, rate-limited `pg_trgm` correction/suggestion path only when
   normal search yields no result. PostgreSQL explicitly documents trigram
   matching as useful alongside full-text search to recognize misspelled input.
   [PostgreSQL `pg_trgm` text-search integration](https://www.postgresql.org/docs/current/pgtrgm.html#PGTRGM-TEXT-SEARCH)
4. Build the relevance set above and tune thresholds/weights from observed
   failures. Escalate to OpenSearch hybrid/ICU only if multilingual or
   theme-search evaluation shows PostgreSQL cannot meet the target.
