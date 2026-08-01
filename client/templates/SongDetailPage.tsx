import React from "react";
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

type ProjectionSlide = {
    position: number;
    section_label: string;
    lines: string[];
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
};

const ProjectionPreview = ({title, slides}: {title: string; slides: ProjectionSlide[]}) => {
    const [currentIndex, setCurrentIndex] = React.useState(0);
    const current = slides[currentIndex];
    const longestLine = Math.max(1, ...slides.flatMap((slide) => slide.lines.map((line) => line.length)));
    const mostLines = Math.max(1, ...slides.map((slide) => slide.lines.length));
    const fit = Math.max(0.56, Math.min(1, 34 / longestLine, 5 / mostLines));
    const fitStyle = {"--projection-fit": fit} as React.CSSProperties;

    const move = (change: number) => {
        setCurrentIndex((index) => Math.min(Math.max(index + change, 0), slides.length - 1));
    };

    return (
        <section className="mt-20 border-t border-chapel-neutral-300 pt-12" aria-labelledby="projection-preview-heading">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
                <div>
                    <p className="text-xs font-bold uppercase tracking-[0.2em] text-chapel-primary-500">Approximate 16:9 canvas</p>
                    <h2 id="projection-preview-heading" className="mt-2 text-4xl sm:text-5xl">Projection Preview</h2>
                </div>
                <p className="max-w-md text-sm leading-6 text-chapel-neutral-600">A non-editable approximation for judging lyric flow and readability—not a pixel-identical EasyWorship renderer.</p>
            </div>

            <div className="mt-8 overflow-hidden border border-chapel-neutral-950 bg-black shadow-[0_28px_70px_rgba(15,30,66,0.22)]">
                <div className="projection-stage" style={fitStyle} aria-label={`Projection slide ${currentIndex + 1} of ${slides.length} for ${title}`}>
                    <div className="projection-stage__motion" aria-hidden="true">
                        <span className="projection-stage__glow projection-stage__glow--one" />
                        <span className="projection-stage__glow projection-stage__glow--two" />
                        <span className="projection-stage__rays" />
                    </div>
                    <div className="projection-stage__shade" aria-hidden="true" />
                    <div className="projection-stage__lyrics" aria-live="polite" aria-atomic="true">
                        <span className="sr-only">{current.section_label}. Slide {currentIndex + 1} of {slides.length}.</span>
                        {current.lines.map((line, index) => <p key={`${current.position}-${index}`}>{line}</p>)}
                    </div>
                    <div className="projection-stage__brand" aria-hidden="true">Chapel of Mercy</div>
                </div>

                <div className="grid gap-5 border-t border-white/15 bg-chapel-secondary-950 px-5 py-5 text-white sm:grid-cols-[auto_1fr_auto] sm:items-center sm:px-7">
                    <button
                        type="button"
                        onClick={() => move(-1)}
                        disabled={currentIndex === 0}
                        className="order-2 border border-white/25 px-4 py-3 text-xs font-bold uppercase tracking-[0.14em] transition-colors hover:bg-white hover:text-chapel-secondary-950 disabled:cursor-not-allowed disabled:opacity-35 sm:order-1"
                        aria-label="Show previous projection slide"
                    >
                        ← Previous
                    </button>
                    <div className="order-1 text-center sm:order-2">
                        <p className="text-xs font-bold uppercase tracking-[0.18em] text-worship-accent-300">{current.section_label}</p>
                        <p className="mt-1 text-sm text-white/60">Slide {currentIndex + 1} of {slides.length}</p>
                    </div>
                    <button
                        type="button"
                        onClick={() => move(1)}
                        disabled={currentIndex === slides.length - 1}
                        className="order-3 border border-white/25 px-4 py-3 text-xs font-bold uppercase tracking-[0.14em] transition-colors hover:bg-white hover:text-chapel-secondary-950 disabled:cursor-not-allowed disabled:opacity-35"
                        aria-label="Show next projection slide"
                    >
                        Next →
                    </button>
                </div>

                <div className="flex flex-wrap justify-center gap-2 border-t border-white/10 bg-chapel-secondary-950 px-5 pb-6" aria-label="Choose a projection slide">
                    {slides.map((slide, index) => (
                        <button
                            key={`${slide.position}-${index}`}
                            type="button"
                            onClick={() => setCurrentIndex(index)}
                            aria-label={`Show slide ${index + 1}: ${slide.section_label}`}
                            aria-current={index === currentIndex ? "step" : undefined}
                            className="h-2.5 w-8 border border-white/40 transition-colors hover:bg-white/60 aria-[current=step]:border-worship-accent-300 aria-[current=step]:bg-worship-accent-300"
                        >
                            <span className="sr-only">Slide {index + 1}</span>
                        </button>
                    ))}
                </div>
            </div>
        </section>
    );
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
                    </div>
                    <aside className="relative bg-chapel-secondary-950 px-6 py-12 text-white lg:my-12 lg:bg-transparent lg:px-12 lg:py-16" aria-label="Song information">
                        <dl className="space-y-7 lg:text-chapel-secondary-950">
                            <div className="border-b border-current/20 pb-5">
                                <dt className="text-[0.65rem] font-bold uppercase tracking-[0.2em] opacity-60">Song freshness</dt>
                                <dd className="mt-2 font-serif text-2xl"><time dateTime={props.song_freshness.iso} title={props.song_freshness.absolute}>{props.song_freshness.relative}</time></dd>
                            </div>
                            <div className="border-b border-current/20 pb-5">
                                <dt className="text-[0.65rem] font-bold uppercase tracking-[0.2em] opacity-60">Catalog freshness</dt>
                                <dd className="mt-2 font-serif text-2xl">
                                    {props.catalog_freshness ? <time dateTime={props.catalog_freshness.iso} title={props.catalog_freshness.absolute}>{props.catalog_freshness.relative}</time> : "Awaiting import"}
                                </dd>
                            </div>
                            <div className="border-b border-current/20 pb-5">
                                <dt className="text-[0.65rem] font-bold uppercase tracking-[0.2em] opacity-60">Lyrics rights status</dt>
                                <dd className="mt-2 font-serif text-2xl capitalize">{props.rights_status}</dd>
                            </div>
                            <div>
                                <dt className="text-[0.65rem] font-bold uppercase tracking-[0.2em] opacity-60">Projection structure</dt>
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
