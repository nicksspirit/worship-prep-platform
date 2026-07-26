import React from "react";

// Four Song Catalog directions on one throwaway route; D captures the selected refinement.
type View = "search" | "detail" | "preview";
type Variant = "a" | "b" | "c" | "d";

type Song = {
    id: string;
    title: string;
    author: string | null;
    copyright: string;
    updated: string;
    previewable: boolean;
    match: string;
    excerpt: string;
};

const songs: Song[] = [
    {
        id: "ew-0142",
        title: "Dawn Is Breaking",
        author: "Prototype sample",
        copyright: "Original prototype text",
        updated: "12 days ago",
        previewable: true,
        match: "dawn breaking mercy morning",
        excerpt: "Dawn is breaking, mercy meets us here. Hope is waking, love has drawn us near. We lift our voices, morning has begun.",
    },
    {
        id: "ew-0881",
        title: "Mercy Like the Morning",
        author: "A. Example",
        copyright: "Rights status unconfirmed",
        updated: "2 months ago",
        previewable: false,
        match: "mercy morning",
        excerpt: "Mercy like the morning, new with every light. Steady through the evening, holding through the night.",
    },
    {
        id: "ew-1250",
        title: "All Creation Sings",
        author: null,
        copyright: "Rights status unconfirmed",
        updated: "4 months ago",
        previewable: false,
        match: "creation sings",
        excerpt: "All creation sings, heaven and earth reply. Every living thing lifts a song on high.",
    },
    {
        id: "ew-2017",
        title: "Morning by Morning",
        author: "Traditional",
        copyright: "Public domain",
        updated: "8 months ago",
        previewable: true,
        match: "morning faithful",
        excerpt: "Morning by morning, faithfulness I see. Strength for today and bright hope carrying me.",
    },
];

const sampleSlides = [
    ["Dawn is breaking", "Mercy meets us here"],
    ["Hope is waking", "Love has drawn us near"],
    ["We lift our voices", "Morning has begun"],
];

const getAuthor = (song: Song) => song.author?.trim() || "N/A";

const Arrow = ({direction = "right"}: {direction?: "left" | "right"}) => (
    <svg
        aria-hidden="true"
        viewBox="0 0 24 24"
        fill="none"
        className={`h-5 w-5 ${direction === "left" ? "rotate-180" : ""}`}
    >
        <path d="M5 12h14M14 7l5 5-5 5" stroke="currentColor" strokeWidth="1.8" />
    </svg>
);

const SearchIcon = () => (
    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" className="h-5 w-5">
        <circle cx="11" cy="11" r="6.5" stroke="currentColor" strokeWidth="1.7" />
        <path d="m16 16 4 4" stroke="currentColor" strokeWidth="1.7" />
    </svg>
);

function usePrototypeRoute() {
    const [variant, setVariantState] = React.useState<Variant>("a");
    const [view, setViewState] = React.useState<View>("search");

    const update = (nextVariant: Variant, nextView: View) => {
        window.history.replaceState({}, "", `?variant=${nextVariant}&view=${nextView}`);
        setVariantState(nextVariant);
        setViewState(nextView);
    };

    React.useEffect(() => {
        const initial = new URLSearchParams(window.location.search);
        const initialVariant = initial.get("variant");
        const initialView = initial.get("view");
        if (["a", "b", "c", "d"].includes(initialVariant || "")) {
            setVariantState(initialVariant as Variant);
        }
        if (["search", "detail", "preview"].includes(initialView || "")) {
            setViewState(initialView as View);
        }
    }, []);

    React.useEffect(() => {
        const onKey = (event: KeyboardEvent) => {
            if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
            const target = event.target as HTMLElement | null;
            if (target?.matches("input, textarea, [contenteditable='true']")) return;
            const order: Variant[] = ["a", "b", "c", "d"];
            const offset = event.key === "ArrowRight" ? 1 : -1;
            const next = order[(order.indexOf(variant) + offset + order.length) % order.length];
            update(next, view);
        };
        window.addEventListener("keydown", onKey);
        return () => window.removeEventListener("keydown", onKey);
    }, [variant, view]);

    return {
        variant,
        view,
        setView: (next: View) => update(variant, next),
        setVariant: (next: Variant) => update(next, view),
    };
}

