import React from "react";
import {reverse} from "@reactivated";
import {Layout} from "../Layout";
import {CatalogSearchPrototype} from "../prototypes/CatalogSearchPrototype";

type Freshness = {
    iso: string;
    absolute: string;
    relative: string;
};

type SearchItem = {
    song_uid: string;
    url: string;
    title: string;
    author: string;
    lyric_preview: string[];
    lyrics_available: boolean;
    rights_status: string;
    song_freshness: Freshness;
};

export type CatalogSearchPageProps = {
    title: string;
    query: string;
    mode: string;
    limit: number;
    searched: boolean;
    results: SearchItem[];
    catalog_freshness: Freshness | null;
    next_url: string | null;
    has_more: boolean;
    error: string | null;
    restart_url: string | null;
    prototype_variant: string | null;
};

const SearchGlyph = () => (
    <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8">
        <circle cx="11" cy="11" r="7" />
        <path d="m16.2 16.2 4.1 4.1" />
    </svg>
);

const FreshnessNote = ({freshness}: {freshness: Freshness | null}) => (
    <div className="flex items-center gap-3 text-xs font-semibold uppercase tracking-[0.15em] text-white/65">
        <span className="relative flex h-2 w-2" aria-hidden="true">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-worship-accent-300 opacity-60 motion-reduce:animate-none" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-worship-accent-300" />
        </span>
        {freshness ? (
            <span>
                Catalog refreshed <time dateTime={freshness.iso} title={freshness.absolute}>{freshness.relative}</time>
            </span>
        ) : (
            <span>Catalog awaiting its first import</span>
        )}
    </div>
);

