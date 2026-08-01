import React from "react";

const variants = [
    {key: "A", name: "Sanctuary Index"},
    {key: "B", name: "Projection Desk"},
    {key: "C", name: "Printed Hymnal"},
] as const;

type VariantKey = (typeof variants)[number]["key"];

export const PrototypeSwitcher = ({current}: {current: VariantKey}) => {
    const currentIndex = variants.findIndex((variant) => variant.key === current);

    const choose = React.useCallback((offset: number) => {
        const nextIndex = (currentIndex + offset + variants.length) % variants.length;
        const url = new URL(window.location.href);
        url.searchParams.set("variant", variants[nextIndex].key);
        window.location.assign(url);
    }, [currentIndex]);

    React.useEffect(() => {
        const handleKeyDown = (event: KeyboardEvent) => {
            const target = event.target as HTMLElement | null;
            if (target?.matches("input, textarea, [contenteditable='true']")) return;
            if (event.key === "ArrowLeft") choose(-1);
            if (event.key === "ArrowRight") choose(1);
        };
        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
    }, [choose]);

    if (import.meta.env.PROD) return null;

    return (
        <div className="fixed inset-x-0 bottom-5 z-[100] flex justify-center px-4" role="toolbar" aria-label="Catalog design prototype variants">
            <div className="flex min-h-14 items-center gap-2 rounded-full bg-chapel-neutral-950 p-1.5 text-white shadow-[0_12px_32px_rgba(0,0,0,0.35)]">
                <button type="button" onClick={() => choose(-1)} className="grid h-11 w-11 place-items-center rounded-full border border-white/20 text-lg hover:bg-white hover:text-chapel-neutral-950 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-worship-accent-300" aria-label="Previous design variant">←</button>
                <div className="min-w-48 px-3 text-center">
                    <p className="text-[0.6rem] font-bold uppercase tracking-[0.18em] text-worship-accent-300">Prototype — local only</p>
                    <p className="mt-0.5 text-sm font-semibold">{current} — {variants[currentIndex].name}</p>
                </div>
                <button type="button" onClick={() => choose(1)} className="grid h-11 w-11 place-items-center rounded-full border border-white/20 text-lg hover:bg-white hover:text-chapel-neutral-950 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-worship-accent-300" aria-label="Next design variant">→</button>
            </div>
        </div>
    );
};
