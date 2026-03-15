import React from "react";

import {Layout} from "../Layout";
import {createZipBlob} from "../utils/zip";

type EmptyState = {
    heading: string;
    message: string;
    link_url: string | null;
    link_label: string | null;
};

type SongPreviewData = {
    song_id: string;
    title: string;
    formatted_lyrics: string;
    filename: string;
    slide_count: number | null;
    position: number;
};

type ScheduleItemPreviewData = {
    position: number;
    item_type: string;
    item_label: string;
    title: string;
    time_label: string;
    leader_name: string | null;
    leader_label: string;
    notes: string;
    status: string;
    status_label: string;
    is_complete: boolean;
    songs: SongPreviewData[];
};

type SchedulePreviewData = {
    schedule_id: string;
    date: string;
    display_date: string;
    title: string;
    status: string;
    status_label: string;
    prev_url: string | null;
    next_url: string | null;
    items: ScheduleItemPreviewData[];
};

type ServicePreviewPageProps = {
    title: string;
    schedule: SchedulePreviewData | null;
    empty_state: EmptyState | null;
};

type Tone = {
    background: string;
    border: string;
    text: string;
};

const shellBorder = "rgba(148, 163, 184, 0.18)";
const printShellBorder = "rgba(148, 163, 184, 0.32)";
const serviceNotes = [
    "Sunday School | 9:40 AM",
    "Worship Service | 10:30 AM",
    "Digging Deep (Bible Study) | Tuesdays at 7 PM on Cisco Webex",
    "Weekly Prayer Meeting | Daily at 9 PM on Webex",
    "Holy Ghost Friday Service | 1st Friday, 9 PM at 16100 SW Farmington Rd",
];

function sanitizeFilenameSegment(value: string): string {
    return value.replace(/[^a-z0-9]+/gi, "_").replace(/^_+|_+$/g, "") || "songs";
}

function downloadBlob(filename: string, blob: Blob): void {
    const downloadUrl = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = downloadUrl;
    anchor.download = filename;
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(downloadUrl), 0);
}

function downloadSong(song: SongPreviewData): void {
    downloadBlob(song.filename, new Blob([song.formatted_lyrics], {type: "text/plain"}));
}

function resolveItemTone(itemType: string): Tone {
    if (itemType === "worship_song" || itemType === "hymn") {
        return {
            background: "rgba(230, 126, 34, 0.14)",
            border: "rgba(230, 126, 34, 0.32)",
            text: "var(--worship-accent-300)",
        };
    }
    if (itemType === "sermon" || itemType === "scripture_reading") {
        return {
            background: "rgba(59, 130, 246, 0.14)",
            border: "rgba(59, 130, 246, 0.3)",
            text: "var(--chapel-secondary-200)",
        };
    }
    if (itemType === "opening_prayer" || itemType === "closing_prayer") {
        return {
            background: "rgba(157, 30, 44, 0.18)",
            border: "rgba(157, 30, 44, 0.34)",
            text: "var(--chapel-primary-200)",
        };
    }
    return {
        background: "rgba(248, 250, 252, 0.08)",
        border: "rgba(148, 163, 184, 0.22)",
        text: "rgb(226 232 240)",
    };
}

