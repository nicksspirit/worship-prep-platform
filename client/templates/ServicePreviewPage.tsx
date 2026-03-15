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

export const Template = (props: ServicePreviewPageProps) => {
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
                <div className="min-h-screen bg-chapel-neutral-50 px-4 py-16 text-chapel-neutral-950 sm:px-6 lg:px-8">
                    <div className="mx-auto max-w-3xl">
                        <section className="text-center">
                            <h1 className="mt-5 font-serif text-4xl font-bold tracking-tight text-chapel-neutral-900">
                                {emptyState?.heading ?? "No schedule available"}
                            </h1>
                            <p className="mx-auto mt-4 max-w-2xl text-base leading-7 text-chapel-neutral-600">
                                {emptyState?.message ??
                                    "A ready or published schedule will appear here once it is available."}
                            </p>
                            {emptyState?.link_url && emptyState.link_label ? (
                                <a
                                    href={emptyState.link_url}
                                    className="minimal-btn mt-8"
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
            <div className={`min-h-screen px-6 py-12 transition-colors lg:px-12 bg-white print:bg-white`}>
                <div className="mx-auto max-w-[1400px]">
                    
                    {/* Header Section */}
                    <div className="flex flex-col gap-6 md:flex-row md:items-start md:justify-between mb-16 border-b border-chapel-neutral-300 pb-8">
                        <div>
                            <h1 className="font-sans text-3xl font-bold uppercase tracking-wide text-chapel-neutral-900 sm:text-4xl mb-2">
                                {schedule.title}
                            </h1>
                            <div className="flex items-center gap-4">
                                <p className="text-sm font-medium text-chapel-neutral-600">
                                    {schedule.items.length} Agenda Items
                                </p>
                                {schedule.status !== "published" && (
                                    <span className="rounded-full bg-worship-accent-100 px-3 py-1 text-[10px] font-bold uppercase tracking-widest text-worship-accent-950">
                                        {schedule.status_label}
                                    </span>
                                )}
                            </div>
                        </div>

                        <div className="flex flex-wrap items-center gap-3">
                            <a
                                href={schedule.prev_url ?? "#"}
                                aria-disabled={!schedule.prev_url}
                                className={`rounded-full px-5 py-2 text-sm font-bold text-white transition-opacity hover:opacity-90 ${
                                    schedule.prev_url ? "bg-chapel-secondary-500" : "pointer-events-none bg-chapel-neutral-300 text-chapel-neutral-500"
                                }`}
                            >
                                Previous
                            </a>
                            <a
                                href={schedule.next_url ?? "#"}
                                aria-disabled={!schedule.next_url}
                                className={`rounded-full px-5 py-2 text-sm font-bold text-white transition-opacity hover:opacity-90 ${
                                    schedule.next_url ? "bg-chapel-secondary-500" : "pointer-events-none bg-chapel-neutral-300 text-chapel-neutral-500"
                                }`}
                            >
                                Next
                            </a>
                            <button
                                type="button"
                                onClick={() => window.print()}
                                className="rounded-full bg-chapel-primary-800 px-5 py-2 text-sm font-bold text-white transition-opacity hover:opacity-90"
                            >
                                Print
                            </button>
                        </div>
                    </div>

                    {/* Main Content Layout */}
                    <div className="grid gap-16 lg:grid-cols-[1fr_350px]">
                        
                        {/* Left Column: Agenda */}
                        <section>
                            <div className="mb-8">
                                <h2 className="text-lg font-bold uppercase tracking-wider text-chapel-neutral-900">
                                    Service Agenda
                                </h2>
                                <p className="text-sm text-chapel-neutral-500">Timeline and leadership handoff</p>
                            </div>

                            <div className="space-y-0">
                                {schedule.items.map((item) => (
                                    <article
                                        key={item.position}
                                        className="flex flex-col gap-4 border-t border-dotted border-chapel-neutral-400 py-6 sm:flex-row sm:items-start"
                                    >
                                        {/* Time & Item Number */}
                                        <div className="w-40 flex-shrink-0 pt-1">
                                            <p className="text-sm font-bold text-chapel-neutral-900">{item.time_label}</p>
                                            <p className="mt-1 text-[10px] font-bold uppercase tracking-widest text-chapel-neutral-500">
                                                Item {item.position}
                                            </p>
                                        </div>

                                        {/* Center: Pills, Title, Songs */}
                                        <div className="flex-1">
                                            <div className="mb-2 flex flex-wrap items-center gap-2">
                                                <span className="rounded-full bg-worship-accent-500 px-3 py-1 text-[10px] font-bold uppercase tracking-widest text-white shadow-sm">
                                                    {item.item_label}
                                                </span>
                                                {!item.is_complete && (
                                                    <span className="rounded-full bg-chapel-danger-600 px-3 py-1 text-[10px] font-bold uppercase tracking-widest text-white shadow-sm">
                                                        Missing Details
                                                    </span>
                                                )}
                                            </div>
                                            
                                            <h3 className="font-serif text-2xl font-bold text-chapel-neutral-950">
                                                {item.title}
                                            </h3>

                                            {item.notes && (
                                                <p className="mt-2 text-sm text-chapel-neutral-600">{item.notes}</p>
                                            )}

                                            {item.songs.length > 0 && (
                                                <div className="mt-4 rounded-xl border border-chapel-neutral-200 bg-white p-3">
                                                    <div className="flex flex-wrap items-center gap-2">
                                                        {item.songs
                                                            .slice()
                                                            .sort((a, b) => a.position - b.position)
                                                            .map((song) => (
                                                                <button
                                                                    key={song.song_id}
                                                                    type="button"
                                                                    onClick={() => setActiveItemPosition(item.position)}
                                                                    className="rounded-lg bg-chapel-neutral-100 px-3 py-1.5 text-xs font-medium text-chapel-neutral-700 transition hover:bg-chapel-neutral-200"
                                                                >
                                                                    <svg className="mr-1.5 inline-block h-3 w-3 text-chapel-neutral-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                                                                    </svg>
                                                                    {song.title}
                                                                </button>
                                                            ))}
                                                    </div>
                                                </div>
                                            )}
                                        </div>

                                        {/* Right: Leader */}
                                        <div className="w-48 flex-shrink-0 pt-1 text-left sm:text-right">
                                            <p className="text-sm font-bold text-chapel-neutral-900">
                                                Leader: <span className="font-medium">{item.leader_name ? item.leader_label : "-"}</span>
                                            </p>
                                            <div className="mt-1.5">
                                                <span className="inline-block rounded-full bg-chapel-neutral-100 px-2.5 py-1 text-[10px] font-bold uppercase tracking-widest text-chapel-neutral-500">
                                                    Status: {item.status_label}
                                                </span>
                                            </div>
                                        </div>
                                    </article>
                                ))}
                                <div className="border-t border-dotted border-chapel-neutral-400"></div>
                            </div>
                        </section>

                        {/* Right Column: Notes & Guidance */}
                        <aside className="space-y-12">
                            <section>
                                <h2 className="mb-6 text-lg font-bold uppercase tracking-wider text-chapel-neutral-900 border-b border-chapel-neutral-300 pb-2">
                                    Worship Notes
                                </h2>
                                <ul className="space-y-4">
                                    {serviceNotes.map((entry, idx) => (
                                        <li key={idx} className="flex items-start text-sm text-chapel-neutral-700 border-b border-dotted border-chapel-neutral-300 pb-4 last:border-0 last:pb-0">
                                            <div className="mr-3 mt-2 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-chapel-neutral-400"></div>
                                            <span>{entry}</span>
                                        </li>
                                    ))}
                                </ul>
                            </section>

                            <section>
                                <h2 className="mb-6 text-lg font-bold uppercase tracking-wider text-chapel-neutral-900 border-b border-chapel-neutral-300 pb-2">
                                    Print Guidance
                                </h2>
                                <ul className="space-y-4 text-sm text-chapel-neutral-700">
                                    <li className="flex items-start">
                                        <div className="mr-3 mt-0.5 flex h-4 w-4 flex-shrink-0 items-center justify-center rounded-full bg-chapel-secondary-500 text-white">
                                            <svg className="h-2.5 w-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                                            </svg>
                                        </div>
                                        <span>Use the Print button before sending this page to paper or PDF.</span>
                                    </li>
                                    <li className="flex items-start">
                                        <div className="mr-3 mt-0.5 flex h-4 w-4 flex-shrink-0 items-center justify-center rounded-full bg-chapel-secondary-500 text-white">
                                            <svg className="h-2.5 w-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                                            </svg>
                                        </div>
                                        <span>Open lyrics from worship and hymn items to export text files.</span>
                                    </li>
                                    <li className="flex items-start">
                                        <div className="mr-3 mt-0.5 flex h-4 w-4 flex-shrink-0 items-center justify-center rounded-full bg-chapel-secondary-500 text-white">
                                            <svg className="h-2.5 w-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                                            </svg>
                                        </div>
                                        <span>Incomplete agenda items are highlighted so the team can fill missing details.</span>
                                    </li>
                                </ul>
                            </section>
                        </aside>

                    </div>
                </div>

                {/* Lyrics Modal */}
                {activeItem ? (
                    <div className="fixed inset-0 z-50 flex items-center justify-center bg-chapel-neutral-950/60 px-4 py-6 backdrop-blur-sm print:hidden">
                        <div className="max-h-[90vh] w-full max-w-4xl overflow-hidden rounded-2xl bg-white shadow-2xl">
                            <div className="flex items-center justify-between border-b border-chapel-neutral-200 px-6 py-5 bg-chapel-neutral-50">
                                <div>
                                    <p className="text-xs font-bold uppercase tracking-widest text-chapel-secondary-500">
                                        Song lyrics
                                    </p>
                                    <h3 className="mt-1 font-serif text-2xl font-bold text-chapel-neutral-950">
                                        {activeItem.title}
                                    </h3>
                                </div>
                                <button
                                    type="button"
                                    onClick={() => setActiveItemPosition(null)}
                                    className="rounded-full p-2 text-chapel-neutral-500 hover:bg-chapel-neutral-200 transition-colors"
                                >
                                    <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                    </svg>
                                </button>
                            </div>

                            <div className="max-h-[calc(90vh-5.25rem)] overflow-y-auto px-6 py-6">
                                <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
                                    <p className="text-sm font-medium text-chapel-neutral-600">
                                        {activeItem.songs.length} song
                                        {activeItem.songs.length === 1 ? "" : "s"} linked to this schedule item.
                                    </p>
                                    {activeItem.songs.length > 1 ? (
                                        <button
                                            type="button"
                                            onClick={() => downloadAllSongs(activeItem)}
                                            className="rounded-lg bg-chapel-primary-600 px-4 py-2 text-sm font-bold text-white transition hover:bg-chapel-primary-700"
                                        >
                                            Download All (.zip)
                                        </button>
                                    ) : null}
                                </div>

                                <div className="space-y-6">
                                    {activeItem.songs
                                        .slice()
                                        .sort((left, right) => left.position - right.position)
                                        .map((song) => (
                                            <section
                                                key={song.song_id}
                                                className="rounded-xl border border-chapel-neutral-200 bg-chapel-neutral-50 overflow-hidden"
                                            >
                                                <div className="flex flex-col gap-3 border-b border-chapel-neutral-200 bg-white px-5 py-4 sm:flex-row sm:items-start sm:justify-between">
                                                    <div>
                                                        <p className="text-[10px] font-bold uppercase tracking-widest text-chapel-secondary-500">
                                                            Song {song.position + 1}
                                                        </p>
                                                        <h4 className="mt-1 font-serif text-xl font-bold text-chapel-neutral-900">
                                                            {song.title}
                                                        </h4>
                                                        <p className="mt-1 text-xs text-chapel-neutral-500">
                                                            {song.slide_count ?? "?"} slides | {song.filename}
                                                        </p>
                                                    </div>
                                                    <button
                                                        type="button"
                                                        onClick={() => downloadSong(song)}
                                                        className="rounded-lg border border-chapel-neutral-300 bg-white px-4 py-2 text-xs font-bold text-chapel-neutral-700 transition hover:bg-chapel-neutral-100 shadow-sm"
                                                    >
                                                        Download .txt
                                                    </button>
                                                </div>
                                                <pre className="p-5 overflow-x-auto whitespace-pre-wrap font-mono text-sm leading-relaxed text-chapel-neutral-800">
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
