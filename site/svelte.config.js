import adapter from "@sveltejs/adapter-static";

// GitHub Pages base path is configurable: BASE_PATH=/repo-name npm run build (empty = site at the domain root).
const base = process.env.BASE_PATH ?? "";
// A base-path build is a GitHub Pages build: og:image and canonical URLs need the absolute site URL (decision 2026-10-12)
if (base && !process.env.SITE_URL) {
  throw new Error(`SITE_URL is not set. A build with BASE_PATH=${base} needs the absolute site URL, e.g. ` +
    `SITE_URL=https://<github-username>.github.io${base}`);
}
const out = process.env.BUILD_DIR ?? "build";

/** @type {import('@sveltejs/kit').Config} */
export default {
  kit: {
    adapter: adapter({ pages: out, assets: out, strict: true }),
    paths: { base },
    // the export contract writes site/public/data/ (pipeline/07_export.py); public/ is the static dir
    files: { assets: "public" },
    prerender: { entries: ["*"], handleMissingId: "fail" },
  },
};