export const Template = (props: ServicePreviewPageProps) => {
    const [isPrintMode, setIsPrintMode] = React.useState(false);
    const [activeItemPosition, setActiveItemPosition] = React.useState<number | null>(null);

    const activeItem = React.useMemo(() => {
        return (
            props.schedule?.items.find((item) => item.position === activeItemPosition) ?? null
        );
    }, [activeItemPosition, props.schedule]);

    React.useEffect(() => {
        if (!activeItem) {
            return undefined;
        }

        const handleEscape = (event: KeyboardEvent) => {
            if (event.key === "Escape") {
                setActiveItemPosition(null);
            }
        };
        window.addEventListener("keydown", handleEscape);
        return () => window.removeEventListener("keydown", handleEscape);
    }, [activeItem]);

    if (props.empty_state || !props.schedule) {
        const emptyState = props.empty_state;
        return (
            <Layout title={props.title}>
                <div className="min-h-screen bg-slate-950 px-4 py-10 text-slate-100 sm:px-6 lg:px-8">
                    <div className="mx-auto max-w-3xl">
                        <section
                            className="rounded-[2rem] border p-10 text-center shadow-2xl"
                            style={{
                                borderColor: shellBorder,
                                background:
                                    "radial-gradient(circle at top, rgba(230, 126, 34, 0.24), transparent 28%), linear-gradient(160deg, rgba(15, 23, 42, 0.98), rgba(30, 41, 59, 0.94))",
                            }}
                        >
                            <p className="text-sm font-semibold uppercase tracking-[0.34em] text-orange-200/80">
                                Service Preview
                            </p>
                            <h1 className="mt-5 text-4xl font-black tracking-tight text-white">
                                {emptyState?.heading ?? "No schedule available"}
                            </h1>
                            <p className="mx-auto mt-4 max-w-2xl text-base leading-7 text-slate-300">
                                {emptyState?.message ??
                                    "A ready or published schedule will appear here once it is available."}
                            </p>
                            {emptyState?.link_url && emptyState.link_label ? (
                                <a
                                    href={emptyState.link_url}
                                    className="btn mt-8 border-0 text-white"
                                    style={{backgroundColor: "var(--chapel-primary-500)"}}
                                >
                                    {emptyState.link_label}
                                </a>
                            ) : null}
                        </section>
                    </div>
                </div>
            </Layout>
        );
    }

    const schedule = props.schedule;

    const downloadAllSongs = (item: ScheduleItemPreviewData) => {
        const archiveName = `${sanitizeFilenameSegment(schedule.title)}_${sanitizeFilenameSegment(item.title)}.zip`;
        const sortedSongs = [...item.songs].sort((left, right) => left.position - right.position);
        downloadBlob(
            archiveName,
            createZipBlob(
                sortedSongs.map((song) => ({
                    name: song.filename,
                    content: song.formatted_lyrics,
                })),
            ),
        );
    };

    return (
        <Layout title={props.title}>
            <div
                className={`min-h-screen px-4 py-6 transition-colors sm:px-6 lg:px-8 ${
                    isPrintMode ? "bg-stone-100 text-slate-900" : "bg-slate-950 text-slate-100"
                }`}
            >
                <div className="mx-auto flex max-w-7xl flex-col gap-8">
                    <section
                        className="overflow-hidden rounded-[2rem] border p-6 shadow-2xl sm:p-8"
                        style={{
                            borderColor: isPrintMode ? printShellBorder : shellBorder,
                            background: isPrintMode
                                ? "linear-gradient(145deg, rgba(255, 255, 255, 0.98), rgba(248, 250, 252, 0.96))"
                                : "radial-gradient(circle at top right, rgba(230, 126, 34, 0.24), transparent 32%), linear-gradient(135deg, rgba(15, 23, 42, 0.98), rgba(30, 58, 138, 0.88) 52%, rgba(157, 30, 44, 0.9))",
                        }}
                    >
                        <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
                            <div className="space-y-4">
                                <p
                                    className={`text-sm font-semibold uppercase tracking-[0.34em] ${
                                        isPrintMode ? "text-slate-500" : "text-orange-200/85"
                                    }`}
                                >
                                    Chapel of Mercy
                                </p>
                                <div className="space-y-3">
                                    <p
                                        className={`text-sm uppercase tracking-[0.28em] ${
                                            isPrintMode ? "text-slate-500" : "text-slate-300/75"
                                        }`}
                                    >
                                        {schedule.display_date}
                                    </p>
                                    <h1
                                        className={`max-w-4xl text-3xl font-black tracking-tight sm:text-5xl ${
                                            isPrintMode ? "text-slate-950" : "text-white"
                                        }`}
                                    >
                                        {schedule.title}
                                    </h1>
                                </div>
                                <div className="flex flex-wrap gap-3">
                                    {schedule.status !== "published" ? (
                                        <span
                                            className="rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.24em]"
                                            style={{
                                                backgroundColor: "rgba(230, 126, 34, 0.14)",
                                                borderColor: "rgba(230, 126, 34, 0.34)",
                                                color: "var(--worship-accent-300)",
                                            }}
                                        >
                                            {schedule.status_label}
                                        </span>
                                    ) : null}
                                    <span
                                        className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.24em] ${
                                            isPrintMode
                                                ? "border-slate-300 bg-white text-slate-600"
                                                : "border-white/10 bg-white/5 text-slate-300"
                                        }`}
                                    >
                                        {schedule.items.length} agenda items
                                    </span>
                                </div>
                            </div>

                            <div className="flex flex-wrap items-center gap-3">
                                <a
                                    href={schedule.prev_url ?? "#"}
                                    aria-disabled={!schedule.prev_url}
                                    className={`btn rounded-full border px-5 ${
                                        schedule.prev_url
                                            ? ""
                                            : "pointer-events-none opacity-40"
                                    } ${isPrintMode ? "border-slate-300 bg-white text-slate-700" : "border-white/15 bg-slate-950/35 text-slate-100"}`}
                                >
                                    Previous
                                </a>
                                <a
                                    href={schedule.next_url ?? "#"}
                                    aria-disabled={!schedule.next_url}
                                    className={`btn rounded-full border px-5 ${
                                        schedule.next_url
                                            ? ""
                                            : "pointer-events-none opacity-40"
                                    } ${isPrintMode ? "border-slate-300 bg-white text-slate-700" : "border-white/15 bg-slate-950/35 text-slate-100"}`}
                                >
                                    Next
                                </a>
                                <button
                                    type="button"
                                    onClick={() => setIsPrintMode((current) => !current)}
                                    className={`btn rounded-full border px-5 ${
                                        isPrintMode
                                            ? "border-slate-300 bg-white text-slate-700"
                                            : "border-white/15 bg-slate-950/35 text-slate-100"
                                    }`}
                                >
                                    {isPrintMode ? "Dark View" : "Print View"}
                                </button>
                                <button
                                    type="button"
                                    onClick={() => window.print()}
                                    className="btn rounded-full border-0 px-5 text-white"
                                    style={{backgroundColor: "var(--chapel-primary-500)"}}
                                >
                                    Print
                                </button>
                            </div>
                        </div>
                    </section>

                    <div className="grid gap-8 xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.75fr)]">
                        <section className="space-y-6">
                            <div className="flex items-end justify-between gap-4">
                                <div>
                                    <p
                                        className={`text-sm uppercase tracking-[0.3em] ${
                                            isPrintMode ? "text-slate-500" : "text-slate-400"
                                        }`}
                                    >
                                        Service Agenda
                                    </p>
                                    <h2
                                        className={`mt-2 text-3xl font-bold ${
                                            isPrintMode ? "text-slate-950" : "text-white"
                                        }`}
                                    >
                                        Timeline and leadership handoff
                                    </h2>
                                </div>
                            </div>

                            <div className="space-y-5">
                                {schedule.items.map((item) => {
                                    const tone = resolveItemTone(item.item_type);
                                    return (
                                        <article
                                            key={item.position}
                                            className={`grid gap-4 rounded-[1.75rem] border p-5 shadow-lg sm:grid-cols-[auto_1fr] sm:p-6 ${
                                                isPrintMode
                                                    ? "bg-white"
                                                    : "bg-slate-900/75 backdrop-blur"
                                            }`}
                                            style={{
                                                borderColor: isPrintMode
                                                    ? printShellBorder
                                                    : shellBorder,
                                            }}
                                        >
                                            <div className="flex flex-col items-start gap-3">
                                                <span
                                                    className={`rounded-2xl border px-4 py-2 text-sm font-semibold ${
                                                        isPrintMode ? "bg-slate-50" : ""
                                                    }`}
                                                    style={{
                                                        borderColor: tone.border,
                                                        backgroundColor: tone.background,
                                                        color: tone.text,
                                                    }}
                                                >
                                                    {item.time_label}
                                                </span>
                                                <div className="flex items-center gap-2">
                                                    <span
                                                        className="h-3 w-3 rounded-full"
                                                        style={{
                                                            backgroundColor: item.is_complete
                                                                ? "var(--chapel-success-500)"
                                                                : "var(--chapel-danger-500)",
                                                        }}
                                                    />
                                                    <span
                                                        className={`text-xs font-semibold uppercase tracking-[0.24em] ${
                                                            isPrintMode
                                                                ? "text-slate-500"
                                                                : "text-slate-400"
                                                        }`}
                                                    >
                                                        Item {item.position}
                                                    </span>
                                                </div>
                                            </div>

                                            <div className="space-y-4">
                                                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                                                    <div className="space-y-3">
                                                        <div className="flex flex-wrap items-center gap-3">
                                                            <span
                                                                className="rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.24em]"
                                                                style={{
                                                                    borderColor: tone.border,
                                                                    backgroundColor: tone.background,
                                                                    color: tone.text,
                                                                }}
                                                            >
                                                                {item.item_label}
                                                            </span>
                                                            {!item.is_complete ? (
                                                                <span
                                                                    className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.24em] ${
                                                                        isPrintMode
                                                                            ? "border-red-200 bg-red-50 text-red-700"
                                                                            : "border-red-400/25 bg-red-500/10 text-red-200"
                                                                    }`}
                                                                >
                                                                    Missing details
                                                                </span>
                                                            ) : null}
                                                        </div>
                                                        <h3
                                                            className={`text-2xl font-bold ${
                                                                isPrintMode
                                                                    ? "text-slate-950"
                                                                    : "text-white"
                                                            }`}
                                                        >
                                                            {item.title}
                                                        </h3>
                                                    </div>

                                                    <div
                                                        className={`rounded-2xl border px-4 py-3 text-sm ${
                                                            isPrintMode
                                                                ? "border-slate-200 bg-slate-50 text-slate-700"
                                                                : "border-white/10 bg-white/5 text-slate-200"
                                                        }`}
                                                    >
                                                        <p className="font-semibold">
                                                            Leader: {item.leader_label}
                                                        </p>
                                                        <p className="mt-1 opacity-80">
                                                            Status: {item.status_label}
                                                        </p>
                                                    </div>
                                                </div>

                                                {item.notes ? (
                                                    <div
                                                        className={`rounded-2xl border px-4 py-4 text-sm leading-6 ${
                                                            isPrintMode
                                                                ? "border-slate-200 bg-slate-50 text-slate-700"
                                                                : "border-white/10 bg-white/5 text-slate-300"
                                                        }`}
                                                    >
                                                        {item.notes}
                                                    </div>
                                                ) : null}

                                                {item.songs.length > 0 ? (
                                                    <div
                                                        className={`rounded-2xl border px-4 py-4 ${
                                                            isPrintMode
                                                                ? "border-slate-200 bg-slate-50"
                                                                : "border-white/10 bg-white/5"
                                                        }`}
                                                    >
                                                        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                                                            <div>
                                                                <p
                                                                    className={`text-xs font-semibold uppercase tracking-[0.3em] ${
                                                                        isPrintMode
                                                                            ? "text-slate-500"
                                                                            : "text-orange-200/80"
                                                                    }`}
                                                                >
                                                                    Linked songs
                                                                </p>
                                                                <div className="mt-3 flex flex-wrap gap-2">
                                                                    {item.songs
                                                                        .slice()
                                                                        .sort(
                                                                            (left, right) =>
                                                                                left.position -
                                                                                right.position,
                                                                        )
                                                                        .map((song) => (
                                                                            <button
                                                                                key={song.song_id}
                                                                                type="button"
                                                                                onClick={() =>
                                                                                    setActiveItemPosition(
                                                                                        item.position,
                                                                                    )
                                                                                }
                                                                                className={`rounded-full border px-3 py-2 text-sm font-medium transition hover:-translate-y-0.5 ${
                                                                                    isPrintMode
                                                                                        ? "border-slate-200 bg-white text-slate-700"
                                                                                        : "border-white/10 bg-slate-950/40 text-slate-100"
                                                                                }`}
                                                                            >
                                                                                {song.position + 1}.{" "}
                                                                                {song.title}
                                                                            </button>
                                                                        ))}
                                                                </div>
                                                            </div>
                                                            <button
                                                                type="button"
                                                                onClick={() =>
                                                                    setActiveItemPosition(item.position)
                                                                }
                                                                className="btn border-0 text-white"
                                                                style={{
                                                                    backgroundColor:
                                                                        "var(--chapel-secondary-500)",
                                                                }}
                                                            >
                                                                Open lyrics
                                                            </button>
                                                        </div>
                                                    </div>
                                                ) : null}
                                            </div>
                                        </article>
                                    );
                                })}
                            </div>
                        </section>

                        <aside className="space-y-5">
                            <section
                                className={`rounded-[1.75rem] border p-6 shadow-lg ${
                                    isPrintMode ? "bg-white" : "bg-slate-900/75"
                                }`}
                                style={{
                                    borderColor: isPrintMode ? printShellBorder : shellBorder,
                                }}
                            >
                                <p
                                    className={`text-sm uppercase tracking-[0.3em] ${
                                        isPrintMode ? "text-slate-500" : "text-orange-200/80"
                                    }`}
                                >
                                    Worship Notes
                                </p>
                                <div className="mt-4 space-y-4">
                                    {serviceNotes.map((entry) => (
                                        <div
                                            key={entry}
                                            className={`rounded-2xl border px-4 py-4 text-sm leading-6 ${
                                                isPrintMode
                                                    ? "border-slate-200 bg-slate-50 text-slate-700"
                                                    : "border-white/10 bg-white/5 text-slate-300"
                                            }`}
                                        >
                                            {entry}
                                        </div>
                                    ))}
                                </div>
                            </section>

                            <section
                                className={`rounded-[1.75rem] border p-6 shadow-lg ${
                                    isPrintMode ? "bg-white" : "bg-slate-900/75"
                                }`}
                                style={{
                                    borderColor: isPrintMode ? printShellBorder : shellBorder,
                                }}
                            >
                                <p
                                    className={`text-sm uppercase tracking-[0.3em] ${
                                        isPrintMode ? "text-slate-500" : "text-orange-200/80"
                                    }`}
                                >
                                    Print guidance
                                </p>
                                <ul
                                    className={`mt-4 space-y-3 text-sm leading-6 ${
                                        isPrintMode ? "text-slate-700" : "text-slate-300"
                                    }`}
                                >
                                    <li>Use Print View before sending this page to paper or PDF.</li>
                                    <li>Open lyrics from worship and hymn items to export text files.</li>
                                    <li>
                                        Incomplete agenda items are highlighted so the team can fill
                                        missing leader or time details before service.
                                    </li>
                                </ul>
                            </section>
                        </aside>
                    </div>
                </div>

                {activeItem ? (
                    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/78 px-4 py-6">
                        <div className="max-h-[90vh] w-full max-w-4xl overflow-hidden rounded-[2rem] border border-white/10 bg-slate-950 text-slate-100 shadow-2xl">
                            <div className="flex items-center justify-between border-b border-white/10 px-6 py-5">
                                <div>
                                    <p className="text-xs uppercase tracking-[0.28em] text-orange-200/75">
                                        Song lyrics
                                    </p>
                                    <h3 className="mt-2 text-2xl font-bold text-white">
                                        {activeItem.title}
                                    </h3>
                                </div>
                                <button
                                    type="button"
                                    onClick={() => setActiveItemPosition(null)}
                                    className="btn btn-ghost text-slate-100"
                                >
                                    Close
                                </button>
                            </div>

                            <div className="max-h-[calc(90vh-5.25rem)] overflow-y-auto px-6 py-6">
                                <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
                                    <p className="text-sm text-slate-300">
                                        {activeItem.songs.length} song
                                        {activeItem.songs.length === 1 ? "" : "s"} linked to this
                                        schedule item.
                                    </p>
                                    {activeItem.songs.length > 1 ? (
                                        <button
                                            type="button"
                                            onClick={() => downloadAllSongs(activeItem)}
                                            className="btn border-0 text-white"
                                            style={{
                                                backgroundColor: "var(--chapel-primary-500)",
                                            }}
                                        >
                                            Download All (.zip)
                                        </button>
                                    ) : null}
                                </div>

                                <div className="space-y-5">
                                    {activeItem.songs
                                        .slice()
                                        .sort((left, right) => left.position - right.position)
                                        .map((song) => (
                                            <section
                                                key={song.song_id}
                                                className="rounded-[1.5rem] border border-white/10 bg-white/5 p-5"
                                            >
                                                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                                                    <div>
                                                        <p className="text-xs uppercase tracking-[0.28em] text-orange-200/75">
                                                            Song {song.position + 1}
                                                        </p>
                                                        <h4 className="mt-2 text-2xl font-bold text-white">
                                                            {song.title}
                                                        </h4>
                                                        <p className="mt-2 text-sm text-slate-400">
                                                            {song.slide_count ?? "?"} slides |{" "}
                                                            {song.filename}
                                                        </p>
                                                    </div>
                                                    <button
                                                        type="button"
                                                        onClick={() => downloadSong(song)}
                                                        className="btn border-0 text-white"
                                                        style={{
                                                            backgroundColor:
                                                                "var(--chapel-secondary-500)",
                                                        }}
                                                    >
                                                        Download .txt
                                                    </button>
                                                </div>
                                                <pre className="mt-5 overflow-x-auto whitespace-pre-wrap rounded-[1.25rem] border border-white/10 bg-slate-950/70 p-4 font-mono text-sm leading-7 text-slate-200">
                                                    {song.formatted_lyrics}
                                                </pre>
                                            </section>
                                        ))}
                                </div>
                            </div>
                        </div>
                    </div>
                ) : null}
            </div>
        </Layout>
    );
};
