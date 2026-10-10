import React from "react";
import {CSRFToken, reverse} from "@reactivated";
import {Layout} from "../Layout";

type Props = {
    title: string;
    service_date: string;
    date_label: string;
    status: string;
    notification_status: string;
    song_count: number;
    sections: {label: string; songs: {id: number; title: string; author: string; song_url: string; remove_url: string}[]}[];
    checkout_url: string;
    error: string | null;
    submitted_at_label: string | null;
    confirmed_at_label: string | null;
    confirmed_by: string | null;
    rejected_at_label: string | null;
    rejected_by: string | null;
    rejection_reason: string;
    comments: {id: number; body: string; created_at_label: string; updated_at_label: string | null; can_edit: boolean; edit_url: string}[];
    comment_url: string;
    comment_body: string;
    comment_errors: string[];
    deliveries: {label: string; status: string}[];
};

export const Template = (props: Props) => {
    const draft = props.status === "draft";
    const confirmed = props.status === "confirmed";
    const rejected = props.status === "rejected";
    return (
        <Layout title={props.title}>
            <main className="mx-auto max-w-6xl px-6 py-12 sm:py-20">
                <a href={reverse("song_carts:list")} className="inline-flex min-h-11 items-center text-sm underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-chapel-primary-500">← My submissions</a>
                <header className="mt-8 border-b border-chapel-neutral-950 pb-8">
                    <div className="flex flex-wrap items-center justify-between gap-4">
                        <h1 className="text-4xl sm:text-5xl">{draft ? "Song cart" : "Song submission"}</h1>
                        <span className={`border px-3 py-2 text-sm font-bold capitalize ${rejected ? "border-chapel-primary-300 bg-chapel-primary-50 text-chapel-primary-700" : "border-chapel-neutral-300 bg-white text-chapel-neutral-800"}`}>{props.status}</span>
                    </div>
                    <p className="mt-5 font-serif text-2xl"><time dateTime={props.service_date}>{props.date_label}</time></p>
                    <p className="mt-3 text-sm text-chapel-neutral-700">{props.song_count} {props.song_count === 1 ? "song" : "songs"}{props.submitted_at_label ? ` · Submitted ${props.submitted_at_label}` : " · Not submitted yet"}</p>
                </header>
                {props.error && <p role="alert" className="mt-6 border border-chapel-primary-300 bg-chapel-primary-50 p-4 text-chapel-primary-800">{props.error}</p>}
                {!draft && (
                    <section aria-label="Submission status" className={`mt-8 border p-5 leading-7 ${rejected ? "border-chapel-primary-300 bg-chapel-primary-50" : "border-chapel-neutral-300 bg-chapel-neutral-100"}`}>
                        <p className="font-bold">{rejected ? "The Technical Team rejected this submission." : confirmed ? "The Technical Team has seen your submission." : "Thank you. We received your submission."}</p>
                        <p className="mt-1 text-chapel-neutral-700">{rejected ? "Your song selection remains saved. You can add a comment below to ask for clarification." : confirmed ? "Confirmed means seen by the team. It does not mean the songs are ready for projection." : "It is pending review by the Technical Team. Your songs are now locked; add a comment below to request a change."}</p>
                        {props.rejection_reason && <p className="mt-4 whitespace-pre-wrap break-words"><span className="font-bold">Reason: </span>{props.rejection_reason}</p>}
                        {(props.confirmed_at_label || props.rejected_at_label) && (
                            <dl className="mt-4 space-y-2 border-t border-chapel-neutral-300 pt-4 text-sm text-chapel-neutral-700">
                                {props.confirmed_at_label && <div><dt className="inline font-bold">First seen: </dt><dd className="inline">{props.confirmed_at_label}{props.confirmed_by ? ` by ${props.confirmed_by}` : ""}</dd></div>}
                                {props.rejected_at_label && <div><dt className="inline font-bold">Rejected: </dt><dd className="inline">{props.rejected_at_label}{props.rejected_by ? ` by ${props.rejected_by}` : ""}</dd></div>}
                            </dl>
                        )}
                    </section>
                )}
                <div className="mt-10 grid gap-10 lg:grid-cols-[minmax(0,1fr)_20rem] lg:gap-12">
                    <div className="min-w-0 space-y-10">
                        {props.sections.map((section, sectionIndex) => (
                            <section key={section.label} aria-labelledby={`section-${sectionIndex}`}>
                                <h2 id={`section-${sectionIndex}`} className="border-b border-chapel-neutral-300 pb-4 text-3xl">{section.label}</h2>
                                {section.songs.length === 0 ? <p className="py-6 text-sm text-chapel-neutral-700">No songs selected.</p> : (
                                    <ol className="divide-y divide-chapel-neutral-300">
                                        {section.songs.map((song, index) => (
                                            <li key={song.id} id={`song-${song.id}`} className="flex items-start gap-3 py-5 sm:gap-4">
                                                <span className="pt-1 text-sm tabular-nums text-chapel-neutral-700" aria-hidden="true">{index + 1}.</span>
                                                <div className="min-w-0 flex-1">
                                                    <a href={song.song_url} className="break-words font-serif text-2xl hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-chapel-primary-500">{song.title}</a>
                                                    {song.author && <p className="mt-1 text-sm text-chapel-neutral-700">{song.author}</p>}
                                                    <p className="mt-2 text-xs tabular-nums text-chapel-neutral-700">Song reference #{song.id}</p>
                                                </div>
                                                {draft && <form method="post" action={song.remove_url}><CSRFToken /><button type="submit" aria-label={`Remove ${song.title} from ${section.label}`} className="min-h-11 px-2 text-sm text-chapel-primary-600 underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-chapel-primary-500">Remove</button></form>}
                                            </li>
                                        ))}
                                    </ol>
                                )}
                            </section>
                        ))}
                    </div>
                    <aside className="self-start border border-chapel-neutral-300 bg-chapel-neutral-100 p-6">
                        <h2 className="text-3xl">{draft ? "Review & submit" : "Your selection"}</h2>
                        <p className="mt-5 text-lg font-bold">{props.song_count} {props.song_count === 1 ? "song" : "songs"}</p>
                        <p className="mt-2 text-sm leading-6 text-chapel-neutral-700">{draft ? "Check the songs and service date before submitting. Submission locks the selection and notifies the Technical Team. You can still add comments afterwards." : "The songs and service date are locked. Use the comment thread to communicate any requested changes."}</p>
                        {draft && <>
                            <form method="post" action={props.checkout_url} className="mt-6"><CSRFToken /><button type="submit" disabled={props.song_count === 0} className="w-full border border-chapel-neutral-950 bg-chapel-neutral-950 px-5 py-4 text-sm font-bold text-white hover:bg-chapel-primary-500 disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-chapel-primary-500">Submit song selection</button></form>
                            {props.song_count === 0 && <p className="mt-3 text-sm text-chapel-neutral-700">Add at least one song to submit.</p>}
                            <a href={reverse("catalog:search")} className="mt-4 inline-flex min-h-11 items-center text-sm font-bold underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-chapel-primary-500">Add another song →</a>
                        </>}
                        {props.deliveries.length > 0 && (
                            <section aria-labelledby="email-delivery-heading" className="mt-6 border-t border-chapel-neutral-300 pt-5">
                                <h3 id="email-delivery-heading" className="font-sans text-sm font-bold">Email delivery</h3>
                                <p className="mt-2 text-xs leading-5 text-chapel-neutral-700">Email delivery is separate from submission status.</p>
                                <ul className="mt-4 space-y-4 text-sm">
                                    {props.deliveries.map((delivery, index) => (
                                        <li key={`${delivery.label}-${index}`}>
                                            <p className="font-medium">{delivery.label}</p>
                                            <p className={`mt-1 ${delivery.status === "failed" ? "text-chapel-primary-700" : "text-chapel-neutral-700"}`}>{delivery.status === "sent" ? "Email sent" : delivery.status === "failed" ? "Email could not be sent. The team can retry delivery." : "Email delivery pending"}</p>
                                        </li>
                                    ))}
                                </ul>
                            </section>
                        )}
                    </aside>
                </div>
                <section aria-labelledby="comments-heading" className="mt-14 max-w-3xl border-t border-chapel-neutral-950 pt-8">
                    <h2 id="comments-heading" className="text-3xl">Comments</h2>
                    <p className="mt-4 max-w-2xl text-sm leading-6 text-chapel-neutral-700">Add instructions or request a change to this submission. Reference a song by its number, such as #123. The Technical Team reads this thread and replies by email.</p>
                    {props.comments.length === 0 ? <p className="mt-6 text-sm text-chapel-neutral-700">No comments yet.</p> : (
                        <ol className="mt-6 divide-y divide-chapel-neutral-300 border-b border-chapel-neutral-300">
                            {props.comments.map((comment) => (
                                <li key={comment.id} id={`comment-${comment.id}`} className="py-6">
                                    <p className="text-sm"><span className="font-bold">You</span><span className="ml-3 text-chapel-neutral-700">{comment.created_at_label}</span></p>
                                    <p className="mt-3 whitespace-pre-wrap break-words leading-7">{comment.body}</p>
                                    {comment.updated_at_label && <p className="mt-2 text-xs text-chapel-neutral-700">Edited {comment.updated_at_label}</p>}
                                    {comment.can_edit ? (
                                        <details className="mt-3">
                                            <summary className="w-fit cursor-pointer py-3 text-sm font-bold text-chapel-primary-600 underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-chapel-primary-500">Edit comment</summary>
                                            <form method="post" action={comment.edit_url} className="mt-2"><CSRFToken />
                                                <label htmlFor={`edit-comment-${comment.id}`} className="block text-sm font-bold">Edit your comment</label>
                                                <textarea id={`edit-comment-${comment.id}`} name="body" required maxLength={5000} rows={4} defaultValue={comment.body} className="mt-3 min-h-28 w-full border border-chapel-neutral-400 bg-white p-3 text-base focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-chapel-primary-500" />
                                                <button type="submit" className="mt-3 min-h-11 border border-chapel-neutral-950 bg-chapel-neutral-950 px-5 py-3 text-sm font-bold text-white hover:bg-chapel-primary-500 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-chapel-primary-500">Save comment</button>
                                            </form>
                                        </details>
                                    ) : <p className="mt-3 text-xs text-chapel-neutral-700">Editing window closed. Add a follow-up below.</p>}
                                </li>
                            ))}
                        </ol>
                    )}
                    <form method="post" action={props.comment_url} className="mt-8"><CSRFToken />
                        <label htmlFor="submission-comment" className="block text-sm font-bold">Add a comment</label>
                        <p id="comment-help" className="mt-2 text-sm leading-6 text-chapel-neutral-700">Draft comments stay editable until submission. After submitting, each posted comment has a 15-minute editing window. You can always add a follow-up.</p>
                        <textarea id="submission-comment" name="body" required maxLength={5000} rows={4} defaultValue={props.comment_body} aria-invalid={props.comment_errors.length > 0} aria-describedby={props.comment_errors.length > 0 ? "comment-help comment-errors" : "comment-help"} className="mt-3 min-h-28 w-full border border-chapel-neutral-400 bg-white p-3 text-base focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-chapel-primary-500" />
                        {props.comment_errors.length > 0 && <p id="comment-errors" role="alert" className="mt-2 text-sm text-chapel-primary-700">{props.comment_errors.join(" ")}</p>}
                        <button type="submit" className="mt-4 min-h-11 border border-chapel-neutral-950 bg-chapel-neutral-950 px-5 py-3 text-sm font-bold text-white hover:bg-chapel-primary-500 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-chapel-primary-500">Post comment</button>
                    </form>
                </section>
            </main>
        </Layout>
    );
};
