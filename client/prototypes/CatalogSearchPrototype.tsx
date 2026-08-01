import React from "react";
import {reverse} from "@reactivated";
import type {CatalogSearchPageProps} from "../templates/CatalogSearchPage";
import {PrototypeSwitcher} from "./PrototypeSwitcher";

// Three variants of public catalog search, switchable via ?variant=, on the existing / route.

type VariantKey = "A" | "B" | "C";
type SearchResult = CatalogSearchPageProps["results"][number];

const sampleResults: SearchResult[] = [
    {
        song_uid: "prototype-amazing-grace",
        url: "#",
        title: "Amazing Grace",
        author: "John Newton",
        lyric_preview: ["Amazing grace, how sweet the sound", "That saved a soul like me"],
        lyrics_available: true,
        rights_status: "unknown",
        song_freshness: {iso: "2026-08-01T12:00:00Z", absolute: "August 1, 2026", relative: "today"},
    },
    {
        song_uid: "prototype-be-thou-my-vision",
        url: "#",
        title: "Be Thou My Vision",
        author: "N/A",
        lyric_preview: ["Be Thou my vision, O Lord of my heart", "Naught be all else to me"],
        lyrics_available: true,
        rights_status: "approved",
        song_freshness: {iso: "2026-07-29T12:00:00Z", absolute: "July 29, 2026", relative: "3 days ago"},
    },
    {
        song_uid: "prototype-holy-forever",
        url: "#",
        title: "Holy Forever",
        author: "Chris Tomlin",
        lyric_preview: [],
        lyrics_available: false,
        rights_status: "restricted",
        song_freshness: {iso: "2026-07-20T12:00:00Z", absolute: "July 20, 2026", relative: "12 days ago"},
    },
];

const PrototypeSearch = ({mode, query, variant, tone = "light"}: {mode: string; query: string; variant: VariantKey; tone?: "light" | "dark"}) => (
    <form action={reverse("catalog:search")} method="get" className={tone === "dark" ? "text-white" : "text-chapel-neutral-950"}>
        <input type="hidden" name="variant" value={variant} />
        <div className={`flex items-end gap-4 border-b ${tone === "dark" ? "border-white/50" : "border-chapel-neutral-950"}`}>
            <label className="min-w-0 flex-1">
                <span className="block text-[0.65rem] font-bold uppercase tracking-[0.16em] opacity-60">Search titles or lyrics</span>
                <input name="q" defaultValue={query || "Amazing"} className="w-full border-0 bg-transparent py-4 font-serif text-3xl outline-none placeholder:opacity-40" placeholder="Enter ordinary words" />
            </label>
            <button type="submit" className="mb-3 grid h-11 w-11 place-items-center border border-current" aria-label="Search catalog">→</button>
        </div>
        <div className="mt-3 flex gap-5 text-xs font-bold uppercase tracking-[0.14em]">
            <label><input type="radio" name="mode" value="title" defaultChecked={mode !== "lyrics"} className="mr-2 accent-chapel-primary-500" />Title</label>
            <label><input type="radio" name="mode" value="lyrics" defaultChecked={mode === "lyrics"} className="mr-2 accent-chapel-primary-500" />Lyrics</label>
        </div>
    </form>
);