function RightsBadge({song, inverse = false}: {song: Song; inverse?: boolean}) {
    return (
        <span className={`catalog-rights ${inverse ? "catalog-rights--inverse" : ""}`}>
            <span className={song.previewable ? "catalog-dot catalog-dot--ok" : "catalog-dot"} />
            {song.previewable ? "Preview available" : "Metadata only"}
        </span>
    );
}

function PrototypeSwitcher({
    variant,
    setVariant,
}: {
    variant: Variant;
    setVariant: (variant: Variant) => void;
}) {
    const labels: Record<Variant, string> = {
        a: "Hymnal Index",
        b: "Control Room",
        c: "Sunday Window",
        d: "Hymnal Excerpts",
    };
    if (import.meta.env.PROD) return null;

    return (
        <aside className="catalog-switcher" aria-label="Prototype variants">
            <span className="catalog-switcher__eyebrow">Prototype</span>
            {(["a", "b", "c", "d"] as Variant[]).map((item) => (
                <button
                    key={item}
                    className={variant === item ? "is-active" : ""}
                    onClick={() => setVariant(item)}
                    aria-pressed={variant === item}
                >
                    <b>{item.toUpperCase()}</b>
                    <span>{labels[item]}</span>
                </button>
            ))}
            <span className="catalog-switcher__hint">← →</span>
        </aside>
    );
}

function SearchField({
    query,
    setQuery,
    dark = false,
}: {
    query: string;
    setQuery: (value: string) => void;
    dark?: boolean;
}) {
    return (
        <label className={`catalog-search ${dark ? "catalog-search--dark" : ""}`}>
            <SearchIcon />
            <span className="sr-only">Search songs</span>
            <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search a title or lyric…"
            />
            <kbd>⌘ K</kbd>
        </label>
    );
}

function ProjectionStage({onBack, variant}: {onBack: () => void; variant: Variant}) {
    const [slide, setSlide] = React.useState(0);
    const next = () => setSlide((value) => Math.min(value + 1, sampleSlides.length - 1));
    const previous = () => setSlide((value) => Math.max(value - 1, 0));

    React.useEffect(() => {
        const onKey = (event: KeyboardEvent) => {
            if (event.key === "Escape") onBack();
            if (event.key === "ArrowRight" || event.key === " ") next();
            if (event.key === "ArrowLeft") previous();
        };
        window.addEventListener("keydown", onKey);
        return () => window.removeEventListener("keydown", onKey);
    }, [onBack]);

    return (
        <section className={`projection-stage projection-stage--${variant}`}>
            <header>
                <button onClick={onBack}><Arrow direction="left" /> Exit preview</button>
                <span>Approximate projection · 16:9</span>
                <span>{slide + 1} / {sampleSlides.length}</span>
            </header>
            <div className="projection-stage__screen">
                <div className="projection-stage__glow" />
                <div className="projection-stage__lyrics" key={slide}>
                    {sampleSlides[slide].map((line) => <p key={line}>{line}</p>)}
                </div>
            </div>
            <footer>
                <button onClick={previous} disabled={slide === 0}><Arrow direction="left" /> Previous</button>
                <div>
                    {sampleSlides.map((_, index) => (
                        <button
                            key={index}
                            aria-label={`Go to slide ${index + 1}`}
                            className={slide === index ? "is-active" : ""}
                            onClick={() => setSlide(index)}
                        />
                    ))}
                </div>
                <button onClick={next} disabled={slide === sampleSlides.length - 1}>Next <Arrow /></button>
            </footer>
        </section>
    );
}

