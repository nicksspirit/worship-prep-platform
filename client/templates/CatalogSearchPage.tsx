import React from "react";
import {reverse} from "@reactivated";
import {Layout} from "../Layout";

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

type CatalogSearchPageProps = {
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
};

const SearchGlyph = () => (
    <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8">
        <circle cx="11" cy="11" r="7" />
        <path d="m16.2 16.2 4.1 4.1" />
    </svg>
);

const FreshnessNote = ({freshness}: {freshness: Freshness | null}) => (
    <p className="flex items-center gap-3 text-xs font-bold uppercase tracking-[0.14em] text-chapel-neutral-600">
        <span className="h-2 w-2 rounded-full bg-chapel-primary-500" aria-hidden="true" />
        {freshness ? (
            <span>
                Catalog refreshed <time dateTime={freshness.iso} title={freshness.absolute}>{freshness.relative}</time>
            </span>
        ) : (
            <span>Catalog awaiting its first import</span>
        )}
    </p>
);

const SearchForm = ({props}: {props: CatalogSearchPageProps}) => (
    <form action={reverse("catalog:search")} method="get" role="search" className="mt-5">
        <label htmlFor="catalog-query" className="text-xs font-bold uppercase tracking-[0.16em] text-chapel-neutral-600">
            Search titles or lyrics
        </label>
        <div className="mt-2 flex items-end gap-3 border-b-2 border-chapel-neutral-950 focus-within:border-chapel-primary-500">
            <input
                id="catalog-query"
                type="search"
                name="q"
                defaultValue={props.query}
                maxLength={128}
                autoComplete="off"
                placeholder={props.mode === "lyrics" ? "Enter a line you remember" : "Enter a song title"}
                className="min-w-0 flex-1 border-0 bg-transparent py-4 font-serif text-2xl text-chapel-neutral-950 outline-none placeholder:text-chapel-neutral-400 sm:text-3xl"
                aria-describedby="catalog-search-help"
            />
            <button
                type="submit"
                className="mb-3 grid h-11 w-11 shrink-0 place-items-center border border-chapel-neutral-950 text-chapel-neutral-950 transition-colors hover:border-chapel-primary-500 hover:bg-chapel-primary-500 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-chapel-primary-500"
                aria-label="Search the song catalog"
            >
                <SearchGlyph />
            </button>
        </div>
        <fieldset className="mt-4 flex flex-wrap items-center gap-x-6 gap-y-3">
            <legend className="sr-only">Search in</legend>
            {(["title", "lyrics"] as const).map((mode) => (
                <label key={mode} className="flex cursor-pointer items-center gap-2 text-xs font-bold uppercase tracking-[0.14em]">
                    <input
                        type="radio"
                        name="mode"
                        value={mode}
                        defaultChecked={props.mode === mode}
                        className="h-4 w-4 accent-chapel-primary-500"
                    />
                    {mode}
                </label>
            ))}
        </fieldset>
        {props.limit !== 20 && <input type="hidden" name="limit" value={props.limit} />}
        <p id="catalog-search-help" className="mt-4 max-w-xl text-sm leading-6 text-chapel-neutral-600">
            Use ordinary words. Capitalization and accents do not affect results.
        </p>
    </form>
);

const SearchHints = () => (
    <div className="grid gap-px border border-chapel-neutral-300 bg-chapel-neutral-300 sm:grid-cols-3">
        {[
            ["Title fragment", "Try two or three words from the song name."],
            ["Lyric line", "Choose Lyrics when the words are more familiar than the title."],
            ["Plain language", "No operators or special search syntax are needed."],
        ].map(([heading, body]) => (
            <article key={heading} className="bg-chapel-neutral-50 p-5">
                <h3 className="font-sans text-xs font-bold uppercase tracking-[0.14em]">{heading}</h3>
                <p className="mt-2 text-sm leading-6 text-chapel-neutral-600">{body}</p>
            </article>
        ))}
    </div>
);

