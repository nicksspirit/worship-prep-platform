import React from "react";
import {reverse} from "@reactivated";
import {Layout} from "../Layout";

type Props = {
    title: string;
    carts: {url: string; service_date: string; date_label: string; status: string; song_count: number; submitted_at_label: string | null}[];
    status_filter: string;
    sort: string;
    filter_url: string;
    error: string | null;
};

export const Template = (props: Props) => (
    <Layout title={props.title}>
        <main className="mx-auto max-w-6xl px-6 py-12 sm:py-20">
            <header className="flex flex-wrap items-end justify-between gap-6 border-b border-chapel-neutral-950 pb-8">
                <div>
                    <h1 className="text-4xl sm:text-5xl">My submissions</h1>
                    <p className="mt-5 max-w-xl leading-7 text-chapel-neutral-700">Your song selections for each service day. Finish a draft or see whether the Technical Team has seen a submitted selection.</p>
                </div>
                <a href={reverse("catalog:search")} className="inline-flex min-h-11 items-center border border-chapel-neutral-950 px-5 py-3 text-sm font-bold hover:bg-chapel-neutral-950 hover:text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-chapel-primary-500">Find songs</a>
            </header>
            {props.error && <p role="alert" className="mt-6 border border-chapel-primary-300 bg-chapel-primary-50 p-4 text-chapel-primary-800">{props.error}</p>}
            <form method="get" action={props.filter_url} className="flex flex-wrap items-end gap-4 py-8">
                <div className="min-w-0 w-full sm:w-auto">
                    <label htmlFor="submission-status" className="block text-sm font-bold">Status</label>
                    <select id="submission-status" name="status" defaultValue={props.status_filter} className="mt-2 min-h-11 w-full border border-chapel-neutral-400 bg-white px-3 py-2 text-base focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-chapel-primary-500 sm:w-44">
                        <option value="">All statuses</option>
                        <option value="draft">Draft</option>
                        <option value="pending">Pending</option>
                        <option value="confirmed">Confirmed</option>
                        <option value="rejected">Rejected</option>
                    </select>
                </div>
                <div className="min-w-0 w-full sm:w-auto">
                    <label htmlFor="submission-sort" className="block text-sm font-bold">Sort by</label>
                    <select id="submission-sort" name="sort" defaultValue={props.sort} className="mt-2 min-h-11 w-full border border-chapel-neutral-400 bg-white px-3 py-2 text-base focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-chapel-primary-500 sm:w-64">
                        <option value="service_date_desc">Service date: newest first</option>
                        <option value="service_date_asc">Service date: oldest first</option>
                        <option value="submitted_desc">Most recently submitted</option>
                    </select>
                </div>
                <button type="submit" className="min-h-11 border border-chapel-neutral-950 bg-chapel-neutral-950 px-5 py-3 text-sm font-bold text-white hover:bg-chapel-primary-500 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-chapel-primary-500">Apply filters</button>
                {props.status_filter && <a href={props.filter_url} className="inline-flex min-h-11 items-center text-sm underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-chapel-primary-500">Clear filters</a>}
            </form>
            {props.carts.length === 0 ? (
                <section className="border-t border-chapel-neutral-300 py-12">
                    <h2 className="text-3xl">{props.status_filter ? "No submissions with this status." : "Start with a song."}</h2>
                    <p className="mt-4 max-w-lg leading-7 text-chapel-neutral-700">{props.status_filter ? "Choose another status or clear the filter to see your other selections." : "Find a song in the catalog and choose “Add to song cart”. Your draft will appear here as soon as you add a song."}</p>
                    <a href={props.status_filter ? props.filter_url : reverse("catalog:search")} className="mt-6 inline-flex min-h-11 items-center font-bold text-chapel-primary-600 underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-chapel-primary-500">{props.status_filter ? "View all submissions" : "Search the song catalog"}</a>
                </section>
            ) : (
                <table className="w-full border-collapse text-left text-sm">
                    <caption className="sr-only">Your song selections, filtered by status and sorted by your chosen order.</caption>
                    <thead className="border-y border-chapel-neutral-300 bg-chapel-neutral-100 text-chapel-neutral-700">
                        <tr>
                            <th scope="col" className="py-4 pr-3 pl-3 font-bold sm:pl-4">Service date</th>
                            <th scope="col" className="hidden px-3 py-4 font-bold sm:table-cell">Songs</th>
                            <th scope="col" className="px-3 py-4 font-bold">Status</th>
                            <th scope="col" className="hidden px-3 py-4 font-bold lg:table-cell">Submitted</th>
                            <th scope="col" className="py-4 pr-3 pl-3 font-bold sm:pr-4"><span className="sr-only">Open submission</span></th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-chapel-neutral-300 border-b border-chapel-neutral-300">
                        {props.carts.map((cart) => (
                            <tr key={cart.url} className="hover:bg-chapel-neutral-100/70">
                                <th scope="row" className="py-5 pr-3 pl-3 font-normal sm:pl-4">
                                    <time dateTime={cart.service_date} className="font-medium">{cart.date_label}</time>
                                    <p className="mt-2 font-normal text-chapel-neutral-700 sm:hidden">{cart.song_count} {cart.song_count === 1 ? "song" : "songs"}</p>
                                    {cart.submitted_at_label && <p className="mt-2 text-xs font-normal text-chapel-neutral-700 lg:hidden">Submitted {cart.submitted_at_label}</p>}
                                </th>
                                <td className="hidden px-3 py-5 tabular-nums sm:table-cell">{cart.song_count}</td>
                                <td className={`px-3 py-5 font-medium capitalize ${cart.status === "rejected" ? "text-chapel-primary-600" : "text-chapel-neutral-800"}`}>{cart.status}</td>
                                <td className="hidden px-3 py-5 text-chapel-neutral-700 lg:table-cell">{cart.submitted_at_label || "Not submitted"}</td>
                                <td className="py-5 pr-3 pl-3 text-right sm:pr-4">
                                    <a href={cart.url} aria-label={`View ${cart.date_label} ${cart.status} submission`} className="inline-flex min-h-11 items-center font-bold text-chapel-primary-600 underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-chapel-primary-500">View</a>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            )}
        </main>
    </Layout>
);