export const Template = (props: CatalogSearchPageProps) => {
    const resultLabel = props.results.length === 1 ? "1 song" : `${props.results.length} songs`;

    const prototypeVariant = props.prototype_variant;
    if (!import.meta.env.PROD && (prototypeVariant === "A" || prototypeVariant === "B" || prototypeVariant === "C")) {
        return (
            <Layout title={`${props.title} — Design prototype`}>
                <CatalogSearchPrototype props={props} variant={prototypeVariant} />
            </Layout>
        );
    }

    return (
        <Layout title={props.title}>
            <main className="min-h-[calc(100vh-5rem)] bg-chapel-neutral-50 text-chapel-neutral-950">
                <section className="catalog-hero overflow-hidden border-b border-white/15 bg-chapel-secondary-950 text-white">
                    <div className="catalog-hero__halo" aria-hidden="true" />
                    <div className="relative mx-auto grid max-w-7xl gap-12 px-6 pb-16 pt-14 lg:grid-cols-[minmax(0,1fr)_minmax(28rem,0.78fr)] lg:px-12 lg:pb-24 lg:pt-20">
                        <div className="max-w-3xl">
                            <FreshnessNote freshness={props.catalog_freshness} />
                            <p className="mt-10 text-xs font-bold uppercase tracking-[0.2em] text-worship-accent-300">The worship archive</p>
                            <h1 className="mt-4 max-w-3xl text-[clamp(3.7rem,8vw,6rem)] leading-[0.82] tracking-[-0.035em] text-balance">
                                Find the song<br />
                                <span className="ml-[0.12em] italic text-worship-accent-300">you remember.</span>
                            </h1>
                            <p className="mt-9 max-w-xl text-base leading-7 text-white/68 sm:text-lg">
                                Search the Chapel of Mercy collection by a title you know or by the words still with you.
                            </p>
                        </div>

                        <form action={reverse("catalog:search")} method="get" className="self-end border border-chapel-secondary-700 bg-chapel-secondary-900 p-5 shadow-[0_18px_42px_rgba(0,0,0,0.24)] sm:p-7" role="search">
                            <fieldset>
                                <legend className="text-xs font-bold uppercase tracking-[0.2em] text-white/60">Search in</legend>
                                <div className="mt-4 grid grid-cols-2 border border-white/20 p-1">
                                    {(["title", "lyrics"] as const).map((mode) => (
                                        <label key={mode} className="relative cursor-pointer">
                                            <input
                                                type="radio"
                                                name="mode"
                                                value={mode}
                                                defaultChecked={props.mode === mode}
                                                className="peer sr-only"
                                            />
                                            <span className="block px-4 py-3 text-center text-xs font-bold uppercase tracking-[0.16em] text-white/60 transition-colors peer-checked:bg-white peer-checked:text-chapel-secondary-950 peer-focus-visible:outline peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-worship-accent-300">
                                                {mode}
                                            </span>
                                        </label>
                                    ))}
                                </div>
                            </fieldset>
                            <label htmlFor="catalog-query" className="mt-7 block text-xs font-bold uppercase tracking-[0.2em] text-white/60">Words to find</label>
                            <div className="mt-3 flex border-b border-white/45 focus-within:border-worship-accent-300">
                                <input
                                    id="catalog-query"
                                    type="search"
                                    name="q"
                                    defaultValue={props.query}
                                    maxLength={128}
                                    autoComplete="off"
                                    placeholder={props.mode === "lyrics" ? "e.g. chains fall, fear bow" : "e.g. Way Maker"}
                                    className="min-w-0 flex-1 border-0 bg-transparent px-0 py-4 font-serif text-2xl text-white outline-none placeholder:text-white/30"
                                    aria-describedby="catalog-search-help"
                                />
                                <button type="submit" className="flex w-14 items-center justify-center text-white transition-colors hover:text-worship-accent-300" aria-label="Search the song catalog">
                                    <SearchGlyph />
                                </button>
                            </div>
                            {props.limit !== 20 && <input type="hidden" name="limit" value={props.limit} />}
                            <p id="catalog-search-help" className="mt-4 text-sm leading-6 text-white/55">
                                Plain words work best. Search ignores capitalization and accents.
                            </p>
                        </form>
                    </div>
                </section>

                <section className="mx-auto max-w-7xl px-6 py-14 lg:px-12 lg:py-20" aria-labelledby="catalog-results-heading">
                    {props.error ? (
                        <div role="alert" className="border border-chapel-primary-500 bg-white p-7">
                            <p className="text-xs font-bold uppercase tracking-[0.2em] text-chapel-primary-500">Search needs attention</p>
                            <h2 id="catalog-results-heading" className="mt-3 text-3xl">We could not continue that search.</h2>
                            <p className="mt-3 max-w-2xl text-chapel-neutral-700">{props.error}</p>
                            {props.restart_url && (
                                <a href={props.restart_url} className="mt-6 inline-flex border-b border-chapel-neutral-950 pb-1 text-xs font-bold uppercase tracking-[0.15em]">
                                    Restart this search
                                </a>
                            )}
                        </div>
                    ) : !props.searched ? (
                        <div className="grid gap-10 lg:grid-cols-[0.72fr_1fr] lg:items-start">
                            <div>
                                <h2 id="catalog-results-heading" className="max-w-lg text-5xl leading-[0.95] sm:text-6xl">Start with what you remember.</h2>
                                <p className="mt-5 max-w-md leading-7 text-chapel-neutral-600">A title fragment, a lyric line, or a few ordinary words are enough to begin.</p>
                            </div>
                            <div className="grid gap-px border border-chapel-neutral-300 bg-chapel-neutral-300 sm:grid-cols-3">
                                {[
                                    ["A title fragment", "Two or three words from the song title can be enough."],
                                    ["A lyric line", "Choose Lyrics when the words—not the name—are familiar."],
                                    ["Simple language", "No operators or special search syntax are needed."],
                                ].map(([heading, body]) => (
                                    <article key={heading} className="min-h-40 bg-chapel-neutral-50 p-6">
                                        <h3 className="font-sans text-sm font-bold uppercase tracking-[0.12em]">{heading}</h3>
                                        <p className="mt-3 text-sm leading-6 text-chapel-neutral-600">{body}</p>
                                    </article>
                                ))}
                            </div>
                        </div>
                    ) : props.results.length === 0 ? (
                        <div className="mx-auto max-w-2xl py-10 text-center">
                            <p className="font-serif text-7xl italic text-chapel-primary-500" aria-hidden="true">0</p>
                            <h2 id="catalog-results-heading" className="mt-5 text-4xl">No songs found for “{props.query.trim()}.”</h2>
                            <p className="mt-4 text-chapel-neutral-600">Try fewer words, check the spelling, or switch between Title and Lyrics. Your search has been kept above.</p>
                        </div>
                    ) : (
                        <>
                            <div className="flex flex-col gap-4 border-b border-chapel-neutral-400 pb-6 sm:flex-row sm:items-end sm:justify-between">
                                <div>
                                    <h2 id="catalog-results-heading" className="text-4xl sm:text-5xl">Songs for “{props.query.trim()}”</h2>
                                    <p className="mt-2 text-xs font-bold uppercase tracking-[0.16em] text-chapel-primary-500">Searching {props.mode}</p>
                                </div>
                                <p className="text-sm text-chapel-neutral-600">Showing {resultLabel}{props.has_more ? " on this page" : ""}</p>
                            </div>

                            <div className="divide-y divide-chapel-neutral-300">
                                {props.results.map((song, index) => (
                                    <article key={song.song_uid} className="group grid gap-5 py-9 md:grid-cols-[3rem_minmax(15rem,0.72fr)_minmax(0,1fr)_2rem] md:items-start">
                                        <span className="pt-2 font-serif text-xl italic text-chapel-neutral-400" aria-hidden="true">{String(index + 1).padStart(2, "0")}</span>
                                        <div>
                                            <h3 className="text-3xl leading-none sm:text-4xl">
                                                <a href={song.url} className="decoration-chapel-primary-300 underline-offset-8 transition-colors hover:text-chapel-primary-500 hover:underline focus-visible:underline">
                                                    {song.title}
                                                </a>
                                            </h3>
                                            <p className="mt-3 text-sm font-semibold text-chapel-neutral-700">Author: {song.author}</p>
                                            <p className="mt-2 text-xs text-chapel-neutral-500">
                                                Song updated <time dateTime={song.song_freshness.iso} title={song.song_freshness.absolute}>{song.song_freshness.relative}</time>
                                            </p>
                                        </div>
                                        <div className="min-h-20 border-l border-chapel-neutral-300 pl-5 text-sm leading-6 text-chapel-neutral-600">
                                            {song.lyrics_available ? (
                                                <>
                                                    <p className="mb-2 text-[0.65rem] font-bold uppercase tracking-[0.17em] text-chapel-neutral-400">Lyric preview</p>
                                                    {song.lyric_preview.map((line, lineIndex) => <p key={lineIndex}>{line}</p>)}
                                                </>
                                            ) : (
                                                <div className="flex min-h-20 items-center text-sm italic text-chapel-neutral-500">Lyrics unavailable for public display.</div>
                                            )}
                                        </div>
                                        <span className="hidden pt-2 text-2xl text-chapel-primary-500 transition-transform group-hover:translate-x-1 md:block" aria-hidden="true">→</span>
                                    </article>
                                ))}
                            </div>

                            {props.next_url && (
                                <div className="flex justify-end border-t border-chapel-neutral-950 pt-8">
                                    <a href={props.next_url} rel="next" data-purpose="catalog-next" className="minimal-btn">
                                        Continue browsing <span aria-hidden="true" className="ml-3">→</span>
                                    </a>
                                </div>
                            )}
                        </>
                    )}
                </section>
            </main>
        </Layout>
    );
};
