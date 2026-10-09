import React from "react";
import {Context, CSRFToken} from "@reactivated";
import {Layout} from "../Layout";

type Props = {
    title: string;
    email: string;
    connections: {id: number; provider: string; name: string}[];
    providers: {name: string; url: string}[];
    form_errors: Record<string, string[]>;
};

export const Template = (props: Props) => {
    const {messages} = React.useContext(Context);

    return (
        <Layout title={props.title}>
            <main className="mx-auto min-h-[calc(100vh-5rem)] w-full max-w-5xl px-6 py-16 text-chapel-neutral-950 sm:px-12 lg:py-24">
                <div className="max-w-3xl">
                    <p className="mb-3 text-xs font-bold uppercase tracking-[0.18em] text-chapel-primary-500">Account settings</p>
                    <h1 className="font-serif text-5xl leading-none tracking-tight sm:text-6xl">Account Connections</h1>
                    <p className="mt-5 max-w-2xl text-base leading-relaxed text-chapel-neutral-700">
                        Manage the services you can use to sign in to <span className="font-semibold">{props.email}</span>.
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

                    <section className="mt-12 border-t border-chapel-neutral-300 pt-8" aria-labelledby="connected-heading">
                        <h2 id="connected-heading" className="font-serif text-3xl tracking-tight">Connected accounts</h2>
                        {props.connections.length ? (
                            <>
                                <p className="mt-3 text-sm leading-relaxed text-chapel-neutral-700">These accounts can sign in to your Worship Prep account.</p>
                                <form method="post" className="mt-6">
                                    <CSRFToken />
                                    <fieldset className="space-y-3">
                                        <legend className="sr-only">Choose a connected account to remove</legend>
                                        {props.connections.map((connection) => (
                                            <label key={connection.id} className="flex cursor-pointer items-center gap-4 border border-chapel-neutral-300 p-5 transition-colors hover:border-chapel-neutral-950 has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-chapel-primary-500">
                                                <input type="radio" name="account" value={connection.id} className="h-4 w-4 accent-chapel-primary-500" />
                                                <span className="min-w-0 flex-1">
                                                    <span className="block text-xs font-bold uppercase tracking-[0.16em] text-chapel-neutral-600">{connection.provider}</span>
                                                    <span className="mt-1 block truncate font-medium">{connection.name}</span>
                                                </span>
                                            </label>
                                        ))}
                                    </fieldset>
                                    {props.form_errors.account?.map((error, index) => (
                                        <p key={index} role="alert" className="mt-3 text-sm font-medium text-chapel-danger-700">{error}</p>
                                    ))}
                                    {props.form_errors.__all__?.map((error, index) => (
                                        <p key={index} role="alert" className="mt-3 text-sm font-medium text-chapel-danger-700">{error}</p>
                                    ))}
                                    <button type="submit" className="minimal-btn-outline mt-5">Remove selected account</button>
                                </form>
                            </>
                        ) : (
                            <p className="mt-3 max-w-2xl text-sm leading-relaxed text-chapel-neutral-700">No third-party accounts are connected. Add Google to sign in with your Google account as well as your password.</p>
                        )}
                    </section>

                    {props.providers.length > 0 && (
                        <section className="mt-12 border-t border-chapel-neutral-300 pt-8" aria-labelledby="add-heading">
                            <h2 id="add-heading" className="font-serif text-3xl tracking-tight">Add an account</h2>
                            <p className="mt-3 text-sm leading-relaxed text-chapel-neutral-700">Choose a provider to connect it to this account.</p>
                            <div className="mt-6 flex flex-wrap gap-3">
                                {props.providers.map((provider) => (
                                    <a key={provider.name} href={provider.url} className="minimal-btn-outline min-w-48 gap-3">
                                        {provider.name === "Google" && <GoogleMark />}
                                        Connect {provider.name}
                                    </a>
                                ))}
                            </div>
                        </section>
                    )}
                </div>
            </main>
        </Layout>
    );
};

const GoogleMark = () => (
    <svg aria-hidden="true" className="h-4 w-4 shrink-0" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
        <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4" />
        <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
        <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
        <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
    </svg>
);
