// Formatting only: every number shown comes from site/public/data (pipeline/07_export.py), already rounded there.
function unit(x) { return x >= 1e9 ? ["bn", 1e9] : x >= 1e6 ? ["M", 1e6] : x >= 1e3 ? ["k", 1e3] : ["", 1]; }
const trim = (v) => String(+v.toPrecision(2));
export function hkd(x) { if (x == null) return "–"; if (x === 0) return "HK$0"; const [u, d] = unit(x); return `HK$${trim(x / d)}${u}`; }
// one format for every range: both ends in the upper end's unit, e.g. "HK$0.43–2.4M" (never "HK$430k–HK$2.4M")
export function hkdRange([a, b]) {
  if (a === b) return hkd(a);
  const [u, d] = unit(b);
  return `HK$${a === 0 ? 0 : trim(a / d)}–${trim(b / d)}${u}`;
}
// shares are exported at 2 significant figures; shown without decimals (decision 2026-10-08)
export const pctRange = ([a, b]) => `${Math.round(a)}–${Math.round(b)}%`;
export const rpText = (rp) => (rp == null ? "not within 200 years" : `1-in-${rp}-year`);
export const ORDINAL = ["zeroth", "first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth"];
export const ordinal = (n) => ORDINAL[n] ?? `${n}th`;
export const cleanName = (n) => String(n).replace(/\s+/g, " ").trim();
export const cmToM = (cm) => (cm / 100).toFixed(2);
