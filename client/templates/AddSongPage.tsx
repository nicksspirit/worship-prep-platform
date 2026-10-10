import React from "react";
import {CSRFToken, reverse} from "@reactivated";
import {Layout} from "../Layout";

type Props = {
    title: string;
    song_title: string;
    action_url: string;
    song_url: string;
    service_date: string;
    section: string;
    sections: {value: string; label: string}[];
    errors: Record<string, string[]>;
};

export const Template = (props: Props) => (
    <Layout title={props.title}>
        <main className="mx-auto max-w-3xl px-6 py-12 sm:py-20">
            <a href={props.song_url} className="inline-flex min-h-11 items-center text-sm underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-chapel-primary-500">← Back to song</a>
            <h1 className="mt-10 break-words text-4xl sm:text-5xl">Add to song cart</h1>
            <p className="mt-5 break-words font-serif text-3xl">{props.song_title}</p>
            <p className="mt-6 max-w-lg leading-7 text-chapel-neutral-700">Choose the service date and where this song belongs. This saves a draft; the Technical Team is notified when you submit your selection.</p>
            {props.errors.__all__ && <p role="alert" className="mt-6 border border-chapel-primary-300 bg-chapel-primary-50 p-4 text-chapel-primary-800">{props.errors.__all__.join(" ")}</p>}
            <form method="post" action={props.action_url} className="mt-10 border-t border-chapel-neutral-300 pt-8">
                <CSRFToken />
                <div className="grid gap-8 sm:grid-cols-2">
                    <div>
                        <label htmlFor="service-date" className="block text-sm font-bold">Service date</label>
                        <input id="service-date" type="date" name="service_date" required defaultValue={props.service_date} aria-invalid={Boolean(props.errors.service_date)} aria-describedby={props.errors.service_date ? "service-date-help service-date-error" : "service-date-help"} className="mt-3 min-h-11 w-full min-w-0 border border-chapel-neutral-400 bg-white p-3 text-base focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-chapel-primary-500" />
                        <p id="service-date-help" className="mt-2 text-sm text-chapel-neutral-700">Sunday or any other service day.</p>
                        {props.errors.service_date && <p id="service-date-error" role="alert" className="mt-2 text-sm text-chapel-primary-500">{props.errors.service_date.join(" ")}</p>}
                    </div>
                    <div>
                        <label htmlFor="service-section" className="block text-sm font-bold">Service section</label>
                        <select id="service-section" name="section" defaultValue={props.section} required aria-invalid={Boolean(props.errors.section)} aria-describedby={props.errors.section ? "service-section-error" : undefined} className="mt-3 min-h-11 w-full border border-chapel-neutral-400 bg-white p-3 text-base focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-chapel-primary-500">
                            {props.sections.map((section) => <option key={section.value} value={section.value}>{section.label}</option>)}
                        </select>
                        {props.errors.section && <p id="service-section-error" role="alert" className="mt-2 text-sm text-chapel-primary-500">{props.errors.section.join(" ")}</p>}
                    </div>
                </div>
                <div className="mt-10 flex flex-wrap items-center gap-6">
                    <button type="submit" className="border border-chapel-neutral-950 bg-chapel-neutral-950 px-8 py-4 text-sm font-bold text-white hover:bg-chapel-primary-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-chapel-primary-500">Add song</button>
                    <a href={reverse("song_carts:list")} className="inline-flex min-h-11 items-center text-sm underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-chapel-primary-500">My submissions</a>
                </div>
            </form>
        </main>
    </Layout>
);