function Lyrics() {
    return (
        <div className="catalog-lyrics">
            {sampleSlides.map((lines, index) => (
                <section key={index}>
                    <span>{index === 1 ? "Chorus" : `Verse ${index === 0 ? 1 : 2}`}</span>
                    <p>{lines[0]}<br />{lines[1]}</p>
                </section>
            ))}
        </div>
    );
}

function VariantA({view, setView}: {view: View; setView: (view: View) => void}) {
    const [query, setQuery] = React.useState("morning");
    const filtered = songs.filter((song) => song.match.includes(query.toLowerCase()));
    if (view === "preview") return <ProjectionStage variant="a" onBack={() => setView("detail")} />;

    if (view === "detail") {
        const song = songs[0];
        return (
            <main className="catalog-a catalog-a--detail">
                <nav><button onClick={() => setView("search")}><Arrow direction="left" /> Back to results</button></nav>
                <article>
                    <header>
                        <div>
                            <p className="catalog-kicker">Song no. 0142 · EasyWorship catalog</p>
                            <h1>{song.title}</h1>
                            <p className="catalog-byline">{getAuthor(song)}</p>
                        </div>
                        <button className="catalog-preview-button" onClick={() => setView("preview")}>
                            <span>▶</span> Preview projection
                        </button>
                    </header>
                    <div className="catalog-a__detail-grid">
                        <Lyrics />
                        <aside>
                            <p className="catalog-kicker">About this song</p>
                            <dl>
                                <div><dt>Copyright</dt><dd>{song.copyright}</dd></div>
                                <div><dt>Last changed</dt><dd>{song.updated}</dd></div>
                                <div><dt>Source ID</dt><dd>{song.id}</dd></div>
                                <div><dt>Verses</dt><dd>3</dd></div>
                            </dl>
                            <RightsBadge song={song} />
                            <p className="catalog-note">Lyrics are cleaned for reading. The preview groups them into approximate EasyWorship slides.</p>
                        </aside>
                    </div>
                </article>
            </main>
        );
    }

    return (
        <main className="catalog-a">
            <header className="catalog-a__masthead">
                <p className="catalog-kicker">Chapel of Mercy · Song Catalog</p>
                <h1>Find the song<br /><i>you’re reaching for.</i></h1>
                <p>Search the church library by title or any words you remember.</p>
            </header>
            <SearchField query={query} setQuery={setQuery} />
            <div className="catalog-a__result-meta"><span>{filtered.length} songs</span><span>Catalog updated 12 days ago</span></div>
            <section className="catalog-a__results">
                {filtered.length ? filtered.map((song, index) => (
                    <button key={song.id} onClick={() => setView("detail")}>
                        <span className="catalog-a__number">{String(index + 1).padStart(2, "0")}</span>
                        <span><b>{song.title}</b><small>{getAuthor(song)}</small></span>
                        <RightsBadge song={song} />
                        <Arrow />
                    </button>
                )) : (
                    <div className="catalog-empty"><h2>No songs found</h2><p>Try fewer words or check the spelling.</p></div>
                )}
            </section>
        </main>
    );
}

