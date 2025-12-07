import React from "react";
import {Context} from "@reactivated";

interface Props {
    title: string;
    children?: React.ReactNode;
}

// Development-only: Critical inline CSS to prevent FOUC
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
        background-color: oklch(0.253267 0.015896 252.417568);
        margin: 0;
        min-height: 100vh;
    }
    #app-content {
        opacity: 0;
        transition: opacity 0.15s ease-out;
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
        <html>
            <head>
                <meta charSet="utf-8" />
                <title>{props.title}</title>
                <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no" />

                {/* Development: inject critical CSS to prevent FOUC */}
                {isDev && <style dangerouslySetInnerHTML={{ __html: devCriticalCSS }} />}
            </head>
            <body>
                {/* In production, content is visible immediately (no opacity hiding) */}
                <div id="app-content" className={isDev ? "" : "loaded"}>
                    {props.children}
                </div>
            </body>
        </html>
    );
};

