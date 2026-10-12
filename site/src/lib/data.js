import { base } from "$app/paths";

export const dataUrl = (name) => `${base}/data/${name}`;
export const imgUrl = (p) => `${base}/${p}`;
export async function getJSON(fetchFn, name) {
  const r = await fetchFn(dataUrl(name));
  if (!r.ok) throw new Error(`${name}: HTTP ${r.status}`);
  return r.json();
}

export const COLORS = {
  navy: "#0B1F33", teal: "#0E7C86", tealInk: "#0B6B73", tealLight: "#7FD1C7", foam: "#E6F4F1", paper: "#FAFAF7",
  seaMap: "#CFE5E2", inkMuted: "#4A5968", none: "#5E7080", line: "#D5DEE3",
  r1: "#F2D7A0", r2: "#F0A04B", r3: "#E4572E", r4: "#9E2A2B",
};
export const RP_CLASSES = [
  { key: "r4", label: "1-in-10 years or more often", color: COLORS.r4, test: (rp) => rp <= 10 },
  { key: "r3", label: "1-in-20 to 1-in-50 years", color: COLORS.r3, test: (rp) => rp >= 20 && rp <= 50 },
  { key: "r2", label: "1-in-100 years", color: COLORS.r2, test: (rp) => rp === 100 },
  { key: "r1", label: "1-in-200 years", color: COLORS.r1, test: (rp) => rp === 200 },
];
export const CLASS3 = { low: COLORS.r1, medium: COLORS.r2, high: COLORS.r4 };
export const rpClass = (rp) => (rp == null ? "none" : RP_CLASSES.find((c) => c.test(rp))?.key ?? "none");
export const rpColor = (rp) => RP_CLASSES.find((c) => c.key === rpClass(rp))?.color ?? COLORS.none;
export const SCENARIOS = ["baseline", "ssp245_2050", "ssp585_2050", "ssp585_2100"];
export const SHORT = { baseline: "1995–2014", ssp245_2050: "2050 · SSP2-4.5", ssp585_2050: "2050 · SSP5-8.5", ssp585_2100: "2100 · SSP5-8.5" };
export const SCENARIO_NOTE = {
  baseline: "1995–2014 climate: the base period of HKO's projections, not \"today\".",
  ssp245_2050: "SSP2-4.5, 2041–2060: a middle-of-the-road emissions pathway.",
  ssp585_2050: "SSP5-8.5, 2041–2060: a very high emissions pathway.",
  ssp585_2100: "SSP5-8.5, 2081–2100: sensitivity only.",
};

// per-scenario fields copied onto feature properties for MapLibre expressions
export function flattenAssets(fc) {
  for (const f of fc.features) {
    const p = f.properties;
    for (const s of SCENARIOS) {
      const d = p.scenarios[s];
      p[`rp_${s}`] = d.rp ?? -1;
      p[`rp_class_${s}`] = rpClass(d.rp);
      p[`tier_${s}`] = d.tier_absolute ?? "";
      p[`loss_${s}`] = !!d.has_coastal_loss;
      p[`watch_${s}`] = d.watch.length ? 1 : 0;
      p[`hot_${s}`] = Object.keys(d.hotspot ?? {}).length ? 1 : 0;
    }
  }
  return fc;
}
export const rpColorExpr = (s) => ["match", ["get", `rp_class_${s}`], ...RP_CLASSES.flatMap((c) => [c.key, c.color]), COLORS.none];
