import React from "react";

import {Layout} from "../Layout";

type EmptyState = {
    heading: string;
    message: string;
    link_url: string | null;
    link_label: string | null;
};

type ScheduleSummary = {
    date: string;
    display_date: string;
    title: string;
    item_count: number;
    preview_url: string;
    status: string;
    status_label: string;
};

type ScheduleListPageProps = {
    title: string;
    schedules: ScheduleSummary[];
    empty_state: EmptyState | null;
};

const cardBorder = "rgba(226, 232, 240, 0.12)";

export const Template = (props: ScheduleListPageProps) => {
    return (
        <Layout title={props.title}>
            <div className="min-h-screen bg-slate-950 text-slate-100">
                <div className="mx-auto flex max-w-7xl flex-col gap-10 px-4 py-8 sm:px-6 lg:px-8">
                    <section
                        className="overflow-hidden rounded-[2rem] border p-8 shadow-2xl"
                        style={{
                            borderColor: cardBorder,
                            background:
                                "radial-gradient(circle at top right, rgba(230, 126, 34, 0.28), transparent 32%), linear-gradient(135deg, rgba(15, 23, 42, 0.98), rgba(30, 58, 138, 0.88) 58%, rgba(157, 30, 44, 0.9))",
                        }}
                    >
                        <div className="grid gap-8 lg:grid-cols-[1.4fr_0.8fr]">
                            <div className="space-y-5">
                                <p className="text-sm font-semibold uppercase tracking-[0.35em] text-orange-200/90">
                                    Chapel of Mercy
                                </p>
                                <div className="space-y-3">
                                    <h1 className="max-w-3xl text-4xl font-black tracking-tight text-white sm:text-5xl">
                                        Service schedule previews for ministers, choir, and the
                                        booth.
                                    </h1>
                                    <p className="max-w-2xl text-base leading-7 text-slate-200/85">
                                        Browse ready and published orders of service, then open the
                                        full preview page to review agenda flow and linked worship
                                        songs.
                                    </p>
                                </div>
                            </div>

                            <div className="grid gap-4 rounded-[1.75rem] border border-white/15 bg-slate-950/30 p-5 backdrop-blur">
                                <div>
                                    <p className="text-xs uppercase tracking-[0.3em] text-slate-300/70">
                                        Archive
                                    </p>
                                    <p className="mt-2 text-3xl font-bold text-white">
                                        {props.schedules.length}
                                    </p>
                                    <p className="mt-2 text-sm text-slate-200/80">
                                        Visible service schedules are sorted newest first when no
                                        upcoming service is available.
                                    </p>
                                </div>
                                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
                                    <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                                        <p className="text-xs uppercase tracking-[0.24em] text-orange-200/75">
                                            Sunday School
                                        </p>
                                        <p className="mt-2 text-lg font-semibold text-white">
                                            9:40 AM
                                        </p>
                                    </div>
                                    <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                                        <p className="text-xs uppercase tracking-[0.24em] text-orange-200/75">
                                            Worship Service
                                        </p>
                                        <p className="mt-2 text-lg font-semibold text-white">
                                            10:30 AM
                                        </p>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </section>

                    {props.empty_state ? (
                        <section
                            className="rounded-[2rem] border bg-slate-900/75 p-10 text-center shadow-xl"
                            style={{borderColor: cardBorder}}
                        >
                            <div className="mx-auto max-w-2xl space-y-4">
                                <p className="text-sm font-semibold uppercase tracking-[0.32em] text-orange-300/80">
                                    Schedule Archive
                                </p>
                                <h2 className="text-3xl font-bold text-white">
                                    {props.empty_state.heading}
                                </h2>
                                <p className="text-base leading-7 text-slate-300">
                                    {props.empty_state.message}
                                </p>
                                {props.empty_state.link_url && props.empty_state.link_label ? (
                                    <a
                                        href={props.empty_state.link_url}
                                        className="btn border-0 text-white"
                                        style={{backgroundColor: "var(--chapel-primary-500)"}}
                                    >
                                        {props.empty_state.link_label}
                                    </a>
                                ) : null}
                            </div>
                        </section>
                    ) : (
                        <section className="space-y-5">
                            <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
                                <div>
                                    <p className="text-sm uppercase tracking-[0.3em] text-slate-400">
                                        Schedule Library
                                    </p>
                                    <h2 className="mt-2 text-3xl font-bold text-white">
                                        Past ready and published services
                                    </h2>
                                </div>
                                <p className="max-w-xl text-sm leading-6 text-slate-400">
                                    Open any card to review the full service flow, inspect linked
                                    songs, and prepare for print or booth handoff.
                                </p>
                            </div>

                            <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
                                {props.schedules.map((schedule) => (
                                    <a
                                        key={schedule.date}
                                        href={schedule.preview_url}
                                        className="group flex h-full flex-col justify-between rounded-[1.75rem] border bg-slate-900/80 p-6 shadow-lg transition duration-200 hover:-translate-y-1 hover:border-orange-300/35 hover:bg-slate-900"
                                        style={{borderColor: cardBorder}}
                                    >
                                        <div className="space-y-6">
                                            <div className="flex items-start justify-between gap-4">
                                                <div>
                                                    <p className="text-xs uppercase tracking-[0.3em] text-slate-400">
                                                        {schedule.display_date}
                                                    </p>
                                                    <h3 className="mt-3 text-2xl font-bold text-white">
                                                        {schedule.title}
                                                    </h3>
                                                </div>
                                                {schedule.status !== "published" ? (
                                                    <span
                                                        className="rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.22em]"
                                                        style={{
                                                            backgroundColor:
                                                                "rgba(230, 126, 34, 0.14)",
                                                            color: "var(--worship-accent-300)",
                                                        }}
                                                    >
                                                        {schedule.status_label}
                                                    </span>
                                                ) : null}
                                            </div>

                                            <div className="grid gap-3 sm:grid-cols-2">
                                                <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                                                    <p className="text-xs uppercase tracking-[0.28em] text-slate-400">
                                                        Agenda Items
                                                    </p>
                                                    <p className="mt-2 text-2xl font-semibold text-white">
                                                        {schedule.item_count}
                                                    </p>
                                                </div>
                                                <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                                                    <p className="text-xs uppercase tracking-[0.28em] text-slate-400">
                                                        Status
                                                    </p>
                                                    <p className="mt-2 text-lg font-semibold text-white">
                                                        {schedule.status_label}
                                                    </p>
                                                </div>
                                            </div>
                                        </div>

                                        <div className="mt-8 flex items-center justify-between text-sm text-slate-300">
                                            <span>Open preview</span>
                                            <span className="transition group-hover:translate-x-1">
                                                →
                                            </span>
                                        </div>
                                    </a>
                                ))}
                            </div>
                        </section>
                    )}
                </div>
            </div>
        </Layout>
    );
};
