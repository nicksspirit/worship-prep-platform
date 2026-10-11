import React from "react";
import {reverse} from "@reactivated";
import {Layout} from "../Layout";

export const Template = (props: {title: string}) => (
    <Layout title={props.title}>
        <main className="mx-auto max-w-6xl px-6 py-12 sm:py-20">
            <a href={reverse("song_carts:list")} className="inline-flex min-h-11 items-center text-sm underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-chapel-primary-500">← My submissions</a>
            <header className="mt-8 border-b border-chapel-neutral-950 pb-8">
                <h1 className="text-4xl sm:text-5xl">Song cart</h1>
                <p className="mt-5 text-sm text-chapel-neutral-700">0 songs · Not submitted yet</p>
            </header>
            <section className="max-w-xl py-12" aria-labelledby="empty-cart-heading">
                <h2 id="empty-cart-heading" className="text-3xl">Your song cart is empty.</h2>
                <p className="mt-4 leading-7 text-chapel-neutral-700">Find a song in the catalog and choose “Add to song cart”. Choose the service date and section when you add your first song.</p>
                <div className="mt-8 flex flex-wrap items-center gap-x-6 gap-y-3">
                    <a href={reverse("catalog:search")} className="inline-flex min-h-11 items-center border border-chapel-neutral-950 bg-chapel-neutral-950 px-5 py-3 text-sm font-bold text-white hover:bg-chapel-primary-500 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-chapel-primary-500">Find songs</a>
                    <a href={reverse("song_carts:add_unlisted")} className="inline-flex min-h-11 items-center text-sm font-bold text-chapel-primary-600 underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-chapel-primary-500">Add an unlisted song</a>
                </div>
            </section>
        </main>
    </Layout>
);
