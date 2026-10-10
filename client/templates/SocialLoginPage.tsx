import React from "react";
import {Context, CSRFToken} from "@reactivated";
import {Layout} from "../Layout";

type Props = {
    title: string;
    provider_name: string;
    action_url: string;
};

export const Template = (props: Props) => {
    const {messages} = React.useContext(Context);

    return (
        <Layout title={props.title}>
            <main className="mx-auto flex min-h-[calc(100vh-5rem)] w-full max-w-5xl items-start px-6 py-16 text-chapel-neutral-950 sm:px-12 lg:py-24">
                <div className="w-full max-w-3xl">
                    <p className="mb-3 text-xs font-bold uppercase tracking-[0.18em] text-chapel-primary-500">Sign in</p>
                    <h1 className="font-serif text-5xl leading-none tracking-tight sm:text-6xl">Sign in with {props.provider_name}</h1>
                    <p className="mt-6 max-w-2xl text-base leading-relaxed text-chapel-neutral-700">
                        Continue to sign in to Worship Prep Platform with your {props.provider_name} account.
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

                    <form action={props.action_url} method="post" className="mt-10 border-t border-chapel-neutral-300 pt-8">
                        <CSRFToken />
                        <button type="submit" className="minimal-btn min-w-56">Continue with {props.provider_name}</button>
                    </form>
                </div>
            </main>
        </Layout>
    );
};