function VariantB({view, setView}: {view: View; setView: (view: View) => void}) {
    const [query, setQuery] = React.useState("mercy");
    if (view === "preview") return <ProjectionStage variant="b" onBack={() => setView("detail")} />;
    const selected = songs[0];
    return (
        <main className="catalog-b">
            <header className="catalog-b__topbar">
                <div><span className="catalog-b__mark">CM</span><b>SONG FINDER</b></div>
                <span><i /> Catalog online · updated 12d ago</span>
            </header>
            <div className="catalog-b__workspace">
                <aside>
                    <p className="catalog-b__label">Library / 2,283 songs</p>
                    <SearchField query={query} setQuery={setQuery} dark />
                    <div className="catalog-b__filters">
                        <button className="is-active">All</button><button>Previewable</button><button>Metadata</button>
                    </div>
                    <div className="catalog-b__list">
                        {songs.filter((song) => song.match.includes(query.toLowerCase())).map((song, index) => (
                            <button
                                key={song.id}
                                className={index === 0 ? "is-active" : ""}
                                onClick={() => setView("detail")}
                            >
                                <span>{song.title}<small>{getAuthor(song)}</small></span>
                                <RightsBadge song={song} inverse />
                            </button>
                        ))}
                    </div>
                </aside>
                <article className={view === "search" ? "catalog-b__welcome" : ""}>
                    {view === "search" ? (
                        <div>
                            <span className="catalog-b__pulse"><SearchIcon /></span>
                            <h1>Choose a song</h1>
                            <p>Search results stay in view while you inspect lyrics and presentation readiness.</p>
                        </div>
                    ) : (
                        <>
                            <header>
                                <div><p className="catalog-b__label">Selected song · {selected.id}</p><h1>{selected.title}</h1><p>{selected.author}</p></div>
                                <button onClick={() => setView("preview")}>▶ Open preview</button>
                            </header>
                            <div className="catalog-b__detail">
                                <Lyrics />
                                <aside>
                                    <p className="catalog-b__label">Song data</p>
                                    <dl>
                                        <dt>Rights</dt><dd>{selected.copyright}</dd>
                                        <dt>Changed</dt><dd>{selected.updated}</dd>
                                        <dt>Slides</dt><dd>3 estimated</dd>
                                    </dl>
                                    <p className="catalog-note">Projection is an approximation. Slide breaks may differ in EasyWorship.</p>
                                </aside>
                            </div>
                        </>
                    )}
                </article>
            </div>
        </main>
    );
}

function VariantC({view, setView}: {view: View; setView: (view: View) => void}) {
    const [query, setQuery] = React.useState("");
    if (view === "preview") return <ProjectionStage variant="c" onBack={() => setView("detail")} />;
    if (view === "detail") {
        const song = songs[0];
        return (
            <main className="catalog-c catalog-c--detail">
                <button className="catalog-c__back" onClick={() => setView("search")}><Arrow direction="left" /> Songs</button>
                <article>
                    <div className="catalog-c__title">
                        <p>Found in your church library</p><h1>{song.title}</h1><span>{getAuthor(song)} · changed {song.updated}</span>
                    </div>
                    <div className="catalog-c__paper"><Lyrics /></div>
                    <aside>
                        <RightsBadge song={song} />
                        <h2>See it on screen</h2>
                        <p>Preview the likely slide breaks and projected scale before service.</p>
                        <button onClick={() => setView("preview")}>Preview projection <Arrow /></button>
                        <small>Approximation · 3 slides · 16:9</small>
                    </aside>
                </article>
            </main>
        );
    }
    return (
        <main className="catalog-c">
            <header>
                <p>Chapel of Mercy song library</p>
                <h1>What would you<br />like to sing?</h1>
            </header>
            <SearchField query={query} setQuery={setQuery} />
            <p className="catalog-c__prompt">{query ? `Matches for “${query}”` : "Try “mercy”, “morning”, or a line you remember"}</p>
            <section className="catalog-c__cards">
                {songs.filter((song) => !query || song.match.includes(query.toLowerCase())).map((song, index) => (
                    <button key={song.id} onClick={() => setView("detail")} style={{"--delay": `${index * 60}ms`} as React.CSSProperties}>
                        <span className="catalog-c__index">{index + 1}</span>
                        <b>{song.title}</b>
                        <small>{getAuthor(song)}</small>
                        <RightsBadge song={song} />
                        <span className="catalog-c__arrow"><Arrow /></span>
                    </button>
                ))}
            </section>
        </main>
    );
}

