import React from "react";
import {CSRFToken, reverse} from "@reactivated";
import {Layout} from "../Layout";
import {ProjectionPreview, type ProjectionSlide} from "../components/ProjectionPreview";

type Props = {
    title: string;
    song_title: string;
    lyrics: string;
    service_date: string;
    date_label: string | null;
    section: string;
    sections: {value: string; label: string}[];
    action_url: string;
    cart_url: string | null;
    can_edit: boolean;
    reviewed: boolean;
    review_url: string | null;
    fingerprint: string;
    errors: Record<string, string[]>;
    slides: ProjectionSlide[];
    formatted_text: string;
};

export const Template = (props: Props) => {
    const [songTitle, setSongTitle] = React.useState(props.song_title);
    const [lyrics, setLyrics] = React.useState(props.lyrics);
    const [serviceDate, setServiceDate] = React.useState(props.service_date);
    const [section, setSection] = React.useState(props.section);
    const changed = songTitle !== props.song_title || lyrics !== props.lyrics || serviceDate !== props.service_date || section !== props.section;
    const fieldClass = "mt-3 min-h-11 w-full min-w-0 border border-chapel-neutral-400 bg-white p-3 text-base focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-chapel-primary-500";
    const buttonClass = "inline-flex min-h-11 items-center justify-center border border-chapel-neutral-950 bg-chapel-neutral-950 px-6 py-4 text-sm font-bold text-white hover:bg-chapel-primary-500 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-chapel-primary-500";
    const generalErrors = [...(props.errors.__all__ || []), ...(props.errors.fingerprint || [])];
    const sectionLabel = props.sections.find((choice) => choice.value === props.section)?.label || props.section;

    return (
        <Layout title={props.title}>
            <main className="mx-auto max-w-6xl px-6 py-12 sm:py-20">
                <a href={props.cart_url || reverse("catalog:search")} className="inline-flex min-h-11 items-center text-sm underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-chapel-primary-500">{props.cart_url ? "← Back to song cart" : "← Back to song search"}</a>
                <header className="mt-8 max-w-3xl">
                    <h1 className="text-4xl sm:text-5xl">{props.can_edit ? props.cart_url ? "Review unlisted song" : "Add an unlisted song" : "Unlisted song"}</h1>
                    <p className="mt-5 leading-7 text-chapel-neutral-700">{props.can_edit ? "Paste the lyrics for a song that is missing from the catalog. Save it to your draft, then review its projection slides before submitting your selection." : "This selection has been submitted. The song and lyrics are locked; use the submission’s comment thread to request a change."}</p>
                </header>
                {generalErrors.length > 0 && <p role="alert" className="mt-6 border border-chapel-primary-300 bg-chapel-primary-50 p-4 text-chapel-primary-800">{generalErrors.join(" ")}</p>}
                {props.can_edit ? (
                    <form method="post" action={props.action_url} className="mt-10 border-t border-chapel-neutral-300 pt-8">
                        <CSRFToken />
                        <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_18rem] lg:gap-12">
                            <div className="min-w-0 space-y-7">
                                <div>
                                    <label htmlFor="unlisted-title" className="block text-sm font-bold">Song title</label>
                                    <input id="unlisted-title" name="title" required maxLength={512} value={songTitle} onChange={(event) => setSongTitle(event.currentTarget.value)} aria-invalid={Boolean(props.errors.title)} aria-describedby={props.errors.title ? "unlisted-title-error" : undefined} className={fieldClass} />
                                    {props.errors.title && <p id="unlisted-title-error" role="alert" className="mt-2 text-sm text-chapel-primary-700">{props.errors.title.join(" ")}</p>}
                                </div>
                                <div>
                                    <label htmlFor="unlisted-lyrics" className="block text-sm font-bold">Lyrics</label>
                                    <p id="unlisted-lyrics-help" className="mt-2 text-sm leading-6 text-chapel-neutral-700">Paste the complete lyrics. Keep verses and choruses separated by blank lines. Words stay in their original order.</p>
                                    <textarea id="unlisted-lyrics" name="lyrics" required maxLength={20000} rows={12} value={lyrics} onChange={(event) => setLyrics(event.currentTarget.value)} aria-invalid={Boolean(props.errors.lyrics)} aria-describedby={props.errors.lyrics ? "unlisted-lyrics-help unlisted-lyrics-error" : "unlisted-lyrics-help"} className={`${fieldClass} resize-y leading-7`} />
                                    {props.errors.lyrics && <p id="unlisted-lyrics-error" role="alert" className="mt-2 text-sm text-chapel-primary-700">{props.errors.lyrics.join(" ")}</p>}
                                </div>
                            </div>
                            <div className="min-w-0 space-y-7">
                                <div>
                                    {props.cart_url ? <>
                                        <p className="text-sm font-bold">Service date</p>
                                        <p className="mt-3 text-base"><time dateTime={props.service_date}>{props.date_label || props.service_date}</time></p>
                                        <input type="hidden" name="service_date" value={props.service_date} />
                                        <p className="mt-2 text-sm leading-6 text-chapel-neutral-700">This song belongs to the cart for this service date.</p>
                                    </> : <>
                                        <label htmlFor="unlisted-service-date" className="block text-sm font-bold">Service date</label>
                                        <input id="unlisted-service-date" type="date" name="service_date" required value={serviceDate} onChange={(event) => setServiceDate(event.currentTarget.value)} aria-invalid={Boolean(props.errors.service_date)} aria-describedby={props.errors.service_date ? "unlisted-date-error" : undefined} className={fieldClass} />
                                    </>}
                                    {props.errors.service_date && <p id="unlisted-date-error" role="alert" className="mt-2 text-sm text-chapel-primary-700">{props.errors.service_date.join(" ")}</p>}
                                </div>
                                <div>
                                    <label htmlFor="unlisted-section" className="block text-sm font-bold">Service section</label>
                                    <select id="unlisted-section" name="section" required value={section} onChange={(event) => setSection(event.currentTarget.value)} aria-invalid={Boolean(props.errors.section)} aria-describedby={props.errors.section ? "unlisted-section-error" : undefined} className={fieldClass}>
                                        {props.sections.map((choice) => <option key={choice.value} value={choice.value}>{choice.label}</option>)}
                                    </select>
                                    {props.errors.section && <p id="unlisted-section-error" role="alert" className="mt-2 text-sm text-chapel-primary-700">{props.errors.section.join(" ")}</p>}
                                </div>
                                <p className="text-sm leading-6 text-chapel-neutral-700">Add preparation instructions in the {props.cart_url ? <a href={`${props.cart_url}#comments-heading`} className="font-medium text-chapel-primary-600 underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-chapel-primary-500">cart’s comment thread</a> : "cart’s comment thread after saving this song"}.</p>
                            </div>
                        </div>
                        <button type="submit" className={`mt-8 ${buttonClass}`}>{changed && props.slides.length > 0 ? "Save and preview your changes" : "Save and preview"}</button>
                    </form>
                ) : (
                    <section aria-labelledby="saved-song-heading" className="mt-10 border-t border-chapel-neutral-300 pt-8">
                        <h2 id="saved-song-heading" className="break-words text-3xl">{props.song_title}</h2>
                        <p className="mt-3 text-sm text-chapel-neutral-700">{props.date_label || props.service_date} · {sectionLabel} · {props.reviewed ? "Lyrics reviewed" : "Review needed"}</p>
                        <details className="mt-6">
                            <summary className="w-fit cursor-pointer py-3 text-sm font-bold text-chapel-primary-600 underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-chapel-primary-500">View original lyrics</summary>
                            <p className="mt-4 max-w-3xl whitespace-pre-wrap break-words leading-7">{props.lyrics}</p>
                        </details>
                    </section>
                )}
                {props.can_edit && changed && props.slides.length > 0 && <p role="status" className="mt-8 border border-chapel-neutral-300 bg-chapel-neutral-100 p-5 leading-7">You have unsaved changes. Save and preview your changes to see the updated slides and mark these lyrics reviewed.</p>}
                {!changed && props.slides.length > 0 && <>
                    {props.can_edit && <p role="status" className="mt-8 border border-chapel-neutral-300 bg-chapel-neutral-100 p-5 leading-7">{props.reviewed ? "Lyrics reviewed. This song can be included when you submit your selection." : "Saved to your draft. Review every slide and the formatted lyrics below, then mark the lyrics reviewed before submitting."}</p>}
                    <ProjectionPreview title={props.song_title} slides={props.slides} />
                    <section aria-labelledby="formatted-lyrics-heading" className="mt-10 border-t border-chapel-neutral-300 pt-8">
                        <h2 id="formatted-lyrics-heading" className="text-3xl">Formatted lyrics</h2>
                        <p id="formatted-lyrics-help" className="mt-4 max-w-2xl text-sm leading-6 text-chapel-neutral-700">This is the prepared text for the Technical Team. You can select and copy it.{props.can_edit ? " To change the words or line breaks, edit the original lyrics above and save again." : " The submitted lyrics are locked."}</p>
                        <label htmlFor="formatted-lyrics" className="sr-only">Prepared projection lyrics</label>
                        <textarea id="formatted-lyrics" readOnly rows={10} value={props.formatted_text} aria-describedby="formatted-lyrics-help" className={`${fieldClass} resize-y leading-7`} />
                        {props.can_edit && !props.reviewed && props.review_url && <form method="post" action={props.review_url} className="mt-6"><CSRFToken /><input type="hidden" name="fingerprint" value={props.fingerprint} /><button type="submit" className={buttonClass}>Mark lyrics reviewed</button></form>}
                        {props.cart_url && <a href={props.cart_url} className="mt-5 inline-flex min-h-11 items-center text-sm font-bold text-chapel-primary-600 underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-chapel-primary-500">Back to song cart →</a>}
                    </section>
                </>}
            </main>
        </Layout>
    );
};
