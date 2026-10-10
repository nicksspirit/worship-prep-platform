import React from "react";
import {Context, CSRFToken} from "@reactivated";
import {Layout} from "../Layout";

type Field = {
    label?: string;
    help_text?: string | null;
    required?: boolean;
    widget?: {
        name: string;
        is_hidden?: boolean;
        value?: string | boolean | number | string[] | null;
        attrs?: {id?: string; placeholder?: string};
        type?: string | null;
    };
};

type Form = {
    fields: Record<string, Field>;
    errors?: Record<string, string[]>;
    iterator?: string[];
};

type Props = {
    title: string;
    page: "verification-sent" | "confirm-email" | "confirm-email-invalid" | "inactive" | "login-code";
    email: string | null;
    user_display: string | null;
    action_url: string | null;
    email_url: string | null;
    recipient: string | null;
    verify_form: Form | null;
    can_resend: boolean;
    cancel_url: string | null;
    logout_url: string | null;
    login_url: string | null;
    redirect_field: {name: string; value: string} | null;
    can_change: boolean;
    change_form: Form | null;
};

const pageCopy = {
    "verification-sent": {
        heading: "Check your inbox",
        body: "We sent you an email verification link. Follow it to finish setting up your account. Check your spam folder if you don’t see it soon.",
    },
    inactive: {heading: "Account inactive", body: "This account is inactive. Contact your administrator for help."},
} as const;

export const Template = (props: Props) => {
    const {messages} = React.useContext(Context);

    return (
        <Layout title={props.title}>
            <main className="mx-auto min-h-[calc(100vh-5rem)] w-full max-w-5xl px-6 py-16 text-chapel-neutral-950 sm:px-12 lg:py-24">
                <div className="max-w-3xl">
                    {props.page === "confirm-email" ? (
                        <>
                            <h1 className="font-serif text-5xl leading-none tracking-tight sm:text-6xl">Confirm email address</h1>
                            <p className="mt-5 max-w-2xl text-base leading-relaxed text-chapel-neutral-700">
                                Confirm that <a className="font-medium underline underline-offset-4" href={`mailto:${props.email ?? ""}`}>{props.email}</a> belongs to {props.user_display}.
                            </p>
                            <form action={props.action_url ?? ""} method="post" className="mt-10 flex flex-col items-start gap-5 border-t border-chapel-neutral-300 pt-8">
                                <CSRFToken />
                                {props.redirect_field && <input type="hidden" name={props.redirect_field.name} value={props.redirect_field.value} />}
                                <button type="submit" className="minimal-btn min-w-52">Confirm email</button>
                            </form>
                        </>
                    ) : props.page === "confirm-email-invalid" ? (
                        <>
                            <h1 className="font-serif text-5xl leading-none tracking-tight sm:text-6xl">Link expired or invalid</h1>
                            <p className="mt-5 max-w-2xl text-base leading-relaxed text-chapel-neutral-700">This email confirmation link has expired or is invalid. Request a new confirmation email to continue.</p>
                            <a href={props.email_url ?? ""} className="minimal-btn mt-10 inline-flex">Request a new link</a>
                        </>
                    ) : props.page === "login-code" ? (
                        <>
                            <h1 className="font-serif text-5xl leading-none tracking-tight sm:text-6xl">Enter sign-in code</h1>
                            <p className="mt-5 max-w-2xl text-base leading-relaxed text-chapel-neutral-700">We sent a code to <span className="font-medium">{props.recipient}</span>. It expires shortly, so enter it soon.</p>
                            {messages.length > 0 && <MessageList messages={messages} />}
                            {props.verify_form && <form action={props.action_url ?? ""} method="post" className="mt-10 max-w-xl space-y-8 border-t border-chapel-neutral-300 pt-8">
                                <CSRFToken />
                                {props.redirect_field && <input type="hidden" name={props.redirect_field.name} value={props.redirect_field.value} />}
                                <FormFields form={props.verify_form} />
                                <div className="flex flex-wrap items-center gap-4">
                                    <button type="submit" className="minimal-btn min-w-52">Confirm</button>
                                    {props.can_resend && <button type="submit" form="resend-code" className="minimal-btn-outline">Request new code</button>}
                                    {props.cancel_url ? <a href={props.cancel_url} className="text-xs font-bold uppercase tracking-widest text-chapel-neutral-600 underline underline-offset-4 transition-colors hover:text-chapel-primary-500">Cancel</a> : <button type="submit" form="cancel-code" className="text-xs font-bold uppercase tracking-widest text-chapel-neutral-600 underline underline-offset-4 transition-colors hover:text-chapel-primary-500">Cancel</button>}
                                </div>
                            </form>}
                            {props.can_resend && <form id="resend-code" action={props.action_url ?? ""} method="post"><CSRFToken />{props.redirect_field && <input type="hidden" name={props.redirect_field.name} value={props.redirect_field.value} />}<input type="hidden" name="action" value="resend" /></form>}
                            {!props.cancel_url && props.logout_url && <form id="cancel-code" action={props.logout_url} method="post"><CSRFToken /><input type="hidden" name="next" value={props.login_url ?? ""} /></form>}
                            {props.can_change && props.change_form && (
                                <details className="mt-10 max-w-xl border-t border-chapel-neutral-300 pt-6" open={Object.keys(props.change_form.errors ?? {}).length > 0 || undefined}>
                                    <summary className="cursor-pointer font-serif text-2xl">Change destination</summary>
                                    <form action={props.action_url ?? ""} method="post" className="mt-6 space-y-8">
                                        <CSRFToken />
                                        {props.redirect_field && <input type="hidden" name={props.redirect_field.name} value={props.redirect_field.value} />}
                                        <input type="hidden" name="action" value="change" />
                                        <FormFields form={props.change_form} />
                                        <button type="submit" className="minimal-btn min-w-52">Update</button>
                                    </form>
                                </details>
                            )}
                        </>
                    ) : (
                        <>
                            <h1 className="font-serif text-5xl leading-none tracking-tight sm:text-6xl">{pageCopy[props.page].heading}</h1>
                            <p className="mt-5 max-w-2xl text-base leading-relaxed text-chapel-neutral-700">{pageCopy[props.page].body}</p>
                            {messages.length > 0 && <MessageList messages={messages} />}
                        </>
                    )}
                </div>
            </main>
        </Layout>
    );
};

