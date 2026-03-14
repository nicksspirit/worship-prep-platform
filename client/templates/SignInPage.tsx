import React from "react";
import {CSRFToken, Context, reverse} from "@reactivated";
import {Layout} from "../Layout";

type SignInPageProps = {
    title: string;
    login_form: {
        fields?: Record<
            string,
            {
                label?: string;
                help_text?: string | null;
                widget?: {
                    name: string;
                    is_hidden?: boolean;
                    value?: string | boolean | number | string[] | null;
                    attrs?: {
                        id?: string;
                        placeholder?: string;
                    };
                    type?: string;
                    tag?: string;
                };
            }
        >;
        errors?: Record<string, string[]> | null;
        iterator?: string[];
    };
    login_value: string | null;
    signup_url: string | null;
    reset_password_url: string;
    google_login_url: string;
    next_value: string | null;
    redirect_field_name: string;
};

type SerializedField = NonNullable<SignInPageProps["login_form"]["fields"]>[string];

const messageClassNames: Record<string, string> = {
    error: "alert-error",
    success: "alert-success",
    warning: "alert-warning",
    info: "alert-info",
    debug: "alert-info",
};

export const Template = (props: SignInPageProps) => {
    const {messages} = React.useContext(Context);
    const fieldMap = {...(props.login_form.fields ?? {})};
    if (!fieldMap.login) {
        fieldMap.login = {
            label: "Email",
            help_text: null,
            widget: {
                name: "login",
                is_hidden: false,
                value: props.login_value,
                attrs: {
                    id: "id_login",
                    placeholder: "Email address",
                },
                type: "email",
                tag: "django.forms.widgets.EmailInput",
            },
        };
    }
    const fieldOrder = props.login_form.iterator ?? Object.keys(fieldMap);
    const orderedFields = fieldOrder
        .map((name) => ({name, field: fieldMap[name]}))
        .filter(
            (entry): entry is {name: string; field: SerializedField} => entry.field != null,
        );
    const hiddenFields = orderedFields.filter((entry) => entry.field.widget?.is_hidden);
    const visibleFields = orderedFields.filter((entry) => !entry.field.widget?.is_hidden);
    const nonFieldErrors = props.login_form.errors?.__all__ ?? [];

    return (
        <Layout title={props.title}>
            <div className="min-h-screen bg-base-200 px-4 py-12">
                <div className="mx-auto flex min-h-[calc(100vh-6rem)] max-w-5xl items-center">
                    <div className="grid w-full gap-8 lg:grid-cols-[1.1fr_0.9fr]">
                        <section className="hidden rounded-3xl bg-primary p-10 text-primary-content shadow-2xl lg:block">
                            <p className="text-sm font-semibold uppercase tracking-[0.3em] opacity-80">
                                Worship Prep Platform
                            </p>
                            <h1 className="mt-6 text-4xl font-bold leading-tight">
                                One sign-in for ministers, choir, and the tech booth.
                            </h1>
                            <p className="mt-4 max-w-lg text-base leading-7 opacity-90">
                                Keep scriptures, lyrics, and service flow aligned from one
                                secure workspace.
                            </p>
                            <div className="mt-10 space-y-4 text-sm opacity-90">
                                <p>Use your email and password to continue.</p>
                                <p>Google sign-in is also available for staff access.</p>
                                <p>Admin access returns you to the page you originally requested.</p>
                            </div>
                        </section>

                        <section className="card bg-base-100 shadow-2xl">
                            <div className="card-body gap-5 p-8">
                                <div className="text-center">
                                    <h2 className="text-3xl font-bold">Sign in</h2>
                                    <p className="mt-2 text-sm text-base-content/70">
                                        Continue to the worship prep workspace.
                                    </p>
                                </div>

                                {messages.length > 0 && (
                                    <div className="space-y-2">
                                        {messages.map((message, index) => (
                                            <div
                                                key={`${message.level}-${index}`}
                                                className={`alert ${messageClassNames[message.level_tag] ?? "alert-info"}`}
                                            >
                                                <span>{message.message}</span>
                                            </div>
                                        ))}
                                    </div>
                                )}

                                {nonFieldErrors.length ? (
                                    <div className="alert alert-error">
                                        <span>{nonFieldErrors.join(" ")}</span>
                                    </div>
                                ) : null}

                                <form
                                    action={reverse("account_login")}
                                    method="post"
                                    className="space-y-4"
                                >
                                    <CSRFToken />

                                    {hiddenFields.map(({name, field}) => (
                                        <input
                                            key={name}
                                            type="hidden"
                                            name={field.widget?.name ?? name}
                                            value={
                                                typeof field.widget?.value === "string"
                                                    ? field.widget.value
                                                    : ""
                                            }
                                        />
                                    ))}

                                    {props.next_value ? (
                                        <input
                                            type="hidden"
                                            name={props.redirect_field_name}
                                            value={props.next_value}
                                        />
                                    ) : null}

                                    {visibleFields.map(({name, field}) => {
                                        const widget = field.widget;
                                        const fieldError = props.login_form.errors?.[name]?.[0] ?? null;
                                        if (!widget) {
                                            return null;
                                        }

                                        if (widget.tag === "django.forms.widgets.CheckboxInput") {
                                            return (
                                                <label
                                                    key={name}
                                                    className="label cursor-pointer justify-start gap-3 rounded-xl border border-base-300 px-4 py-3"
                                                >
                                                    <input
                                                        type="checkbox"
                                                        name={widget.name}
                                                        className="checkbox checkbox-primary"
                                                        defaultChecked={Boolean(widget.value)}
                                                    />
                                                    <span className="label-text text-sm font-medium">
                                                        {field.label ?? name}
                                                    </span>
                                                </label>
                                            );
                                        }

                                        return (
                                            <div key={name} className="form-control">
                                                <label
                                                    className="label"
                                                    htmlFor={widget.attrs?.id ?? widget.name}
                                                >
                                                    <span className="label-text font-medium">
                                                        {field.label ?? name}
                                                    </span>
                                                </label>
                                                <input
                                                    id={widget.attrs?.id ?? widget.name}
                                                    type={widget.type ?? "text"}
                                                    name={widget.name}
                                                    defaultValue={
                                                        Array.isArray(widget.value)
                                                            ? widget.value.join(", ")
                                                            : typeof widget.value === "string" ||
                                                                typeof widget.value === "number"
                                                              ? String(widget.value)
                                                              : ""
                                                    }
                                                    placeholder={
                                                        widget.attrs?.placeholder ?? field.label ?? name
                                                    }
                                                    autoComplete={
                                                        widget.tag ===
                                                        "django.forms.widgets.PasswordInput"
                                                            ? "current-password"
                                                            : "email"
                                                    }
                                                    className={`input input-bordered w-full ${
                                                        fieldError ? "input-error" : ""
                                                    }`}
                                                />
                                                {fieldError ? (
                                                    <p className="mt-2 text-sm text-error">
                                                        {fieldError}
                                                    </p>
                                                ) : null}
                                            </div>
                                        );
                                    })}

                                    <div className="flex justify-end">
                                        <a
                                            href={props.reset_password_url}
                                            className="link link-hover text-sm text-base-content/70"
                                        >
                                            Forgot your password?
                                        </a>
                                    </div>

                                    <button type="submit" className="btn btn-primary w-full">
                                        Sign in
                                    </button>
                                </form>

                                <div className="divider">OR</div>

                                <form action={props.google_login_url} method="post">
                                    <CSRFToken />
                                    {props.next_value ? (
                                        <input
                                            type="hidden"
                                            name={props.redirect_field_name}
                                            value={props.next_value}
                                        />
                                    ) : null}

                                    <button type="submit" className="btn btn-outline w-full">
                                        <svg
                                            className="h-5 w-5"
                                            viewBox="0 0 24 24"
                                            xmlns="http://www.w3.org/2000/svg"
                                            aria-hidden="true"
                                        >
                                            <path
                                                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                                                fill="#4285F4"
                                            />
                                            <path
                                                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                                                fill="#34A853"
                                            />
                                            <path
                                                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                                                fill="#FBBC05"
                                            />
                                            <path
                                                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                                                fill="#EA4335"
                                            />
                                        </svg>
                                        <span>Continue with Google</span>
                                    </button>
                                </form>

                                {props.signup_url ? (
                                    <p className="text-center text-sm text-base-content/70">
                                        Don&apos;t have an account?{" "}
                                        <a href={props.signup_url} className="link link-primary">
                                            Sign up
                                        </a>
                                    </p>
                                ) : null}
                            </div>
                        </section>
                    </div>
                </div>
            </div>
        </Layout>
    );
};
