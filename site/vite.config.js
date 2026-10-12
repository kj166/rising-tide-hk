import { sveltekit } from "@sveltejs/kit/vite";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [sveltekit()],
  define: {
    // SHOW_LANDSD_AERIAL=false (build environment) hides the LandsD aerial thumbnail and logo (PUBLISH_MANIFEST item 7)
    __SHOW_LANDSD_AERIAL__: JSON.stringify(process.env.SHOW_LANDSD_AERIAL !== "false"),
    // absolute origin + base for og:image / canonical (e.g. https://user.github.io/repo); empty = relative URLs
    __SITE_URL__: JSON.stringify(process.env.SITE_URL ?? ""),
  },
  build: { target: "es2022", chunkSizeWarningLimit: 1200 },
});
