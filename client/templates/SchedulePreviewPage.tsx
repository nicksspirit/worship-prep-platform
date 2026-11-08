import React from "react";

import {Layout} from "../Layout";
import {ProjectionPreview, type ProjectionSlide} from "../components/ProjectionPreview";

type Props = {
    title: string | null;
    sections: {title: string | null; songs: {title: string; slides: ProjectionSlide[]}[]}[];
    created_date: string | null;
};

const dateFormat = new Intl.DateTimeFormat("en-US", {month: "short", day: "numeric", year: "numeric", timeZone: "UTC"});

export const Template = ({title, sections, created_date}: Props) => {
    const [songIndex, setSongIndex] = React.useState(0);
    let nextIndex = 0;
    const groups = sections.map(({title, songs}) => ({
        title,
        songs: songs.map((song) => ({...song, index: nextIndex++})),
    }));
    const songs = groups.flatMap((group) => group.songs);
    const song = songs[songIndex];

    return (
        <Layout title={title ? `${title} — Schedule Preview` : "Schedule Preview unavailable"}>
            <main className="min-h-[calc(100vh-5rem)] bg-chapel-neutral-50 text-chapel-neutral-950">
                <header className="border-b border-chapel-neutral-300 bg-chapel-secondary-950 text-white">
                    <div className="mx-auto max-w-7xl px-6 py-12 sm:py-16 lg:px-12">
                        <p className="text-xs font-bold uppercase tracking-[0.18em] text-worship-accent-300">Schedule Preview</p>
                        <h1 className="mt-4 break-words text-5xl sm:text-7xl">{title ?? "This preview is unavailable"}</h1>
                        <div className="mt-4 flex flex-wrap justify-between gap-x-6 gap-y-2 text-sm text-white/80">
                            <p>{title ? `${songs.length} ${songs.length === 1 ? "song" : "songs"} in service order` : "The link may have expired. Ask the tech team for a new preview."}</p>
                            {created_date && <p>Created <time dateTime={created_date}>{dateFormat.format(new Date(created_date))}</time></p>}
                        </div>
                    </div>
                </header>
                {song && (
                    <div className="mx-auto grid max-w-7xl items-start gap-10 px-6 py-10 lg:grid-cols-[minmax(0,16rem)_minmax(0,1fr)] lg:px-12">
                        <div className="min-w-0 lg:hidden">
                            <label htmlFor="schedule-preview-song" className="block text-sm font-bold">Choose a song</label>
                            <select
                                id="schedule-preview-song"
                                className="mt-3 w-full max-w-xl rounded-none border border-chapel-neutral-600 bg-white px-4 py-3 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-chapel-primary-500"
                                value={songIndex}
                                onChange={(event) => setSongIndex(Number(event.target.value))}
                            >
                                {groups.map(({title, songs}) => {
                                    const options = songs.map(({index, title}) => (
                                        <option key={index} value={index}>{`${index + 1}. ${title}`}</option>
                                    ));
                                    return title ? <optgroup key={title} label={title}>{options}</optgroup> : options;
                                })}
                            </select>
                        </div>
                        <aside className="hidden min-w-0 lg:block" aria-labelledby="service-order-heading">
                            <h2 id="service-order-heading" className="text-2xl">Service order</h2>
                            <div className="mt-4 max-h-[60dvh] space-y-5 overflow-y-auto">
                                {groups.map(({title, songs}) => (
                                    <div key={title ?? "ungrouped"}>
                                        {title && <h3 className="mb-2 text-xs font-bold uppercase tracking-wider text-chapel-neutral-700">{title}</h3>}
                                        <ol role="list" start={songs[0].index + 1} className="space-y-2">
                                            {songs.map(({index, title}) => (
                                                <li key={index}>
                                                    <button
                                                        type="button"
                                                        aria-current={songIndex === index ? "true" : undefined}
                                                        onClick={() => setSongIndex(index)}
                                                        className="flex w-full items-start gap-3 border border-chapel-neutral-300 bg-white px-3 py-3 text-start text-sm hover:border-chapel-primary-500 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-chapel-primary-500 aria-[current=true]:border-chapel-secondary-950 aria-[current=true]:bg-chapel-secondary-950 aria-[current=true]:text-white"
                                                    >
                                                        <span aria-hidden="true" className="shrink-0 tabular-nums opacity-75">{index + 1}.</span>
                                                        <span className="font-semibold [overflow-wrap:anywhere]">{title}</span>
                                                    </button>
                                                </li>
                                            ))}
                                        </ol>
                                    </div>
                                ))}
                            </div>
                        </aside>
                        <ProjectionPreview key={songIndex} title={song.title} slides={song.slides} heading={song.title} className="min-w-0" showNotes={false} />
                    </div>
                )}
            </main>
        </Layout>
    );
};
