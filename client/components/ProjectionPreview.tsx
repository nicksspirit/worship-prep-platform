import React from "react";
import {Context} from "@reactivated";

export type ProjectionSlide = {
    position: number;
    section_label: string;
    lines: string[];
};

export const ProjectionPreview = ({title, slides}: {title: string; slides: ProjectionSlide[]}) => {
    const {STATIC_URL} = React.useContext(Context);
    const staticUrl = STATIC_URL.replace(/\/+$/, "");
    const [currentIndex, setCurrentIndex] = React.useState(0);
    const [isFullscreen, setIsFullscreen] = React.useState(false);
    const [reduceMotion, setReduceMotion] = React.useState(false);
    const launchButtonRef = React.useRef<HTMLButtonElement>(null);
    const closeButtonRef = React.useRef<HTMLButtonElement>(null);
    const previewRef = React.useRef<HTMLDivElement>(null);
    const videoRef = React.useRef<HTMLVideoElement>(null);
    const current = slides[currentIndex];
    const longestLine = Math.max(1, ...slides.flatMap((slide) => slide.lines.map((line) => line.length)));
    const mostLines = Math.max(1, ...slides.map((slide) => slide.lines.length));
    const fit = Math.max(0.56, Math.min(1, 34 / longestLine, 5 / mostLines));
    const fitStyle = {"--projection-fit": fit} as React.CSSProperties;

    const move = (change: number) => {
        setCurrentIndex((index) => Math.min(Math.max(index + change, 0), slides.length - 1));
    };

    const openFullscreenPreview = () => {
        setIsFullscreen(true);
    };

    const closeFullscreenPreview = () => {
        setIsFullscreen(false);
    };

    React.useEffect(() => {
        if (!isFullscreen) return;
        const previousOverflow = document.body.style.overflow;
        const closeOnEscape = (event: KeyboardEvent) => {
            if (event.key === "Escape") closeFullscreenPreview();
            if (event.key === "Tab") {
                const buttons = previewRef.current?.querySelectorAll<HTMLButtonElement>("button:not(:disabled)");
                if (!buttons?.length) return;
                const first = buttons[0];
                const last = buttons[buttons.length - 1];
                if (event.shiftKey && document.activeElement === first) {
                    event.preventDefault();
                    last.focus();
                } else if (!event.shiftKey && document.activeElement === last) {
                    event.preventDefault();
                    first.focus();
                }
            }
        };
        document.body.style.overflow = "hidden";
        document.addEventListener("keydown", closeOnEscape);
        requestAnimationFrame(() => closeButtonRef.current?.focus());

        return () => {
            document.body.style.overflow = previousOverflow;
            document.removeEventListener("keydown", closeOnEscape);
            launchButtonRef.current?.focus();
        };
    }, [isFullscreen]);

    React.useEffect(() => {
        const preference = window.matchMedia("(prefers-reduced-motion: reduce)");
        const updatePreference = () => setReduceMotion(preference.matches);
        updatePreference();
        preference.addEventListener("change", updatePreference);
        return () => preference.removeEventListener("change", updatePreference);
    }, []);

    React.useEffect(() => {
        const video = videoRef.current;
        if (!video) return;
        if (reduceMotion) {
            video.pause();
            if (video.readyState >= 1) {
                video.currentTime = Math.min(0.25, video.duration || 0.25);
            }
            return;
        }
        void video.play().catch(() => undefined);
    }, [reduceMotion]);

    return (
        <section className="mt-20 border-t border-chapel-neutral-300 pt-12" aria-labelledby="projection-preview-heading">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
                <div>
                    <p className="text-xs font-normal text-chapel-neutral-700">Approximate 16:9 canvas</p>
                    <h2 id="projection-preview-heading" className="mt-2 text-4xl sm:text-5xl">Projection Preview</h2>
                </div>
                <div className="max-w-md">
                    <p className="text-sm leading-6 text-chapel-neutral-600">A non-editable approximation for judging lyric flow and readability—not a pixel-identical EasyWorship renderer.</p>
                    <button
                        ref={launchButtonRef}
                        type="button"
                        onClick={openFullscreenPreview}
                        className="mt-5 inline-flex w-full items-center justify-between border border-chapel-neutral-950 bg-chapel-neutral-950 px-5 py-4 text-xs font-bold uppercase tracking-[0.15em] text-white sm:w-auto sm:gap-8"
                    >
                        Open full screen preview <span aria-hidden="true">↗</span>
                    </button>
                </div>
            </div>

            <div
                ref={previewRef}
                className={`projection-preview-shell mt-8 overflow-hidden border border-chapel-neutral-950 bg-black shadow-[0_28px_70px_rgba(15,30,66,0.22)]${isFullscreen ? " projection-preview-shell--fullscreen" : ""}`}
                role={isFullscreen ? "dialog" : undefined}
                aria-modal={isFullscreen ? "true" : undefined}
                aria-labelledby={isFullscreen ? "projection-fullscreen-heading" : undefined}
            >
                <div className="projection-preview__fullscreen-bar">
                    <p id="projection-fullscreen-heading">Projection Preview</p>
                    <button
                        ref={closeButtonRef}
                        type="button"
                        onClick={closeFullscreenPreview}
                        aria-label="Close full screen preview"
                    >
                        Close <span aria-hidden="true">×</span>
                    </button>
                </div>
                <div className="projection-preview__canvas">
                  <div className="projection-stage" style={fitStyle} aria-label={`Projection slide ${currentIndex + 1} of ${slides.length} for ${title}`}>
                    <video
                        ref={videoRef}
                        className="projection-stage__background"
                        autoPlay={!reduceMotion}
                        loop
                        muted
                        playsInline
                        preload="metadata"
                        aria-hidden="true"
                        onLoadedMetadata={(event) => {
                            if (reduceMotion) {
                                event.currentTarget.pause();
                                event.currentTarget.currentTime = Math.min(0.25, event.currentTarget.duration || 0.25);
                            }
                        }}
                    >
                        <source src={`${staticUrl}/media/default-song-background.mp4`} type="video/mp4" />
                    </video>
                    <div className="projection-stage__shade" aria-hidden="true" />
                    <div className="projection-stage__lyrics" aria-live="polite" aria-atomic="true">
                        <span className="sr-only">{current.section_label}. Slide {currentIndex + 1} of {slides.length}.</span>
                        {current.lines.map((line, index) => <p key={`${current.position}-${index}`}>{line}</p>)}
                    </div>
                    <div className="projection-stage__brand" aria-hidden="true">Chapel of Mercy</div>
                  </div>
                </div>

                <div className="projection-preview__controls grid gap-5 border-t border-white/15 bg-chapel-secondary-950 px-5 py-5 text-white sm:grid-cols-[auto_1fr_auto] sm:items-center sm:px-7">
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

                <div className="projection-preview__pager flex flex-wrap justify-center gap-2 border-t border-white/10 bg-chapel-secondary-950 px-5 pb-6" aria-label="Choose a projection slide">
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
