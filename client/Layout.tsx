import React from "react";
import {Context} from "@reactivated";

interface Props {
    title: string;
    children?: React.ReactNode;
}

// Development-only: Critical inline CSS to prevent Flash of Unstyled Content (FOUC)
// In dev, Vite injects CSS via JS modules, causing a gap between HTML render and style injection.
// This CSS:
// 1. Sets background immediately to avoid white flash
// 2. Hides content until styles load
// 3. Reveals content smoothly after hydration
//
// NOTE: The background color (oklch value) matches DaisyUI's bg-base-200 dark theme.
// If you change themes in tailwind.config.js, update this value accordingly.
const devCriticalCSS = `
    html, body {
        background-color: #F8F9FA;
        color: #212529;
        margin: 0;
        min-height: 100vh;
        -webkit-font-smoothing: antialiased;
    }
    #app-content {
        opacity: 0;
        transition: opacity 0.4s ease-out;
    }
    #app-content.loaded {
        opacity: 1;
    }
`;

export const Layout = (props: Props) => {
    const {STATIC_URL} = React.useContext(Context);

    // Only apply FOUC prevention in development
    // In production, Reactivated generates a blocking <link> tag, so CSS loads before paint
    const isDev = !import.meta.env.PROD;

    React.useEffect(() => {
        if (!isDev) return;

        // Reveal content after hydration (styles will be loaded by then)
        requestAnimationFrame(() => {
            document.getElementById("app-content")?.classList.add("loaded");
        });
    }, [isDev]);

    return (
        <html lang="en" data-theme="light">
            <head>
                <meta charSet="utf-8" />
                <title>{props.title}</title>
                <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no" />
                
                {/* Favicons */}
                <link rel="apple-touch-icon" sizes="180x180" href={`${STATIC_URL}apple-touch-icon.png`} />
                <link rel="icon" type="image/png" sizes="32x32" href={`${STATIC_URL}favicon-32x32.png`} />
                <link rel="icon" type="image/png" sizes="16x16" href={`${STATIC_URL}favicon-16x16.png`} />
                <link rel="manifest" href={`${STATIC_URL}site.webmanifest`} />
                <link rel="shortcut icon" href={`${STATIC_URL}favicon.ico`} />

                {/* Development: inject critical CSS to prevent FOUC */}
                {isDev && <style dangerouslySetInnerHTML={{ __html: devCriticalCSS }} />}
            </head>
            <body>
                {/* In production, content is visible immediately (no opacity hiding) */}
                <div id="app-content" className={isDev ? "" : "loaded"}>
                    <header className="sticky top-0 z-50 flex h-16 items-center justify-between border-b border-chapel-neutral-300 bg-chapel-neutral-50 px-6 sm:px-8">
                        <div className="flex w-1/3 items-center">
                            <span className="text-sm font-bold uppercase tracking-[0.15em] text-chapel-neutral-900">
                                Chapel of Mercy
                            </span>
                        </div>
                        
                        <div className="relative flex w-1/3 justify-center">
                            {/* Centered Circular Logo overlapping the bottom border */}
                            <div className="absolute top-1/2 flex h-16 w-16 -translate-y-1/2 items-center justify-center rounded-full border-4 border-chapel-neutral-50 shadow-sm bg-white overflow-hidden">
                                <img src={`${STATIC_URL}rccgcm_logo.png`} alt="RCCG Chapel of Mercy Logo" className="h-full w-full object-cover" />
                            </div>
                        </div>

                        <div className="flex w-1/3 items-center justify-end gap-3">
                            <button className="flex h-8 w-8 items-center justify-center rounded-full border border-chapel-neutral-300 text-chapel-neutral-600 transition-colors hover:bg-chapel-neutral-200">
                                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                                </svg>
                            </button>
                            <div className="flex items-center gap-2">
                                <div className="h-8 w-8 rounded-full bg-chapel-neutral-300 overflow-hidden">
                                    <svg className="h-full w-full text-chapel-neutral-500" fill="currentColor" viewBox="0 0 24 24">
                                        <path d="M24 20.993V24H0v-2.996A14.977 14.977 0 0112.004 15c4.904 0 9.26 2.354 11.996 5.993zM16.002 8.999a4 4 0 11-8 0 4 4 0 018 0z" />
                                    </svg>
                                </div>
                                <svg className="h-4 w-4 text-chapel-neutral-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                                </svg>
                            </div>
                        </div>
                    </header>

                    <div className="w-full">
                        {props.children}
                    </div>
                </div>
            </body>
        </html>
    );
};
