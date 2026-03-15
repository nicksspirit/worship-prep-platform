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

export const Template = (props: ScheduleListPageProps) => {
    return (
        <Layout title={props.title}>
            <div className="min-h-screen bg-chapel-neutral-50 text-chapel-neutral-950">
                <main className="px-6 lg:px-12 py-16 lg:py-24 max-w-[1400px] mx-auto">
                    {/* Editorial Header Section */}
                    <div className="mb-16 flex flex-col lg:flex-row lg:items-end justify-between gap-12 border-b border-chapel-neutral-300 pb-12">
                        <div className="max-w-3xl">
                            <p className="text-xs font-bold uppercase tracking-[0.2em] text-chapel-secondary-500 mb-6">
                                Service Agendas
                            </p>
                            <h1 className="font-serif text-[3.5rem] lg:text-[5rem] leading-[0.95] tracking-tight text-chapel-neutral-950">
                                Orchestrating the <br />
                                <span className="italic text-chapel-neutral-500">Divine Flow.</span>
                            </h1>
                        </div>
                        
                        <div className="flex gap-16 lg:pb-2">
                            <div>
                                <p className="text-[10px] font-bold uppercase tracking-widest text-chapel-neutral-500 mb-2">Total Archives</p>
                                <p className="font-sans text-5xl font-medium tracking-tight text-chapel-neutral-900">{props.schedules.length}</p>
                            </div>
                        </div>
                    </div>

                    {props.empty_state ? (
                        <div className="py-32 flex flex-col items-center justify-center text-center">
                            <h2 className="font-serif text-4xl mb-4 text-chapel-neutral-900">{props.empty_state.heading}</h2>
                            <p className="text-lg text-chapel-neutral-600 max-w-md mb-8">
                                {props.empty_state.message}
                            </p>
                            {props.empty_state.link_url && props.empty_state.link_label && (
                                <a href={props.empty_state.link_url} className="minimal-btn bg-chapel-primary-500 text-white hover:bg-chapel-primary-600 rounded-lg">
                                    {props.empty_state.link_label}
                                </a>
                            )}
                        </div>
                    ) : (
                        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-8">
                            {props.schedules.map((schedule, idx) => {
                                const isPublished = schedule.status === "published";
                                return (
                                    <a
                                        key={schedule.date}
                                        href={schedule.preview_url}
                                        className="group flex flex-col border border-chapel-neutral-300 bg-white hover:border-chapel-secondary-500 hover:shadow-xl transition-all duration-300 overflow-hidden"
                                    >
                                        <div className="p-8 lg:p-10 flex-grow flex flex-col justify-between">
                                            <div>
                                                <div className="flex items-start justify-between mb-8">
                                                    <span className="text-[10px] font-bold uppercase tracking-[0.2em] text-chapel-neutral-400 group-hover:text-chapel-secondary-300 transition-colors">
                                                        No. {String(idx + 1).padStart(3, '0')}
                                                    </span>
                                                    {!isPublished && (
                                                        <span className="text-[10px] font-bold uppercase tracking-widest bg-worship-accent-100 text-worship-accent-950 px-3 py-1 rounded-full group-hover:bg-worship-accent-500 group-hover:text-white transition-colors">
                                                            {schedule.status_label}
                                                        </span>
                                                    )}
                                                </div>
                                                
                                                <h3 className="font-serif text-3xl lg:text-4xl leading-tight mb-4 text-chapel-neutral-900 group-hover:text-chapel-secondary-600 transition-colors">
                                                    {schedule.title}
                                                </h3>
                                                
                                                <p className="text-sm font-medium text-chapel-neutral-500 group-hover:text-chapel-secondary-400 transition-colors tracking-wide">
                                                    {schedule.display_date}
                                                </p>
                                            </div>
                                        </div>

                                        <div className="border-t border-chapel-neutral-200 group-hover:border-chapel-secondary-200 p-6 flex items-center justify-between bg-chapel-neutral-50 group-hover:bg-chapel-secondary-50 transition-colors">
                                            <div>
                                                <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-chapel-neutral-500 group-hover:text-chapel-secondary-500 mb-1 transition-colors">Agenda Items</p>
                                                <p className="font-serif text-2xl text-chapel-neutral-900 group-hover:text-chapel-secondary-600 transition-colors">{schedule.item_count}</p>
                                            </div>
                                            <div className="w-10 h-10 flex items-center justify-center rounded-full bg-chapel-neutral-200 text-chapel-neutral-600 group-hover:bg-chapel-secondary-500 group-hover:text-white transition-colors">
                                                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
                                                </svg>
                                            </div>
                                        </div>
                                    </a>
                                );
                            })}
                        </div>
                    )}
                </main>

                <footer className="border-t border-chapel-neutral-300 py-12 px-6 lg:px-12 text-center text-xs font-bold uppercase tracking-[0.2em] text-chapel-neutral-500 bg-white">
                    Redeemed Christian Church of God • Chapel of Mercy
                </footer>
            </div>
        </Layout>
    );
};
