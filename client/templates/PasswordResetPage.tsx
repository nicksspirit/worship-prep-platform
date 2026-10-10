import React from "react";
import {Context, CSRFToken} from "@reactivated";
import {Layout} from "../Layout";

type ResetField = {
    label?: string;
    widget?: {
        name: string;
        is_hidden?: boolean;
        value?: string | boolean | number | string[] | null;
        attrs?: {id?: string; placeholder?: string};
        type?: string;
        tag?: string;
    };
};

type Props = {
    title: string;
    step: "request" | "sent" | "set" | "invalid" | "complete";
    form?: {
        fields?: Record<string, ResetField>;
        errors?: Record<string, string[]> | null;
        iterator?: string[];
    } | null;
    sign_in_url: string;
    reset_url: string;
};

const copy = {
    request: {
        heading: "Reset your password",
        body: "Enter the email address connected to your account. We’ll send instructions if it matches an active account.",
        button: "Send reset instructions",
    },
    sent: {
        heading: "Check your inbox",
        body: "If an active account uses that address, a password reset email is on its way. Check your spam folder if it doesn’t arrive soon.",
    },
    set: {
        heading: "Choose a new password",
        body: "Set a new password for your account. Use a password you have not used here before.",
        button: "Update password",
    },
    invalid: {
        heading: "This reset link has expired",
        body: "Password reset links can only be used once and expire for your security. Request a new link to continue.",
        button: "Request a new link",
    },
    complete: {
        heading: "Password updated",
        body: "Your password has been changed. Sign in with your new password to continue.",
        button: "Return to sign in",
    },
} as const;

