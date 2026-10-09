import React from "react";
import {Context, CSRFToken} from "@reactivated";
import {Layout} from "../Layout";

type Props = {
    title: string;
    provider_name: string;
    continue_url: string;
    cancel_url: string;
};

export const Template = (props: Props) => {
    const {messages} = React.useContext(Context);

    return (
        <Layout title={props.title}>
            <main className="mx-auto flex min-h-[calc(100vh-5rem)] w-full max-w-5xl items-start px-6 py-16 text-chapel-neutral-950 sm:px-12 lg:py-24">
                <div className="w-full max-w-3xl">
                    <h1 className="font-serif text-5xl leading-none tracking-tight sm:text-6xl">
                        Connect {props.provider_name}
                    </h1>
                    <p className="mt-6 max-w-2xl text-base leading-relaxed text-chapel-neutral-700">
                        Continue to choose a {props.provider_name} account and connect it to your Worship Prep account.
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

                    <div className="mt-10 flex flex-col items-start gap-5 border-t border-chapel-neutral-300 pt-8 sm:flex-row sm:items-center">
                        <form action={props.continue_url} method="post">
                            <CSRFToken />
                            <button type="submit" className="minimal-btn min-w-52 gap-3">
                                <GoogleMark />
                                Continue
                            </button>
                        </form>
                        <a
                            href={props.cancel_url}
                            className="text-xs font-bold uppercase tracking-widest text-chapel-neutral-600 underline decoration-chapel-neutral-400 underline-offset-4 transition-colors hover:text-chapel-primary-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-chapel-primary-500"
                        >
                            Cancel
                        </a>
                    </div>
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