export const Template = (props: CatalogSearchPageProps) => {
    const resultLabel = props.results.length === 1 ? "1 song" : `${props.results.length} songs`;

    return (
        <Layout title={props.title}>
            <main className="min-h-[calc(100vh-5rem)] bg-chapel-neutral-50 text-chapel-neutral-950">
                <div className="mx-auto grid max-w-7xl lg:grid-cols-[19rem_minmax(0,1fr)]">
                    <aside className="border-b border-chapel-primary-700 bg-chapel-primary-500 p-7 text-white lg:min-h-[calc(100vh-5rem)] lg:border-b-0 lg:border-r lg:p-10">
                        <p className="text-xs font-bold uppercase tracking-[0.18em] text-worship-accent-200">Sanctuary Index</p>
                        <h1 className="mt-6 max-w-xs text-5xl leading-[0.9] text-balance">Songs for gathering.</h1>
                        <p className="mt-6 max-w-md text-sm leading-6 text-white/80">
                            A clear, ordered index for the moment before rehearsal, service, or study.
                        </p>
                        <div className="mt-8 border-t border-white/30 pt-5 lg:mt-12">
                            <p className="text-xs font-bold uppercase tracking-[0.14em] text-worship-accent-200">Public edition</p>
                            <p className="mt-2 text-sm leading-6 text-white/75">Read-only songs prepared for the whole worship community.</p>
                        </div>
                        <div className="mt-10 hidden grid-cols-6 gap-x-3 gap-y-2 text-center text-[0.65rem] font-bold text-white/55 lg:grid" aria-hidden="true">
                            {"ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("").map((letter) => <span key={letter}>{letter}</span>)}
                        </div>
                    </aside>

                    <section className="min-w-0 px-6 py-9 sm:px-8 lg:px-12 lg:py-14" aria-labelledby="catalog-results-heading">
                        <div className="border-b border-chapel-neutral-300 pb-9">
                            <FreshnessNote freshness={props.catalog_freshness} />
                            <p className="mt-5 max-w-2xl text-sm leading-6 text-chapel-neutral-600">
                                Search by name when you know it. Search by lyrics when only the words remain.
                            </p>
                            <SearchForm props={props} />
                        </div>

                        <div className="pt-10">
                            {props.error ? (
                                <div role="alert" className="border border-chapel-primary-200 bg-chapel-primary-50 p-6 sm:p-8">
                                    <p className="text-xs font-bold uppercase tracking-[0.16em] text-chapel-primary-500">Search needs attention</p>
                                    <h2 id="catalog-results-heading" className="mt-3 text-3xl">We could not continue that search.</h2>
                                    <p className="mt-3 max-w-2xl text-chapel-neutral-700">{props.error}</p>
                                    {props.restart_url && (
                                        <a href={props.restart_url} className="mt-6 inline-flex border-b border-chapel-neutral-950 pb-1 text-xs font-bold uppercase tracking-[0.14em]">
                                            Restart this search
                                        </a>
                                    )}
                                </div>
                            ) : !props.searched ? (
                                <div>
                                    <div className="mb-7 flex flex-col gap-2 border-b border-chapel-neutral-950 pb-4 sm:flex-row sm:items-end sm:justify-between">
                                        <h2 id="catalog-results-heading" className="text-4xl">Start with what you remember.</h2>
                                        <p className="text-sm text-chapel-neutral-500">Three ways to begin</p>
                                    </div>
                                    <SearchHints />
                                </div>
                            ) : props.results.length === 0 ? (
                                <div className="max-w-2xl py-8">
                                    <p className="font-serif text-6xl italic text-chapel-primary-500" aria-hidden="true">0</p>
                                    <h2 id="catalog-results-heading" className="mt-4 text-4xl">No songs found for “{props.query.trim()}.”</h2>
                                    <p className="mt-4 leading-7 text-chapel-neutral-600">
                                        Try fewer words, check the spelling, or switch between Title and Lyrics. Your search remains above.
                                    </p>
                                </div>
                            ) : (
                                <>
                                    <div className="flex flex-col gap-3 border-b border-chapel-neutral-950 pb-4 sm:flex-row sm:items-end sm:justify-between">
                                        <div>
                                            <p className="text-xs font-bold uppercase tracking-[0.14em] text-chapel-primary-500">Searching {props.mode}</p>
                                            <h2 id="catalog-results-heading" className="mt-2 text-4xl">Songs for “{props.query.trim()}”</h2>
                                        </div>
                                        <p className="shrink-0 text-sm text-chapel-neutral-500">Showing {resultLabel}{props.has_more ? " on this page" : ""}</p>
                                    </div>

                                    <div className="divide-y divide-chapel-neutral-300">
                                        {props.results.map((song, index) => (
                                            <article key={song.song_uid} className="group grid gap-4 py-6 sm:grid-cols-[2.5rem_minmax(0,1fr)_minmax(12rem,0.7fr)_2rem] sm:items-center">
                                                <span className="font-serif text-lg italic text-chapel-neutral-400" aria-hidden="true">{String(index + 1).padStart(2, "0")}</span>
                                                <div className="min-w-0">
                                                    <h3 className="text-3xl leading-none">
                                                        <a href={song.url} className="decoration-chapel-primary-300 underline-offset-8 transition-colors hover:text-chapel-primary-500 hover:underline focus-visible:underline">
                                                            {song.title}
                                                        </a>
                                                    </h3>
                                                    <p className="mt-2 text-sm font-semibold text-chapel-neutral-700">Author: {song.author}</p>
                                                    <p className="mt-1 text-xs text-chapel-neutral-500">
                                                        Updated <time dateTime={song.song_freshness.iso} title={song.song_freshness.absolute}>{song.song_freshness.relative}</time>
                                                    </p>
                                                </div>
                                                <div className="border-l border-chapel-neutral-300 pl-4 text-sm leading-6 text-chapel-neutral-600">
                                                    {song.lyrics_available ? (
                                                        <>
                                                            <p className="mb-1 text-[0.65rem] font-bold uppercase tracking-[0.14em] text-chapel-neutral-400">Lyric preview</p>
                                                            {song.lyric_preview.map((line, lineIndex) => <p key={lineIndex}>{line}</p>)}
                                                        </>
                                                    ) : (
                                                        <p className="italic text-chapel-neutral-500">Lyrics unavailable for public display.</p>
                                                    )}
                                                </div>
                                                <span className="hidden text-right text-xl text-chapel-primary-500 transition-transform group-hover:translate-x-1 sm:block" aria-hidden="true">→</span>
                                            </article>
                                        ))}
                                    </div>

                                    {props.next_url && (
                                        <div className="flex justify-end border-t border-chapel-neutral-950 pt-7">
                                            <a href={props.next_url} rel="next" data-purpose="catalog-next" className="minimal-btn">
                                                Continue browsing <span aria-hidden="true" className="ml-3">→</span>
                                            </a>
                                        </div>
                                    )}
                                </>
                            )}
                        </div>
                    </section>
                </div>
            </main>
        </Layout>
    );
};
