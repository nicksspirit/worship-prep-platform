import React from "react";
import {Context, CSRFToken} from "@reactivated";
import {Layout} from "../Layout";

type Field = {
    label?: string;
    help_text?: string | null;
    help_items?: string[];
    required?: boolean;
    widget?: {
        name: string;
        is_hidden?: boolean;
        value?: string | boolean | number | string[] | null;
        attrs?: {id?: string; placeholder?: string};
        type?: string | null;
        tag?: string;
    };
};

type Form = {
    fields?: Record<string, Field>;
    errors?: Record<string, string[]> | null;
    iterator?: string[];
};

type Props = {
    title: string;
    page: "emails" | "change-password" | "set-password" | "reauthenticate";
    form: Form;
    action_url: string;
    email_addresses?: {email: string; verified: boolean; primary: boolean}[];
    can_add_email?: boolean;
    reset_password_url?: string | null;
    redirect_field?: {name: string; value: string} | null;
    reauthentication_alternatives?: {description: string; url: string}[];
};

const pageCopy = {
    emails: {heading: "Email addresses", description: "Manage the email addresses connected to your account."},
    "change-password": {heading: "Change password", description: "Choose a new password to keep your account secure."},
    "set-password": {heading: "Set password", description: "Add a password so you can sign in with your email address."},
    reauthenticate: {heading: "Confirm access", description: "Enter your password to safeguard your account."},
} as const;

export const Template = (props: Props) => {
    const {messages} = React.useContext(Context);
    const fields = props.form.fields ?? {};
    const orderedFields = (props.form.iterator ?? Object.keys(fields))
        .map((name) => ({name, field: fields[name]}))
        .filter((entry): entry is {name: string; field: Field} => entry.field != null);
    const hiddenFields = orderedFields.filter(({field}) => field.widget?.is_hidden);
    const visibleFields = orderedFields.filter(({field}) => !field.widget?.is_hidden);
    const nonFieldErrors = props.form.errors?.__all__ ?? [];
    const copy = pageCopy[props.page];

    return (
        <Layout title={props.title}>
            <main className="mx-auto min-h-[calc(100vh-5rem)] w-full max-w-5xl px-6 py-16 text-chapel-neutral-950 sm:px-12 lg:py-24">
                <div className="max-w-3xl">
                    <h1 className="font-serif text-5xl leading-none tracking-tight sm:text-6xl">{copy.heading}</h1>
                    <p className="mt-5 max-w-2xl text-base leading-relaxed text-chapel-neutral-700">{copy.description}</p>

                    {messages.length > 0 && (
                        <div className="mt-8 space-y-2" aria-live="polite">
                            {messages.map((message, index) => (
                                <p key={index} className="border border-chapel-neutral-300 bg-chapel-neutral-100 p-4 text-sm font-medium">
                                    {message.message}
                                </p>
                            ))}
                        </div>
                    )}

                    {props.page === "emails" ? (
                        <div className="mt-12 space-y-12">
                            <section className="border-t border-chapel-neutral-300 pt-8" aria-labelledby="email-list-heading">
                                <h2 id="email-list-heading" className="font-serif text-3xl tracking-tight">Your email addresses</h2>
                                {props.email_addresses?.length ? (
                                    <form action={props.action_url} method="post" className="mt-6">
                                        <CSRFToken />
                                        <fieldset className="space-y-3">
                                            <legend className="sr-only">Choose an email address to manage</legend>
                                            {props.email_addresses.map((address, index) => (
                                                <label key={address.email} className="flex cursor-pointer items-center gap-4 border border-chapel-neutral-300 p-5 transition-colors hover:border-chapel-neutral-950 has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-chapel-primary-500">
                                                    <input type="radio" name="email" value={address.email} defaultChecked={address.primary || (props.email_addresses?.length === 1 && index === 0)} className="h-4 w-4 accent-chapel-primary-500" />
                                                    <span className="min-w-0 flex-1">
                                                        <span className="block break-all font-medium">{address.email}</span>
                                                        <span className="mt-2 flex flex-wrap gap-2 text-[10px] font-bold uppercase tracking-[0.14em]">
                                                            {address.primary && <span className="text-chapel-secondary-600">Primary</span>}
                                                            {address.verified ? <span className="text-chapel-success-700">Verified</span> : <span className="text-chapel-danger-700">Unverified</span>}
                                                        </span>
                                                    </span>
                                                </label>
                                            ))}
                                        </fieldset>
                                        <div className="mt-5 flex flex-wrap gap-3">
                                            <button type="submit" name="action_primary" className="minimal-btn-outline">Make primary</button>
                                            <button type="submit" name="action_send" className="minimal-btn-outline">Resend verification</button>
                                            <button type="submit" name="action_remove" className="minimal-btn-outline">Remove</button>
                                        </div>
                                    </form>
                                ) : (
                                    <p className="mt-3 text-sm leading-relaxed text-chapel-neutral-700">No email addresses are connected yet.</p>
                                )}
                            </section>

                            {props.can_add_email && (
                                <section className="border-t border-chapel-neutral-300 pt-8" aria-labelledby="add-email-heading">
                                    <h2 id="add-email-heading" className="font-serif text-3xl tracking-tight">Add an email address</h2>
                                    <form action={props.action_url} method="post" className="mt-6 space-y-8">
                                        <CSRFToken />
                                        {renderFields(visibleFields, props.form.errors)}
                                        {renderErrors(nonFieldErrors)}
                                        <button type="submit" name="action_add" className="minimal-btn">Add email</button>
                                    </form>
                                </section>
                            )}
                        </div>
                    ) : (
                        <section className="mt-12 max-w-xl border-t border-chapel-neutral-300 pt-8">
                            {props.page === "reauthenticate" && <p className="mb-6 text-sm leading-relaxed text-chapel-neutral-700">Please confirm your identity before continuing.</p>}
                            <form action={props.action_url} method="post" className="space-y-8">
                                <CSRFToken />
                                {hiddenFields.map(({name, field}) => (
                                    <input key={name} type="hidden" name={field.widget?.name ?? name} value={inputValue(field.widget?.value)} />
                                ))}
                                {props.redirect_field && <input type="hidden" name={props.redirect_field.name} value={props.redirect_field.value} />}
                                {renderFields(visibleFields, props.form.errors)}
                                {renderErrors(nonFieldErrors)}
                                <div className="flex flex-col items-start gap-5">
                                    <button type="submit" className="minimal-btn min-w-56">
                                        {props.page === "change-password" ? "Change password" : props.page === "set-password" ? "Set password" : "Confirm"}
                                    </button>
                                    {props.page === "change-password" && props.reset_password_url && (
                                        <a href={props.reset_password_url} className="text-xs font-bold uppercase tracking-widest text-chapel-neutral-600 underline underline-offset-4 transition-colors hover:text-chapel-primary-500">Forgot password?</a>
                                    )}
                                </div>
                            </form>
                            {props.reauthentication_alternatives && props.reauthentication_alternatives.length > 0 && (
                                <div className="mt-10 border-t border-chapel-neutral-300 pt-6">
                                    <h2 className="font-serif text-2xl">Other ways to confirm</h2>
                                    <ul className="mt-4 space-y-2">
                                        {props.reauthentication_alternatives.map((alternative) => (
                                            <li key={alternative.url}><a className="font-medium underline underline-offset-4 hover:text-chapel-primary-500" href={alternative.url}>{alternative.description}</a></li>
                                        ))}
                                    </ul>
                                </div>
                            )}
                        </section>
                    )}
                </div>
            </main>
        </Layout>
    );
};

