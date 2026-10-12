// Sentence templates. Every figure is filled from the export (site/public/data); the templates contain no numbers.
// tests/test_site_copy.py renders them with the real export and compares against the approved wording.
import { hkdRange, ordinal, cleanName } from "./format.js";

const find = (arr, sc, q, rp) => arr.find((x) => x.scenario === sc && x.slr_quantile === q && x.return_period === rp);

// The Quayside margin sentence (approved wording, decision 2026-10-08). Throws if the export no longer supports a
// clause, so a pipeline change cannot silently publish a wrong claim.
export function marginSentence(m) {
  const mid = find(m.margins_cm, "ssp245_2050", "median", 100);
  const high = find(m.margins_cm, "ssp245_2050", "high", 100);
  const hi85 = find(m.margins_cm, "ssp585_2050", "high", 100);
  const r200 = m.reached.find((x) => x.scenario === "ssp245_2050" && x.slr_quantile === "median");
  if (!(mid?.margin_cm > 0 && high?.margin_cm > 0 && hi85?.margin_cm < 0 && r200?.reached))
    throw new Error(`margin facts for ${m.name} no longer match the approved sentence`);
  return `${cleanName(m.name)}, Link's ${ordinal(m.value_rank_hk)} most valuable Hong Kong property, is protected from the 2050 ` +
    `1-in-${mid.return_period}-year sea level (SSP2-4.5, median) by a margin of about ${mid.margin_cm} cm of ground on the route from the sea. ` +
    `The high end of that scenario's range leaves about ${high.margin_cm} cm, the high end of SSP5-8.5 erases it, ` +
    `and the rarer 1-in-${r200.return_period}-year level already reaches the site.`;
}

// "more than triples": both ends of the 2050 range at least 3 x the 1995–2014 range (else the build fails)
export function tripleCheck(P) {
  const lo = P.ssp245_2050.eal_total_hkd[0] / P.baseline.eal_total_hkd[0];
  const hi = P.ssp245_2050.eal_total_hkd[1] / P.baseline.eal_total_hkd[1];
  if (!(lo > 3 && hi > 3)) throw new Error(`"more than triples" not supported: ${lo.toFixed(2)} / ${hi.toFixed(2)}`);
  return [lo, hi];
}

export function subhead(portfolio) {
  tripleCheck(portfolio.scenarios);
  const f = portfolio.scenarios.ssp245_2050;
  return `Just ${f.n_assets_with_coastal_loss} of Link's ${portfolio.n_assets} assessed Hong Kong properties carry all of its coastal flood risk. ` +
    "That risk more than triples by 2050, and targeted flood barriers could pay for themselves.";
}

export const ealSentence = (P) =>
  `Expected coastal flood loss more than triples by 2050: ${hkdRange(P.baseline.eal_total_hkd)} a year becomes ${hkdRange(P.ssp245_2050.eal_total_hkd)}.`;
