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
        tag?: string;
    };
};

type Props = {
    title: string;
    provider_name: string;
    site_name: string;
    form: {
        fields?: Record<string, Field>;
        errors?: Record<string, string[]> | null;
        iterator?: string[];
    };
    action_url: string;
    redirect_field?: {name: string; value: string} | null;
};

export const Template = (props: Props) => {
    const {messages} = React.useContext(Context);
    const fields = props.form.fields ?? {};
    const orderedFields = (props.form.iterator ?? Object.keys(fields))
        .map((name) => ({name, field: fields[name]}))
        .filter((entry): entry is {name: string; field: Field} => entry.field != null);
    const hiddenFields = orderedFields.filter(({field}) => field.widget?.is_hidden);
    const visibleFields = orderedFields.filter(({field}) => !field.widget?.is_hidden);

    return (
        <Layout title={props.title}>
            <main className="mx-auto min-h-[calc(100vh-5rem)] w-full max-w-5xl px-6 py-16 text-chapel-neutral-950 sm:px-12 lg:py-24">
                <div className="max-w-3xl">
                    <p className="mb-3 text-xs font-bold uppercase tracking-[0.18em] text-chapel-primary-500">Account setup</p>
                    <h1 className="font-serif text-5xl leading-none tracking-tight sm:text-6xl">Complete your sign-up</h1>
                    <p className="mt-5 max-w-2xl text-base leading-relaxed text-chapel-neutral-700">
                        Use your {props.provider_name} account to join {props.site_name}. Confirm the details below to finish setting up your account.
                    </p>

                    {messages.length > 0 && (
                        <div className="mt-8 space-y-2" aria-live="polite">
                            {messages.map((message, index) => (
                                <p key={index} className="border border-chapel-neutral-300 bg-chapel-neutral-100 p-4 text-sm font-medium">
                                    {message.message}
                                </p>
                            ))}
                        </div>
                    )}

                    <form action={props.action_url} method="post" className="mt-10 space-y-8 border-t border-chapel-neutral-300 pt-8">
                        <CSRFToken />
                        {hiddenFields.map(({name, field}) => (
                            <input key={name} type="hidden" name={field.widget?.name ?? name} value={inputValue(field.widget?.value)} />
                        ))}
                        {props.redirect_field && <input type="hidden" name={props.redirect_field.name} value={props.redirect_field.value} />}
                        {visibleFields.map(({name, field}) => renderField(name, field, props.form.errors))}
                        {(props.form.errors?.__all__ ?? []).length > 0 && (
                            <div className="border border-chapel-danger-700 bg-chapel-danger-50 p-4 text-sm font-medium text-chapel-danger-800" role="alert">
                                {props.form.errors?.__all__?.join(" ")}
                            </div>
                        )}
                        <button type="submit" className="minimal-btn min-w-56">Complete sign-up</button>
                    </form>
                </div>
            </main>
        </Layout>
    );
};

function renderField(name: string, field: Field, errors?: Record<string, string[]> | null) {
    const widget = field.widget;
    if (!widget) return null;
    const id = widget.attrs?.id ?? widget.name;
    const fieldErrors = errors?.[name] ?? [];
    return (
        <div key={name} className="relative group">
            <label htmlFor={id} className="block text-[10px] font-bold uppercase tracking-[0.2em] text-chapel-neutral-600 transition-colors group-focus-within:text-chapel-primary-500">
                {field.label ?? name}
            </label>
            <input
                id={id}
                type={widget.type ?? "text"}
                name={widget.name}
                defaultValue={inputValue(widget.value)}
                placeholder={widget.attrs?.placeholder ?? ""}
                required={field.required}
                aria-invalid={fieldErrors.length > 0 || undefined}
                aria-describedby={fieldErrors.length ? `${id}-errors` : undefined}
                className={`minimal-input ${fieldErrors.length ? "border-chapel-danger-700 text-chapel-danger-700" : ""}`}
            />
            {field.help_text && <p className="mt-2 text-sm leading-relaxed text-chapel-neutral-600">{field.help_text}</p>}
            {fieldErrors.length > 0 && <ul id={`${id}-errors`} className="mt-2 space-y-1 text-sm font-medium text-chapel-danger-700" role="alert">{fieldErrors.map((error, index) => <li key={index}>{error}</li>)}</ul>}
        </div>
    );
}

function inputValue(value: string | boolean | number | string[] | null | undefined) {
    if (Array.isArray(value)) return value.join(", ");
    return typeof value === "string" || typeof value === "number" ? String(value) : "";
}
