import { defineConfig } from "vite";
import tailwindcss from "@tailwindcss/vite";

// Django serves /static/fonts/ through WhiteNoise. Vite resolves a root-absolute
// url(/static/fonts/x.woff2) against the project root, copies the file into static/dist
// and rewrites the URL to /x.woff2, which does not exist. Undo that after the bundle is
// built so the font files have exactly one home and one URL.
const keepDjangoStaticFonts = {
  name: "keep-django-static-fonts",
  generateBundle(_options, bundle) {
    const emittedFonts = Object.keys(bundle).filter((name) => name.endsWith(".woff2"));
    for (const asset of Object.values(bundle)) {
      if (asset.type !== "asset" || !asset.fileName.endsWith(".css")) continue;
      let css = String(asset.source);
      for (const font of emittedFonts) {
        css = css.replaceAll(`url(/${font})`, `url(/static/fonts/${font})`);
      }
      if (/url\(\/[^/)]+\.woff2\)/.test(css)) {
        this.error(`${asset.fileName} still references a font outside /static/fonts/.`);
      }
      asset.source = css;
    }
    for (const font of emittedFonts) delete bundle[font];
  },
};

export default defineConfig({
  // Django owns static assets. Its collectstatic output lives in public/, so Vite
  // must not treat that generated directory as a second source of frontend assets.
  publicDir: false,
  plugins: [tailwindcss(), keepDjangoStaticFonts],
});