function MessageList({messages}: {messages: {message: string}[]}) {
    return <div className="mt-8 space-y-2" aria-live="polite">{messages.map((message, index) => <p key={index} className="border border-chapel-neutral-300 bg-chapel-neutral-100 p-4 text-sm font-medium">{message.message}</p>)}</div>;
}

function FormFields({form}: {form: Form}) {
    const fields = form.iterator ?? Object.keys(form.fields);
    return <>
        {fields.map((name) => {
            const field = form.fields[name];
            const widget = field?.widget;
            if (!widget) return null;
            const id = widget.attrs?.id ?? widget.name;
            const errors = form.errors?.[name] ?? [];
            if (widget.is_hidden) return <input key={name} type="hidden" name={widget.name} value={formValue(widget.value)} />;
            return <div key={name} className="relative group">
                <label htmlFor={id} className="block text-[10px] font-bold uppercase tracking-[0.2em] text-chapel-neutral-600 transition-colors group-focus-within:text-chapel-primary-500">{field.label ?? name}</label>
                <input id={id} type={widget.type ?? "text"} name={widget.name} defaultValue={formValue(widget.value)} placeholder={widget.attrs?.placeholder ?? ""} required={field.required} aria-invalid={errors.length > 0 || undefined} aria-describedby={errors.length ? `${id}-errors` : undefined} className={`minimal-input ${errors.length ? "border-chapel-danger-700 text-chapel-danger-700" : ""}`} />
                {field.help_text && <p className="mt-2 text-sm leading-relaxed text-chapel-neutral-600">{field.help_text}</p>}
                {errors.length > 0 && <ul id={`${id}-errors`} className="mt-2 space-y-1 text-sm font-medium text-chapel-danger-700" role="alert">{errors.map((error, index) => <li key={index}>{error}</li>)}</ul>}
            </div>;
        })}
        {(form.errors?.__all__ ?? []).map((error, index) => <p key={index} role="alert" className="border border-chapel-danger-700 bg-chapel-danger-50 p-4 text-sm font-medium text-chapel-danger-800">{error}</p>)}
    </>;
}

function formValue(value: string | boolean | number | string[] | null | undefined) {
    if (Array.isArray(value)) return value.join(", ");
    return typeof value === "string" || typeof value === "number" ? String(value) : "";
}