function renderFields(fields: {name: string; field: Field}[], errors?: Record<string, string[]> | null) {
    return fields.map(({name, field}) => {
        const widget = field.widget;
        if (!widget) return null;
        const id = widget.attrs?.id ?? widget.name;
        const fieldErrors = errors?.[name] ?? [];
        const inputClass = `minimal-input ${fieldErrors.length ? "border-chapel-danger-700 text-chapel-danger-700" : ""}`;

        return (
            <div key={name} className="relative group">
                {widget.tag === "django.forms.widgets.CheckboxInput" ? (
                    <label htmlFor={id} className="flex cursor-pointer items-center gap-3 text-sm font-bold">
                        <input id={id} type="checkbox" name={widget.name} defaultChecked={Boolean(widget.value)} required={field.required} className="h-5 w-5 accent-chapel-primary-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-chapel-primary-500" />
                        {field.label ?? name}
                    </label>
                ) : (
                    <>
                        <label htmlFor={id} className="block text-[10px] font-bold uppercase tracking-[0.2em] text-chapel-neutral-600 transition-colors group-focus-within:text-chapel-primary-500">{field.label ?? name}</label>
                        <input
                            id={id}
                            type={widget.type ?? "text"}
                            name={widget.name}
                            defaultValue={inputValue(widget.value)}
                            placeholder={widget.attrs?.placeholder ?? ""}
                            autoComplete={autoComplete(name, widget.type)}
                            required={field.required}
                            aria-invalid={fieldErrors.length > 0 || undefined}
                            aria-describedby={fieldErrors.length ? `${id}-errors` : undefined}
                            className={inputClass}
                        />
                    </>
                )}
                {field.help_items?.length ? (
                    <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-relaxed text-chapel-neutral-600">
                        {field.help_items.map((item, index) => <li key={index}>{item}</li>)}
                    </ul>
                ) : field.help_text && <p className="mt-2 text-sm leading-relaxed text-chapel-neutral-600">{field.help_text}</p>}
                {fieldErrors.length > 0 && <ul id={`${id}-errors`} className="mt-2 space-y-1 text-sm font-medium text-chapel-danger-700" role="alert">{fieldErrors.map((error, index) => <li key={index}>{error}</li>)}</ul>}
            </div>
        );
    });
}

function renderErrors(errors: string[]) {
    return errors.length > 0 ? <div className="border border-chapel-danger-700 bg-chapel-danger-50 p-4 text-sm font-medium text-chapel-danger-800" role="alert">{errors.join(" ")}</div> : null;
}

function inputValue(value: string | boolean | number | string[] | null | undefined) {
    if (Array.isArray(value)) return value.join(", ");
    return typeof value === "string" || typeof value === "number" ? String(value) : "";
}

function autoComplete(name: string, type?: string | null) {
    if (type !== "password") return name.includes("email") ? "email" : undefined;
    if (name.includes("old") || name.includes("current")) return "current-password";
    return "new-password";
}
