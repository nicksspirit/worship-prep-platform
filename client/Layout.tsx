import React from "react";
import {Context} from "@reactivated";

interface Props {
    title: string;
    children?: React.ReactNode;
}

// Critical inline CSS to prevent FOUC
// 1. Set background immediately to avoid white flash
// 2. Hide content until styles load
// 3. Reveal content smoothly after hydration
const criticalCSS = `
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
    const contentRef = React.useRef<HTMLDivElement>(null);

    // Show content after hydration (styles will be loaded by then)
    React.useEffect(() => {
        // Small delay to ensure CSS has been injected by Vite
        requestAnimationFrame(() => {
            contentRef.current?.classList.add("loaded");
        });
    }, []);

    return (
        <html>
            <head>
                <meta charSet="utf-8" />
                <title>{props.title}</title>
                <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no" />
                
                {/* Critical CSS to prevent Flash of Unstyled Content (FOUC) */}
                <style dangerouslySetInnerHTML={{ __html: criticalCSS }} />
                
                {/* Production: load compiled CSS */}
                {import.meta.env.PROD && (
                    <link rel="stylesheet" href={`${STATIC_URL}dist/index.css`} />
                )}
            </head>
            <body>
                <div id="app-content" ref={contentRef}>
                    {props.children}
                </div>
            </body>
        </html>
    );
};