function VariantD({view, setView}: {view: View; setView: (view: View) => void}) {
    const [query, setQuery] = React.useState("");
    const normalizedQuery = query.trim().toLowerCase();
    const filtered = songs.filter((song) => {
        const searchableText = [
            song.title,
            song.author,
            song.match,
            song.excerpt,
        ].join(" ").toLowerCase();
        return !normalizedQuery || searchableText.includes(normalizedQuery);
    });

    if (view === "preview") {
        return <ProjectionStage variant="d" onBack={() => setView("detail")} />;
    }

    if (view === "detail") {
        const song = songs[0];
        return (
            <main className="catalog-d catalog-d--detail">
                <nav>
                    <button onClick={() => setView("search")}>
                        <Arrow direction="left" /> Back to songs
                    </button>
                </nav>
                <article>
                    <header>
                        <div>
                            <p className="catalog-kicker">
                                Song no. 0142 · EasyWorship catalog
                            </p>
                            <h1>{song.title}</h1>
                            <p className="catalog-byline">Written by {getAuthor(song)}</p>
                        </div>
                        <button
                            className="catalog-preview-button"
                            onClick={() => setView("preview")}
                        >
                            <span>▶</span> Preview projection
                        </button>
                    </header>
                    <div className="catalog-d__detail-grid">
                        <Lyrics />
                        <aside>
                            <p className="catalog-kicker">Song details</p>
                            <dl>
                                <div><dt>Author</dt><dd>{getAuthor(song)}</dd></div>
                                <div><dt>Copyright</dt><dd>{song.copyright}</dd></div>
                                <div><dt>Last changed</dt><dd>{song.updated}</dd></div>
                                <div><dt>Source ID</dt><dd>{song.id}</dd></div>
                            </dl>
                            <p className="catalog-note">
                                Lyrics are cleaned for reading. Projection preview uses
                                approximate slide breaks.
                            </p>
                        </aside>
                    </div>
                </article>
            </main>
        );
    }

    const suggestions = ["mercy", "morning", "creation"];
    return (
        <main className="catalog-d">
            <header className="catalog-d__masthead">
                <p className="catalog-kicker">Chapel of Mercy · Song Catalog</p>
                <div>
                    <h1>Find the song<br /><i>you’re reaching for.</i></h1>
                    <p>Search by title, author, or any lyric you remember.</p>
                </div>
            </header>

            <section className="catalog-d__search-block" aria-label="Song search">
                <SearchField query={query} setQuery={setQuery} />
                <div className="catalog-d__suggestions">
                    <span>Try</span>
                    {suggestions.map((suggestion) => (
                        <button key={suggestion} onClick={() => setQuery(suggestion)}>
                            {suggestion}
                        </button>
                    ))}
                </div>
            </section>

            <div className="catalog-d__result-meta" aria-live="polite">
                <span>{filtered.length} {filtered.length === 1 ? "song" : "songs"}</span>
                <span>Catalog updated 12 days ago</span>
            </div>

            <section className="catalog-d__results" aria-label="Search results">
                {filtered.length ? filtered.map((song) => (
                    <button key={song.id} onClick={() => setView("detail")}>
                        <span className="catalog-d__song">
                            <b>{song.title}</b>
                            <small>{getAuthor(song)}</small>
                        </span>
                        <span className="catalog-d__excerpt">
                            <small>Lyric excerpt</small>
                            <span>{song.excerpt}</span>
                        </span>
                        <span className="catalog-d__open" aria-hidden="true">
                            <Arrow />
                        </span>
                    </button>
                )) : (
                    <div className="catalog-empty">
                        <h2>No songs found</h2>
                        <p>Try one word from the title or lyric.</p>
                        <button onClick={() => setQuery("")}>Clear search</button>
                    </div>
                )}
            </section>
        </main>
    );
}

export const Template = () => {
    const route = usePrototypeRoute();
    return (
        <>
            <a className="catalog-skip" href="#catalog-main">Skip to content</a>
            <div id="catalog-main">
                {route.variant === "a" && <VariantA view={route.view} setView={route.setView} />}
                {route.variant === "b" && <VariantB view={route.view} setView={route.setView} />}
                {route.variant === "c" && <VariantC view={route.view} setView={route.setView} />}
                {route.variant === "d" && <VariantD view={route.view} setView={route.setView} />}
            </div>
            <PrototypeSwitcher variant={route.variant} setVariant={route.setVariant} />
        </>
    );
};