const VariantA = ({props, results}: {props: CatalogSearchPageProps; results: SearchResult[]}) => (
    <main className="min-h-[calc(100vh-5rem)] bg-chapel-neutral-50 pb-28 text-chapel-neutral-950">
        <div className="mx-auto grid max-w-7xl lg:grid-cols-[19rem_1fr]">
            <aside className="border-b border-chapel-neutral-300 bg-chapel-primary-500 p-7 text-white lg:min-h-[calc(100vh-5rem)] lg:border-b-0 lg:border-r lg:p-10">
                <p className="text-xs font-bold uppercase tracking-[0.18em] text-worship-accent-200">Sanctuary Index</p>
                <h1 className="mt-7 text-5xl leading-[0.9]">Songs for gathering.</h1>
                <p className="mt-6 text-sm leading-6 text-white/75">A quick, ordered index for the moment before rehearsal, service, or study.</p>
                <div className="mt-12 border-t border-white/30 pt-6 text-sm">
                    <p className="font-semibold">Catalog freshness</p>
                    <p className="mt-1 text-white/65">{props.catalog_freshness?.relative ?? "Awaiting import"}</p>
                </div>
                <div className="mt-10 hidden grid-cols-6 gap-2 text-center text-xs font-bold lg:grid">
                    {"ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("").map((letter) => <span key={letter} className="py-1 text-white/55">{letter}</span>)}
                </div>
            </aside>
            <section className="px-6 py-10 lg:px-12 lg:py-14">
                <PrototypeSearch mode={props.mode} query={props.query} variant="A" />
                <div className="mt-12 flex items-end justify-between border-b border-chapel-neutral-950 pb-4">
                    <h2 className="text-4xl">Catalog index</h2>
                    <span className="text-sm text-chapel-neutral-500">{results.length} sample songs</span>
                </div>
                <div className="divide-y divide-chapel-neutral-300">
                    {results.map((song) => (
                        <a key={song.song_uid} href={song.url} className="grid gap-3 py-6 transition-colors hover:bg-chapel-primary-50 sm:grid-cols-[1fr_12rem_3rem] sm:items-center sm:px-3">
                            <div><h3 className="text-3xl">{song.title}</h3><p className="mt-1 text-sm text-chapel-neutral-500">Author: {song.author}</p></div>
                            <p className="text-sm text-chapel-neutral-600">{song.lyrics_available ? song.lyric_preview[0] : "Metadata only"}</p>
                            <span className="text-right text-chapel-primary-500" aria-hidden="true">→</span>
                        </a>
                    ))}
                </div>
            </section>
        </div>
    </main>
);

const VariantB = ({props, results}: {props: CatalogSearchPageProps; results: SearchResult[]}) => (
    <main className="min-h-[calc(100vh-5rem)] bg-chapel-secondary-950 pb-28 text-white">
        <section className="border-b border-chapel-secondary-700 px-6 py-10 lg:px-12">
            <div className="mx-auto grid max-w-7xl items-end gap-10 lg:grid-cols-[1fr_1.1fr]">
                <div>
                    <p className="text-sm font-semibold text-worship-accent-300">Projection desk / discover</p>
                    <h1 className="mt-4 text-6xl leading-[0.9]">Type the line<br />still in your head.</h1>
                </div>
                <PrototypeSearch mode={props.mode} query={props.query} variant="B" tone="dark" />
            </div>
        </section>
        <section className="mx-auto grid max-w-7xl gap-0 lg:grid-cols-[0.8fr_1.2fr]">
            <div className="border-b border-chapel-secondary-700 lg:border-b-0 lg:border-r">
                {results.map((song, index) => (
                    <a key={song.song_uid} href={song.url} className={`block border-b border-chapel-secondary-700 px-6 py-7 transition-colors hover:bg-chapel-secondary-900 lg:px-10 ${index === 0 ? "bg-chapel-primary-500" : ""}`}>
                        <div className="flex items-start justify-between gap-4"><h2 className="text-3xl">{song.title}</h2><span className="text-xs opacity-50">0{index + 1}</span></div>
                        <p className="mt-2 text-sm opacity-65">{song.author}</p>
                    </a>
                ))}
            </div>
            <div className="grid min-h-[31rem] place-items-center overflow-hidden bg-chapel-secondary-800 p-8 lg:p-14">
                <div className="relative grid aspect-video w-full place-items-center overflow-hidden bg-chapel-secondary-950 shadow-[0_20px_55px_rgba(0,0,0,0.45)]">
                    <div className="absolute inset-0 bg-[radial-gradient(circle_at_30%_80%,var(--color-chapel-primary-500),transparent_48%)] opacity-65" />
                    <div className="relative max-w-[80%] text-center text-3xl font-bold leading-tight text-white [text-shadow:0_3px_12px_#000] sm:text-4xl">
                        {(results[0].lyric_preview.length ? results[0].lyric_preview : ["Lyrics unavailable for public display."]).map((line) => <p key={line}>{line}</p>)}
                    </div>
                </div>
            </div>
        </section>
    </main>
);

const VariantC = ({props, results}: {props: CatalogSearchPageProps; results: SearchResult[]}) => (
    <main className="min-h-[calc(100vh-5rem)] bg-chapel-neutral-100 pb-28 text-chapel-neutral-950">
        <header className="border-b-[0.5rem] border-chapel-primary-500 bg-chapel-neutral-50 px-6 py-10 lg:px-12">
            <div className="mx-auto flex max-w-7xl flex-col gap-8 lg:flex-row lg:items-end lg:justify-between">
                <div>
                    <p className="font-serif text-2xl italic text-chapel-primary-500">Chapel of Mercy</p>
                    <h1 className="mt-2 text-6xl tracking-[-0.03em]">The Song Register</h1>
                </div>
                <p className="max-w-sm border-t border-chapel-neutral-400 pt-3 text-sm leading-6 text-chapel-neutral-600">Public edition · Read-only · Refreshed {props.catalog_freshness?.relative ?? "after the first import"}</p>
            </div>
        </header>
        <section className="mx-auto max-w-7xl px-6 py-10 lg:px-12">
            <div className="grid gap-10 lg:grid-cols-[0.6fr_1fr]">
                <div className="lg:sticky lg:top-28 lg:self-start">
                    <h2 className="text-4xl italic">What do you remember?</h2>
                    <div className="mt-7"><PrototypeSearch mode={props.mode} query={props.query} variant="C" /></div>
                    <blockquote className="mt-14 border-t border-chapel-neutral-400 pt-7 font-serif text-2xl italic leading-8 text-chapel-neutral-600">“Search by name when you know it. Search by lyrics when only the words remain.”</blockquote>
                </div>
                <div className="columns-1 gap-8 sm:columns-2">
                    {results.map((song, index) => (
                        <article key={song.song_uid} className="mb-8 break-inside-avoid border-t-2 border-chapel-neutral-950 bg-chapel-neutral-50 p-6">
                            <p className="text-xs font-bold uppercase tracking-[0.14em] text-chapel-primary-500">Entry {String(index + 1).padStart(2, "0")}</p>
                            <h3 className="mt-4 text-4xl leading-none"><a href={song.url} className="hover:text-chapel-primary-500">{song.title}</a></h3>
                            <p className="mt-3 text-sm font-semibold">Author: {song.author}</p>
                            <div className="mt-8 border-t border-chapel-neutral-300 pt-5 font-serif text-xl italic leading-7 text-chapel-neutral-600">
                                {song.lyrics_available ? song.lyric_preview.map((line) => <p key={line}>{line}</p>) : <p>Lyrics unavailable for public display.</p>}
                            </div>
                        </article>
                    ))}
                </div>
            </div>
        </section>
    </main>
);

export const CatalogSearchPrototype = ({props, variant}: {props: CatalogSearchPageProps; variant: VariantKey}) => {
    const results = props.results.length > 0 ? props.results : sampleResults;
    return (
        <>
            {variant === "A" && <VariantA props={props} results={results} />}
            {variant === "B" && <VariantB props={props} results={results} />}
            {variant === "C" && <VariantC props={props} results={results} />}
            <PrototypeSwitcher current={variant} />
        </>
    );
};