export const Template = (props: Props) => {
    const {messages} = React.useContext(Context);
    const content = copy[props.step];
    const actionLabel = "button" in content ? content.button : "";
    const fieldMap = props.form?.fields ?? {};
    const fields = (props.form?.iterator ?? Object.keys(fieldMap))
        .map((name) => ({name, field: fieldMap[name]}))
        .filter((entry): entry is {name: string; field: ResetField} => entry.field != null);
    const errors = props.form?.errors ?? {};

    return (
        <Layout title={props.title} signedOutHeaderLink="song-search">
            <main className="flex min-h-[calc(100vh-5rem)] w-full flex-col overflow-hidden bg-chapel-neutral-50 text-chapel-neutral-950 lg:flex-row">
                <aside className="bg-grain relative flex w-full flex-col justify-between border-b border-chapel-neutral-950 bg-chapel-neutral-200 px-8 py-12 lg:w-[45%] lg:border-b-0 lg:border-r lg:p-16">
                    <div className="relative z-10 pt-8 lg:pt-16">
                        <h1 className="mb-8 font-serif text-[4rem] leading-[0.9] tracking-tight lg:text-[6rem]">
                            Worship <br />
                            <span className="italic text-chapel-primary-500">Preparation.</span>
                        </h1>
                        <p className="max-w-sm text-lg font-medium leading-relaxed text-chapel-neutral-700">
                            Secure access keeps your service plans and shared materials in trusted hands.
                        </p>
                    </div>
                    <div className="relative z-10 mt-12 flex items-center justify-between border-t border-chapel-neutral-950/20 pt-6 lg:mt-0">
                        <span className="text-xs font-bold uppercase tracking-widest">Est. 2026</span>
                        <span className="text-xs font-bold uppercase tracking-widest text-chapel-primary-500">Secure Access</span>
                    </div>
                </aside>

                <section className="flex w-full flex-col justify-center bg-chapel-neutral-50 px-8 py-16 lg:w-[55%] lg:px-24 xl:px-32">
                    <div className="mx-auto w-full max-w-lg">
                        <h2 className="mb-5 font-serif text-4xl leading-none tracking-tight">{content.heading}</h2>
                        <p className="max-w-md text-base leading-relaxed text-chapel-neutral-700">{content.body}</p>

                        {messages.length > 0 && (
                            <div className="mt-7 space-y-2" aria-live="polite">
                                {messages.map((message, index) => (
                                    <p key={index} className="border border-chapel-neutral-300 bg-chapel-neutral-100 p-4 text-sm font-medium">
                                        {message.message}
                                    </p>
                                ))}
                            </div>
                        )}

                        {props.step === "request" && props.form && (
                            <form method="post" className="mt-10 space-y-8">
                                <CSRFToken />
                                {fields.filter(({field}) => field.widget?.is_hidden).map(({name, field}) => (
                                    <input key={name} type="hidden" name={field.widget?.name ?? name} value={String(field.widget?.value ?? "")} />
                                ))}
                                {fields.filter(({field}) => !field.widget?.is_hidden).map(({name, field}) => {
                                    const widget = field.widget;
                                    if (!widget) return null;
                                    const error = errors[name]?.[0];
                                    return (
                                        <div key={name}>
                                            <label htmlFor={widget.attrs?.id ?? widget.name} className="mb-1 block text-[10px] font-bold uppercase tracking-[0.2em] text-chapel-neutral-600">
                                                {field.label ?? name}
                                            </label>
                                            <input
                                                id={widget.attrs?.id ?? widget.name}
                                                name={widget.name}
                                                type={widget.type ?? "text"}
                                                defaultValue={typeof widget.value === "string" ? widget.value : ""}
                                                autoComplete="email"
                                                aria-invalid={Boolean(error)}
                                                aria-describedby={error ? `${widget.name}-error` : undefined}
                                                className={`minimal-input ${error ? "border-chapel-danger-700" : ""}`}
                                            />
                                            {error && <p id={`${widget.name}-error`} className="mt-2 text-sm font-medium text-chapel-danger-700">{error}</p>}
                                        </div>
                                    );
                                })}
                                <button type="submit" className="minimal-btn w-full">{actionLabel}</button>
                            </form>
                        )}

                        {props.step === "set" && props.form && (
                            <form method="post" className="mt-10 space-y-8">
                                <CSRFToken />
                                {fields.map(({name, field}) => {
                                    const widget = field.widget;
                                    if (!widget || widget.is_hidden) return null;
                                    const error = errors[name]?.[0];
                                    return (
                                        <div key={name}>
                                            <label htmlFor={widget.attrs?.id ?? widget.name} className="mb-1 block text-[10px] font-bold uppercase tracking-[0.2em] text-chapel-neutral-600">
                                                {field.label ?? name}
                                            </label>
                                            <input
                                                id={widget.attrs?.id ?? widget.name}
                                                name={widget.name}
                                                type="password"
                                                autoComplete="new-password"
                                                aria-invalid={Boolean(error)}
                                                aria-describedby={error ? `${widget.name}-error` : undefined}
                                                className={`minimal-input ${error ? "border-chapel-danger-700" : ""}`}
                                            />
                                            {error && <p id={`${widget.name}-error`} className="mt-2 text-sm font-medium text-chapel-danger-700">{error}</p>}
                                        </div>
                                    );
                                })}
                                {errors.__all__?.[0] && <p role="alert" className="text-sm font-medium text-chapel-danger-700">{errors.__all__.join(" ")}</p>}
                                <button type="submit" className="minimal-btn w-full">{actionLabel}</button>
                            </form>
                        )}

                        {props.step === "invalid" && (
                            <a href={props.reset_url} className="minimal-btn mt-10 w-full">{actionLabel}</a>
                        )}
                        {props.step === "complete" && (
                            <a href={props.sign_in_url} className="minimal-btn mt-10 w-full">{actionLabel}</a>
                        )}
                        {props.step !== "complete" && (
                            <a href={props.sign_in_url} className="mt-8 block text-center text-xs font-bold uppercase tracking-widest text-chapel-neutral-600 transition-colors hover:text-chapel-neutral-950 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-chapel-primary-500">
                                Return to sign in
                            </a>
                        )}
                    </div>
                </section>
            </main>
        </Layout>
    );
};
