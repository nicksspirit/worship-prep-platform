import React from "react";
import {CSRFToken, Context, reverse} from "@reactivated";
import {Layout} from "../Layout";

type RequestInvitationPageProps = {
    title: string;
    success: boolean;
    sign_in_url: string;
    non_field_errors: string[];
    email: string;
    first_name: string;
    last_name: string;
    message: string;
    field_errors: Record<string, string>;
};

export const Template = (props: RequestInvitationPageProps) => {
    const {messages} = React.useContext(Context);

    return (
        <Layout title={props.title}>
            <div className="flex min-h-[calc(100vh-5rem)] w-full flex-col lg:flex-row bg-chapel-neutral-50 text-chapel-neutral-950 overflow-hidden">
                <div className="bg-grain relative flex flex-col justify-between w-full lg:w-[45%] bg-chapel-neutral-200 border-b lg:border-b-0 lg:border-r border-chapel-neutral-950">
                    <div className="relative z-10 pt-16 px-8 lg:px-16">
                        
                        <h1 className="font-serif text-[4rem] lg:text-[6rem] leading-[0.9] tracking-tight mb-8">
                            Request <br />
                            <span className="italic text-chapel-primary-500">Access.</span>
                        </h1>

                        <p className="max-w-sm text-lg font-medium leading-relaxed text-chapel-neutral-700">
                            Membership is by invitation. Share your details and our team will review your request.
                        </p>
                    </div>

                    <div className="relative z-10 mt-16 lg:mt-0 flex items-center justify-between border-t border-chapel-neutral-950/20 pt-6 pb-12 lg:pb-16 px-8 lg:px-16">
                        <div className="text-xs font-bold uppercase tracking-widest">Invite only</div>
                        <div className="text-xs font-bold uppercase tracking-widest text-chapel-primary-500">New requests</div>
                    </div>
                </div>

                <div className="flex w-full lg:w-[55%] flex-col justify-center px-8 py-16 lg:px-24 xl:px-32 bg-chapel-neutral-50">
                    <div className="w-full max-w-lg mx-auto">
                        <h2 className="text-3xl font-serif tracking-tight mb-12">Request Invitation</h2>

                        {props.success ? (
                            <div className="space-y-8">
                                <div className="text-sm font-medium p-4 border border-chapel-neutral-950 bg-chapel-neutral-100 leading-relaxed">
                                    Thank you. If your request is approved, you will receive an email with a link to complete
                                    your account setup.
                                </div>
                                <a href={props.sign_in_url} className="minimal-btn inline-block text-center w-full">
                                    Back to Sign In
                                </a>
                            </div>
                        ) : (
                            <>
                                <div className="space-y-6 mb-12">
                                    {messages.length > 0 && (
                                        <div className="space-y-2">
                                            {messages.map((message, index) => (
                                                <div
                                                    key={index}
                                                    className="text-sm font-medium p-4 border border-chapel-neutral-950 bg-chapel-neutral-100"
                                                >
                                                    {message.message}
                                                </div>
                                            ))}
                                        </div>
                                    )}

                                    {props.non_field_errors.length > 0 && (
                                        <div className="text-sm font-bold text-chapel-primary-500 border border-chapel-primary-500 p-4">
                                            {props.non_field_errors.join(" ")}
                                        </div>
                                    )}
                                </div>

                                <form action={reverse("request_invitation")} method="post" className="space-y-10">
                                    <CSRFToken />

                                    <div className="space-y-8">
                                        <div className="relative group">
                                            <label
                                                htmlFor="id_email"
                                                className="block text-[10px] font-bold uppercase tracking-[0.2em] text-chapel-neutral-500 transition-colors group-focus-within:text-chapel-primary-500"
                                            >
                                                Email
                                            </label>
                                            <input
                                                id="id_email"
                                                type="email"
                                                name="email"
                                                defaultValue={props.email}
                                                placeholder="you@example.org"
                                                autoComplete="email"
                                                required
                                                className={`minimal-input ${props.field_errors.email ? "border-chapel-primary-500 text-chapel-primary-500" : ""}`}
                                            />
                                            {props.field_errors.email && (
                                                <p className="mt-2 text-xs font-bold text-chapel-primary-500">
                                                    {props.field_errors.email}
                                                </p>
                                            )}
                                        </div>

                                        <div className="relative group">
                                            <label
                                                htmlFor="id_first_name"
                                                className="block text-[10px] font-bold uppercase tracking-[0.2em] text-chapel-neutral-500 transition-colors group-focus-within:text-chapel-primary-500"
                                            >
                                                First name
                                            </label>
                                            <input
                                                id="id_first_name"
                                                type="text"
                                                name="first_name"
                                                defaultValue={props.first_name}
                                                autoComplete="given-name"
                                                required
                                                className={`minimal-input ${props.field_errors.first_name ? "border-chapel-primary-500 text-chapel-primary-500" : ""}`}
                                            />
                                            {props.field_errors.first_name && (
                                                <p className="mt-2 text-xs font-bold text-chapel-primary-500">
                                                    {props.field_errors.first_name}
                                                </p>
                                            )}
                                        </div>

                                        <div className="relative group">
                                            <label
                                                htmlFor="id_last_name"
                                                className="block text-[10px] font-bold uppercase tracking-[0.2em] text-chapel-neutral-500 transition-colors group-focus-within:text-chapel-primary-500"
                                            >
                                                Last name
                                            </label>
                                            <input
                                                id="id_last_name"
                                                type="text"
                                                name="last_name"
                                                defaultValue={props.last_name}
                                                autoComplete="family-name"
                                                required
                                                className={`minimal-input ${props.field_errors.last_name ? "border-chapel-primary-500 text-chapel-primary-500" : ""}`}
                                            />
                                            {props.field_errors.last_name && (
                                                <p className="mt-2 text-xs font-bold text-chapel-primary-500">
                                                    {props.field_errors.last_name}
                                                </p>
                                            )}
                                        </div>

                                        <div className="relative group">
                                            <label
                                                htmlFor="id_message"
                                                className="block text-[10px] font-bold uppercase tracking-[0.2em] text-chapel-neutral-500 transition-colors group-focus-within:text-chapel-primary-500"
                                            >
                                                Message{" "}
                                                <span className="font-normal normal-case tracking-normal text-chapel-neutral-400">
                                                    (optional)
                                                </span>
                                            </label>
                                            <textarea
                                                id="id_message"
                                                name="message"
                                                rows={4}
                                                defaultValue={props.message}
                                                placeholder="Role, ministry team, or other context…"
                                                className={`minimal-input min-h-[120px] py-3 ${props.field_errors.message ? "border-chapel-primary-500 text-chapel-primary-500" : ""}`}
                                            />
                                            {props.field_errors.message && (
                                                <p className="mt-2 text-xs font-bold text-chapel-primary-500">
                                                    {props.field_errors.message}
                                                </p>
                                            )}
                                        </div>
                                    </div>

                                    <div className="flex flex-col gap-6 pt-4">
                                        <button type="submit" className="minimal-btn w-full">
                                            Submit request
                                        </button>

                                        <a
                                            href={props.sign_in_url}
                                            className="text-xs font-bold uppercase tracking-widest text-chapel-neutral-500 hover:text-chapel-neutral-950 text-center transition-colors"
                                        >
                                            Back to Sign In
                                        </a>
                                    </div>
                                </form>
                            </>
                        )}
                    </div>
                </div>
            </div>
        </Layout>
    );
};
