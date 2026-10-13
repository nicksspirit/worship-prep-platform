import React from "react";
import { Context, CSRFToken, reverse } from "@reactivated";

interface Props {
  title: string;
  children?: React.ReactNode;
  signedOutHeaderLink?: "staff-sign-in" | "song-search";
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

const GOOGLE_FONTS_URL =
  "https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,500;0,600;0,700;1,400&family=Instrument+Sans:ital,wght@0,400;0,500;0,600;0,700;1,400&display=swap";

export const Layout = (props: Props) => {
  const { STATIC_URL, user, song_cart } = React.useContext(Context);
  const staticUrl = STATIC_URL.replace(/\/+$/, "");
  const signedOutHeaderLink = props.signedOutHeaderLink === "song-search"
    ? {href: reverse("catalog:search"), label: "Song search"}
    : {href: reverse("account_login"), label: "Sign in"};

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
        <link rel="apple-touch-icon" sizes="180x180" href={`${staticUrl}/apple-touch-icon.png`} />
        <link rel="icon" type="image/png" sizes="32x32" href={`${staticUrl}/favicon-32x32.png`} />
        <link rel="icon" type="image/png" sizes="16x16" href={`${staticUrl}/favicon-16x16.png`} />
        <link rel="manifest" href={`${staticUrl}/site.webmanifest`} />
        <link rel="shortcut icon" href={`${staticUrl}/favicon.ico`} />

        {/* Fonts load in parallel with the app stylesheet. A CSS @import would chain them behind it. */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link rel="stylesheet" href={GOOGLE_FONTS_URL} />

        {/* Production: Reactivated appends its stylesheet after </html>, so the first paint is unstyled.
            Linking it in <head> makes it render-blocking. The duplicate tag is a cache hit. */}
        {!isDev && <link rel="stylesheet" href={`${staticUrl}/dist/index.css`} />}

        {/* Development: inject critical CSS to prevent FOUC */}
        {isDev && <style dangerouslySetInnerHTML={{ __html: devCriticalCSS }} />}
      </head>
      <body>
        {/* In production, content is visible immediately (no opacity hiding) */}
        <div id="app-content" className={isDev ? "" : "loaded"}>
          <header className="sticky top-0 z-50 flex min-h-20 flex-wrap items-center justify-between border-b border-chapel-neutral-300 bg-chapel-neutral-50/95 px-5 sm:px-12">
            <div className="flex min-h-20 flex-1 items-center">
              <a href={reverse("catalog:search")} className="text-xs font-bold uppercase tracking-[0.15em] text-chapel-neutral-900 transition-colors hover:text-chapel-primary-500 sm:text-sm">
                Chapel of Mercy
              </a>
            </div>

            <div className="relative flex w-18 justify-center">
              {/* Centered Circular Logo overlapping the bottom border */}
              <div className="absolute top-1/2 flex h-18 w-18 -translate-y-1/2 items-center justify-center rounded-full border-4 border-chapel-neutral-50 shadow-sm bg-white overflow-hidden p-1.5">
                <img src={`${staticUrl}/rccgcm_logo.png`} alt="RCCG Chapel of Mercy Logo" className="h-full w-full object-contain scale-[1.3]" />
              </div>
            </div>

            <div className="flex min-h-20 flex-1 items-center justify-end gap-2 sm:gap-3">
              {user?.is_authenticated && (
                <a href={reverse("song_carts:list")} className="hidden min-h-11 items-center whitespace-nowrap text-sm font-bold text-chapel-neutral-700 hover:text-chapel-primary-500 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-chapel-primary-500 md:inline-flex">My submissions</a>
              )}
              {user?.is_authenticated && (
                <a href={song_cart.url} aria-label={`Your song cart, ${song_cart.song_count} ${song_cart.song_count === 1 ? "song" : "songs"}`} className="relative inline-flex min-h-11 min-w-11 items-center justify-center text-chapel-neutral-700 hover:text-chapel-primary-500 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-chapel-primary-500">
                  <svg aria-hidden="true" className="h-6 w-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M2 3h3l3 12h11l3-9H6" /><circle cx="9" cy="20" r="1" /><circle cx="19" cy="20" r="1" /></svg>
                  {song_cart.song_count > 0 && (
                    <span aria-hidden="true" className="absolute -right-0.5 -top-0.5 flex min-h-5 min-w-5 items-center justify-center rounded-full bg-chapel-primary-500 px-1 text-[0.65rem] font-bold leading-none text-white">{song_cart.song_count}</span>
                  )}
                </a>
              )}
              {user?.is_authenticated ? (
                <div className="dropdown dropdown-end">
                  <button type="button" aria-label="Account menu" tabIndex={0} className="flex items-center gap-2 cursor-pointer hover:bg-chapel-neutral-200 p-1.5 rounded-full transition-colors">
                    <div className="h-9 w-9 rounded-full bg-chapel-neutral-300 overflow-hidden flex items-center justify-center">
                      {user.avatar_url ? (
                        <img src={user.avatar_url} alt={user.full_name || "Profile"} className="h-full w-full object-cover" />
                      ) : (
                        <svg className="h-full w-full text-chapel-neutral-500" fill="currentColor" viewBox="0 0 24 24">
                          <path d="M24 20.993V24H0v-2.996A14.977 14.977 0 0112.004 15c4.904 0 9.26 2.354 11.996 5.993zM16.002 8.999a4 4 0 11-8 0 4 4 0 018 0z" />
                        </svg>
                      )}
                    </div>
                    <svg className="hidden h-4 w-4 text-chapel-neutral-600 mr-1 sm:block" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </button>
                  <ul tabIndex={0} className="dropdown-content z-1 menu p-2 shadow bg-white border border-chapel-neutral-200 rounded-box w-52 mt-2">
                    {user.is_staff && (
                      <li>
                        <a href="/admin/" className="w-full text-left text-chapel-neutral-700 hover:text-chapel-primary-600 font-medium px-4 py-2">Admin Portal</a>
                      </li>
                    )}
                    <li>
                      <a href={reverse("account_email")} className="w-full text-left text-chapel-neutral-700 hover:text-chapel-primary-600 font-medium px-4 py-2">Change Email</a>
                    </li>
                    <li>
                      <a href={reverse("account_change_password")} className="w-full text-left text-chapel-neutral-700 hover:text-chapel-primary-600 font-medium px-4 py-2">Change Password</a>
                    </li>
                    <li>
                      <a href={reverse("socialaccount_connections")} className="w-full text-left text-chapel-neutral-700 hover:text-chapel-primary-600 font-medium px-4 py-2">Account Connections</a>
                    </li>
                    <li>
                      <form method="post" action="/accounts/logout/" className="w-full p-0 flex">
                        <CSRFToken />
                        <button type="submit" className="w-full text-left text-chapel-neutral-700 hover:text-chapel-primary-600 font-medium px-4 py-2">Log Out</button>
                      </form>
                    </li>
                  </ul>
                </div>
              ) : (
                <a
                  href={signedOutHeaderLink.href}
                  className="border-b border-chapel-neutral-400 pb-1 text-[0.65rem] font-bold uppercase tracking-[0.16em] text-chapel-neutral-700 transition-colors hover:border-chapel-primary-500 hover:text-chapel-primary-500 sm:text-xs"
                >
                  {signedOutHeaderLink.label}
                </a>
              )}
            </div>
            {user?.is_authenticated && (
              <nav aria-label="Submissions" className="flex w-full justify-end border-t border-chapel-neutral-200 md:hidden">
                <a href={reverse("song_carts:list")} className="inline-flex min-h-11 items-center text-sm font-bold text-chapel-neutral-700 hover:text-chapel-primary-500 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-chapel-primary-500">My submissions</a>
              </nav>
            )}
          </header>

          <div className="w-full">
            {props.children}
          </div>
        </div>
      </body>
    </html>
  );
};
