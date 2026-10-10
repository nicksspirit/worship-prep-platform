import React from "react";
import {Context} from "@reactivated";
import {Layout} from "../Layout";

type Props = {
    title: string;
    state: "cancelled" | "error";
    sign_in_url: string;
};

const copy = {
    cancelled: {
        eyebrow: "Sign in",
        heading: "Sign in cancelled",
        description: "Google sign-in was cancelled. If that was a mistake, return to sign in and try again.",
        action: "Return to sign in",
    },
    error: {
        eyebrow: "Sign in",
        heading: "Google sign-in didn’t work",
        description: "We couldn’t complete sign-in with Google. Please return to sign in and try again.",
        action: "Return to sign in",
    },
} as const;

export const Template = (props: Props) => {
    const {messages} = React.useContext(Context);
    const page = copy[props.state];

    return (
        <Layout title={props.title}>
            <main className="mx-auto flex min-h-[calc(100vh-5rem)] w-full max-w-5xl items-start px-6 py-16 text-chapel-neutral-950 sm:px-12 lg:py-24">
                <div className="w-full max-w-3xl">
                    <p className="mb-3 text-xs font-bold uppercase tracking-[0.18em] text-chapel-primary-500">{page.eyebrow}</p>
                    <h1 className="font-serif text-5xl leading-none tracking-tight sm:text-6xl">{page.heading}</h1>
                    <p className="mt-6 max-w-2xl text-base leading-relaxed text-chapel-neutral-700">{page.description}</p>

                    {messages.length > 0 && (
                        <div className="mt-8 space-y-2" aria-live="polite">
                            {messages.map((message, index) => (
                                <p key={index} className="border border-chapel-neutral-300 bg-chapel-neutral-100 p-4 text-sm font-medium">
                                    {message.message}
                                </p>
                            ))}
                        </div>
                    )}

                    <div className="mt-10 border-t border-chapel-neutral-300 pt-8">
                        <a href={props.sign_in_url} className="minimal-btn inline-flex min-w-56">{page.action}</a>
                    </div>
                </div>
            </main>
        </Layout>
    );
};
