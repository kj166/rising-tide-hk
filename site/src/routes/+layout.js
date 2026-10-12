import { getJSON } from "$lib/data.js";
import { base } from "$app/paths";

export const prerender = true;
export const trailingSlash = "always";

// small exported JSON shared by every page (large GeoJSON is fetched client-side by the map pages)
export async function load({ fetch }) {
  const names = ["portfolio", "meta", "scorecard", "adaptation", "heat", "margins"];
  const vals = await Promise.all(names.map((n) => getJSON(fetch, `${n}.json`)));
  const photos = await (await fetch(`${base}/img/photos.json`)).json();
  return { ...Object.fromEntries(names.map((n, i) => [n, vals[i]])), photos };
}
