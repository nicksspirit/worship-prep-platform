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
    request_invitation_url: string;
    reset_password_url: string;
    google_login_url: string;
    next_value: string | null;
    redirect_field_name: string;
};

type SerializedField = NonNullable<SignInPageProps["login_form"]["fields"]>[string];

export const Template = (props: SignInPageProps) => {
    const {messages} = React.useContext(Context);
    const fieldMap = {...(props.login_form.fields ?? {})};
    if (!fieldMap.login) {
        fieldMap.login = {
            label: "Email Address",
            help_text: null,
            widget: {
                name: "login",
                is_hidden: false,
                value: props.login_value,
                attrs: {
                    id: "id_login",
                    placeholder: "e.g., minister@chapel.org",
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
            <div className="flex min-h-[calc(100vh-5rem)] w-full flex-col lg:flex-row bg-chapel-neutral-50 text-chapel-neutral-950 overflow-hidden">
                
                {/* Left Side: Editorial Typography & Imagery */}
                <div className="bg-grain relative flex flex-col justify-between w-full lg:w-[45%] bg-chapel-neutral-200 px-8 py-12 lg:p-16 border-b lg:border-b-0 lg:border-r border-chapel-neutral-950">
                    <div className="relative z-10 pt-16">
                        
                        <h1 className="font-serif text-[4rem] lg:text-[6rem] leading-[0.9] tracking-tight mb-8">
                            Worship <br />
                            <span className="italic text-chapel-primary-500">Preparation.</span>
                        </h1>
                        
                        <p className="max-w-sm text-lg font-medium leading-relaxed text-chapel-neutral-700">
                            Synchronizing the altar, the choir, and the technical booth into a single harmonious flow.
                        </p>
                    </div>

                    <div className="relative z-10 mt-16 lg:mt-0 flex items-center justify-between border-t border-chapel-neutral-950/20 pt-6">
                        <div className="text-xs font-bold uppercase tracking-widest">Est. 2026</div>
                        <div className="text-xs font-bold uppercase tracking-widest text-chapel-primary-500">Secure Access</div>
                    </div>
                </div>

                {/* Right Side: Brutalist Form */}
                <div className="flex w-full lg:w-[55%] flex-col justify-center px-8 py-16 lg:px-24 xl:px-32 bg-chapel-neutral-50">
                    <div className="w-full max-w-lg mx-auto">
                        <h2 className="text-3xl font-serif tracking-tight mb-12">Sign In</h2>

                        <div className="space-y-6 mb-12">
                            {messages.length > 0 && (
                                <div className="space-y-2">
                                    {messages.map((message, index) => (
                                        <div key={index} className="text-sm font-medium p-4 border border-chapel-neutral-950 bg-chapel-neutral-100">
                                            {message.message}
                                        </div>
                                    ))}
                                </div>
                            )}

                            {nonFieldErrors.length > 0 && (
                                <div className="text-sm font-bold text-chapel-primary-500 border border-chapel-primary-500 p-4">
                                    {nonFieldErrors.join(" ")}
                                </div>
                            )}
                        </div>

                        <form action={reverse("account_login")} method="post" className="space-y-10">
                            <CSRFToken />
                            {hiddenFields.map(({name, field}) => (
                                <input key={name} type="hidden" name={field.widget?.name ?? name} value={typeof field.widget?.value === "string" ? field.widget.value : ""} />
                            ))}
                            {props.next_value && (
                                <input type="hidden" name={props.redirect_field_name} value={props.next_value} />
                            )}

                            <div className="space-y-8">
                                {visibleFields.map(({name, field}) => {
                                    const widget = field.widget;
                                    const fieldError = props.login_form.errors?.[name]?.[0] ?? null;
                                    if (!widget) return null;

                                    if (widget.tag === "django.forms.widgets.CheckboxInput") {
                                        return (
                                            <label key={name} className="flex items-center gap-4 cursor-pointer mt-4">
                                                <input
                                                    type="checkbox"
                                                    name={widget.name}
                                                    defaultChecked={Boolean(widget.value)}
                                                    className="w-5 h-5 accent-chapel-primary-500 cursor-pointer border-chapel-neutral-950 rounded-none focus:ring-0"
                                                />
                                                <span className="text-sm font-bold uppercase tracking-wider text-chapel-neutral-950">
                                                    {field.label ?? name}
                                                </span>
                                            </label>
                                        );
                                    }

                                    return (
                                        <div key={name} className="relative group">
                                            <label htmlFor={widget.attrs?.id ?? widget.name} className="block text-[10px] font-bold uppercase tracking-[0.2em] text-chapel-neutral-500 transition-colors group-focus-within:text-chapel-primary-500">
                                                {field.label ?? name}
                                            </label>
                                            <input
                                                id={widget.attrs?.id ?? widget.name}
                                                type={widget.type ?? "text"}
                                                name={widget.name}
                                                defaultValue={
                                                    Array.isArray(widget.value) ? widget.value.join(", ") : typeof widget.value === "string" || typeof widget.value === "number" ? String(widget.value) : ""
                                                }
                                                placeholder={widget.attrs?.placeholder ?? ""}
                                                autoComplete={widget.tag === "django.forms.widgets.PasswordInput" ? "current-password" : "email"}
                                                className={`minimal-input ${fieldError ? "border-chapel-primary-500 text-chapel-primary-500" : ""}`}
                                            />
                                            {fieldError && <p className="mt-2 text-xs font-bold text-chapel-primary-500">{fieldError}</p>}
                                        </div>
                                    );
                                })}
                            </div>

                            <div className="flex flex-col gap-6 pt-4">
                                <button type="submit" className="minimal-btn w-full">
                                    Sign In
                                </button>
                                
                                <a href={props.reset_password_url} className="text-xs font-bold uppercase tracking-widest text-chapel-neutral-500 hover:text-chapel-neutral-950 text-center transition-colors">
                                    Recover Password
                                </a>
                            </div>
                        </form>

                        <div className="my-12 relative flex items-center justify-center">
                            <div className="absolute w-full border-t border-chapel-neutral-300"></div>
                            <span className="relative bg-chapel-neutral-50 px-4 text-[10px] font-bold uppercase tracking-[0.2em] text-chapel-neutral-400">
                                OR
                            </span>
                        </div>

                        <form action={props.google_login_url} method="post">
                            <CSRFToken />
                            {props.next_value && <input type="hidden" name={props.redirect_field_name} value={props.next_value} />}
                            <button type="submit" className="minimal-btn-outline w-full gap-4">
                                <svg className="h-4 w-4" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                    <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4" />
                                    <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
                                    <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
                                    <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
                                </svg>
                                Sign In via Google
                            </button>
                        </form>

                        <div className="mt-10 text-center">
                            <a
                                href={props.request_invitation_url}
                                className="text-xs font-bold uppercase tracking-widest text-chapel-primary-500 hover:text-chapel-neutral-950 transition-colors border-b border-chapel-primary-500/40 hover:border-chapel-neutral-950 pb-0.5"
                            >
                                Request Invitation
                            </a>
                        </div>
                    </div>
                </div>
            </div>
        </Layout>
    );
};
