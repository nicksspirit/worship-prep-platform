import React from "react";
import {reverse} from "@reactivated";
import {Layout} from "../Layout";

type InvitationRequiredPageProps = {
    title: string;
    request_invitation_url: string;
    sign_in_url: string;
};

export const Template = (props: InvitationRequiredPageProps) => {
    return (
        <Layout title={props.title} signedOutHeaderLink="song-search">
            <main className="flex min-h-[calc(100vh-5rem)] w-full flex-col overflow-hidden bg-chapel-neutral-50 text-chapel-neutral-950 lg:flex-row">
                <aside className="bg-grain relative flex w-full flex-col justify-between border-b border-chapel-neutral-950 bg-chapel-neutral-200 px-8 py-12 lg:w-[45%] lg:border-b-0 lg:border-r lg:p-16">
                    <div className="relative z-10 pt-16">
                        <p className="mb-7 text-[10px] font-bold uppercase tracking-[0.2em] text-chapel-primary-500">
                            Worship Prep Platform
                        </p>
                        <h1 className="mb-8 font-serif text-[4rem] leading-[0.9] tracking-tight lg:text-[6rem]">
                            Access by <br />
                            <span className="italic text-chapel-primary-500">invitation.</span>
                        </h1>
                        <p className="max-w-sm text-lg font-medium leading-relaxed text-chapel-neutral-700">
                            A shared service flow begins with the people entrusted to prepare it.
                        </p>
                    </div>

                    <div className="relative z-10 mt-16 flex items-center justify-between border-t border-chapel-neutral-950/20 pt-6 lg:mt-0">
                        <span className="text-xs font-bold uppercase tracking-widest">Est. 2026</span>
                        <span className="text-xs font-bold uppercase tracking-widest text-chapel-primary-500">Secure Access</span>
                    </div>
                </aside>

                <section className="flex w-full flex-col justify-center bg-chapel-neutral-50 px-8 py-16 lg:w-[55%] lg:px-24 xl:px-32">
                    <div className="mx-auto w-full max-w-lg">
                        <p className="mb-5 text-[10px] font-bold uppercase tracking-[0.2em] text-chapel-primary-500">
                            Invitation required
                        </p>
                        <h2 className="mb-6 font-serif text-4xl leading-none tracking-tight">
                            You need an invitation to join.
                        </h2>
                        <p className="max-w-md text-lg leading-relaxed text-chapel-neutral-700">
                            Your Google account was verified, but this platform is reserved for invited ministry, choir, and technical booth members.
                        </p>

                        <div className="my-10 border-t border-chapel-neutral-300" />

                        <div className="space-y-5">
                            <a href={props.request_invitation_url} className="minimal-btn w-full">
                                Request an Invitation
                            </a>
                            <a
                                href={props.sign_in_url}
                                className="block text-center text-xs font-bold uppercase tracking-widest text-chapel-neutral-500 transition-colors hover:text-chapel-neutral-950 focus:outline-none focus-visible:text-chapel-primary-500"
                            >
                                Return to Sign In
                            </a>
                        </div>

                        <p className="mt-12 border-l border-chapel-primary-500 pl-4 text-sm leading-relaxed text-chapel-neutral-600">
                            Already invited? Sign in using the email address that received your invitation.
                        </p>
                    </div>
                </section>
            </main>
        </Layout>
    );
};
