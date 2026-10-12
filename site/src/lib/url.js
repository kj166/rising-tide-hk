import { replaceState } from "$app/navigation";

// Shareable state in the query string: scenario, asset, hazard (+ sea, compare, filter on Explore)
export function getQuery(key, fallback = null) {
  if (typeof location === "undefined") return fallback;
  return new URLSearchParams(location.search).get(key) ?? fallback;
}
export function setQuery(obj) {
  const u = new URL(location.href);
  for (const [k, v] of Object.entries(obj)) (v == null || v === "" || v === false) ? u.searchParams.delete(k) : u.searchParams.set(k, v);
  if (u.href !== location.href) replaceState(u, {});
}
