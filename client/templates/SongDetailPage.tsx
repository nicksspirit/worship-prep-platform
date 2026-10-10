import React from "react";
import {ProjectionPreview, type ProjectionSlide} from "../components/ProjectionPreview";
import {Layout} from "../Layout";

type Freshness = {
    iso: string;
    absolute: string;
    relative: string;
};

type SongSection = {
    position: number;
    label: string;
    text: string;
};

type SongDetailPageProps = {
    title: string;
    author: string;
    copyright_notice: string;
    rights_status: string;
    lyrics_available: boolean;
    sections: SongSection[];
    slides: ProjectionSlide[];
    slide_count: number;
    song_freshness: Freshness;
    catalog_freshness: Freshness | null;
    catalog_url: string;
    add_to_cart_url: string;
};


export const Template = (props: SongDetailPageProps) => (
    <Layout title={`${props.title} — Song Catalog`}>
        <main className="min-h-[calc(100vh-5rem)] bg-chapel-neutral-50 text-chapel-neutral-950">
            <section className="relative overflow-hidden border-b border-chapel-neutral-300">
                <div className="absolute inset-y-0 right-0 hidden w-[38%] bg-chapel-primary-500 lg:block" aria-hidden="true" />
                <div className="relative mx-auto grid max-w-7xl lg:grid-cols-[1fr_0.55fr]">
                    <div className="px-6 py-14 lg:px-12 lg:py-24">
                        <a href={props.catalog_url} className="inline-flex items-center gap-3 text-xs font-bold uppercase tracking-[0.18em] text-chapel-neutral-600 transition-colors hover:text-chapel-primary-500">
                            <span aria-hidden="true">←</span> Back to search
                        </a>
                        <p className="mt-16 text-xs font-bold uppercase tracking-[0.18em] text-chapel-primary-500">Song Detail</p>
                        <h1 className="mt-4 max-w-4xl text-[clamp(3.7rem,8vw,6rem)] leading-[0.86] tracking-[-0.035em] text-balance">{props.title}</h1>
                        <p className="mt-8 text-lg font-semibold">Author: {props.author}</p>
                        <a href={props.add_to_cart_url} className="mt-8 inline-flex border border-chapel-neutral-950 bg-chapel-neutral-950 px-6 py-4 text-sm font-bold text-white hover:bg-chapel-primary-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-chapel-primary-500">
                            Add to song cart
                        </a>
                    </div>
                    <aside className="relative bg-chapel-secondary-950 px-6 py-12 text-white lg:my-12 lg:bg-transparent lg:px-12 lg:py-16" aria-label="Song information">
                        <dl className="space-y-7">
                            <div className="border-b border-current/20 pb-5">
                                <dt className="text-[0.65rem] font-bold uppercase tracking-[0.2em] text-white/80">Song freshness</dt>
                                <dd className="mt-2 font-serif text-2xl"><time dateTime={props.song_freshness.iso} title={props.song_freshness.absolute}>{props.song_freshness.relative}</time></dd>
                            </div>
                            <div className="border-b border-current/20 pb-5">
                                <dt className="text-[0.65rem] font-bold uppercase tracking-[0.2em] text-white/80">Catalog freshness</dt>
                                <dd className="mt-2 font-serif text-2xl">
                                    {props.catalog_freshness ? <time dateTime={props.catalog_freshness.iso} title={props.catalog_freshness.absolute}>{props.catalog_freshness.relative}</time> : "Awaiting import"}
                                </dd>
                            </div>
                            <div className="border-b border-current/20 pb-5">
                                <dt className="text-[0.65rem] font-bold uppercase tracking-[0.2em] text-white/80">Lyrics rights status</dt>
                                <dd className="mt-2 font-serif text-2xl capitalize">{props.rights_status}</dd>
                            </div>
                            <div>
                                <dt className="text-[0.65rem] font-bold uppercase tracking-[0.2em] text-white/80">Projection structure</dt>
                                <dd className="mt-2 font-serif text-2xl">{props.lyrics_available ? `${props.slide_count} ${props.slide_count === 1 ? "slide" : "slides"}` : "Not available"}</dd>
                            </div>
                        </dl>
                    </aside>
                </div>
            </section>

            <div className="mx-auto max-w-6xl px-6 py-14 lg:px-12 lg:py-20">
                {props.lyrics_available ? (
                    <>
                        <section aria-labelledby="song-lyrics-heading">
                            <div className="grid gap-8 lg:grid-cols-[0.45fr_1fr]">
                                <div>
                                    <h2 id="song-lyrics-heading" className="text-5xl">Lyrics</h2>
                                    <p className="mt-3 text-xs font-bold uppercase tracking-[0.16em] text-chapel-primary-500">Source order preserved</p>
                                    {props.copyright_notice && <p className="mt-6 max-w-xs text-sm leading-6 text-chapel-neutral-600">{props.copyright_notice}</p>}
                                </div>
                                <div className="divide-y divide-chapel-neutral-300 border-t border-chapel-neutral-950">
                                    {props.sections.map((section) => (
                                        <article key={`${section.position}-${section.label}`} className="grid gap-5 py-8 sm:grid-cols-[7rem_1fr]">
                                            <h3 className="font-sans text-xs font-bold uppercase tracking-[0.18em] text-chapel-primary-500">{section.label}</h3>
                                            <p className="whitespace-pre-line font-serif text-2xl leading-[1.35] sm:text-3xl">{section.text}</p>
                                        </article>
                                    ))}
                                </div>
                            </div>
                        </section>
                        {props.slides.length > 0 && <ProjectionPreview title={props.title} slides={props.slides} />}
                    </>
                ) : (
                    <section className="mx-auto max-w-3xl border border-chapel-primary-500 bg-white p-8" aria-labelledby="restricted-heading">
                        <p className="text-xs font-bold uppercase tracking-[0.2em] text-chapel-primary-500">Metadata-only entry</p>
                        <h2 id="restricted-heading" className="mt-3 text-4xl">Lyrics are unavailable for public display.</h2>
                        <p className="mt-4 max-w-xl leading-7 text-chapel-neutral-600">This song remains discoverable by title and source information, but its lyric text and projected lyric view are withheld under the current Lyrics Rights Status.</p>
                        {props.copyright_notice && <p className="mt-6 text-sm text-chapel-neutral-500">{props.copyright_notice}</p>}
                    </section>
                )}
            </div>
        </main>
    </Layout>
);
