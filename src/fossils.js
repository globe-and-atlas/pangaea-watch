// "What's here": nearest fossil finds to home's ANCIENT position, searched in ancient
// geography. Every fossil in data/fossil_index.json is already placed where its rock was at
// each keyframe (same MERDITH2021 model as home), so cross-plate neighbours count -- in the
// Triassic a Texas site can find its Pangaean neighbours in Africa or South America.
// Mirrors whats_here_at() in execution/build_fossil_index.py.

export const TIERS = [["here", 400], ["nearby", 1200], ["region", 3000]];
// Headline groups get first claim on every tier; the rest (ammonites, turtles, crocs, early
// mammals) only fill in when no headline taxon is within the widest tier -- ammonites are so
// abundant they would otherwise headline every coastal scene.
export const HEADLINE_GROUPS = ["dinosaur", "bird", "pterosaur", "marine reptile", "archosaur"];
const MAX_TAXA = 3;
const R_KM = 6371;

function distKm(lat1, lon1, lat2, lon2) {
  const r = Math.PI / 180;
  const a = Math.sin(((lat2 - lat1) * r) / 2) ** 2 +
    Math.cos(lat1 * r) * Math.cos(lat2 * r) * Math.sin(((lon2 - lon1) * r) / 2) ** 2;
  return 2 * R_KM * Math.asin(Math.min(1, Math.sqrt(a)));
}

/**
 * @param {object} index parsed fossil_index.json
 * @param {number} frame Mesozoic keyframe index
 * @param {number} lat home paleo latitude at that keyframe
 * @param {number} lon home paleo longitude at that keyframe
 */
export function whatsHere(index, frame, lat, lon) {
  const marine = new Set(index.meta.marine_groups);
  const headline = new Set(HEADLINE_GROUPS);
  // Distances once per entry, best (nearest) record per genus
  const best = new Map();
  let nearest = null;
  for (const [ri, plat10, plon10] of index.frames[frame] ?? []) {
    const d = distKm(lat, lon, plat10 / 10, plon10 / 10);
    if (d > TIERS[TIERS.length - 1][1]) continue;
    const [ti, maxMa, minMa, fi] = index.records[ri];
    const [genus, group, trace] = index.taxa[ti];
    const km = Math.floor(d + 0.5); // same half-up rounding as whats_here_at()
    if (!nearest || km < nearest.distKm) nearest = { distKm: km, group };
    const prev = best.get(genus);
    if (!prev || km < prev.distKm) {
      best.set(genus, { genus, group, trace: !!trace, distKm: km,
        formation: index.formations[fi], rangeMa: [maxMa, minMa] });
    }
  }
  const all = [...best.values()];
  // "Marine" only when a marine find is close (here tier): a far-off ammonite says nothing
  // about whether home itself was under the sea
  const env = { nearestKm: nearest?.distKm ?? null,
    marine: !!nearest && marine.has(nearest.group) && nearest.distKm <= TIERS[0][1] };
  for (const pool of [all.filter((x) => headline.has(x.group)), all]) {
    for (const [tier, radius] of TIERS) {
      const inTier = pool.filter((x) => x.distKm <= radius);
      if (!inTier.length) continue;
      inTier.sort((a, b) => (a.group !== "dinosaur") - (b.group !== "dinosaur") ||
        a.distKm - b.distKm || (a.genus < b.genus ? -1 : a.genus > b.genus ? 1 : 0));
      return { tier, radiusKm: radius, taxa: inTier.slice(0, MAX_TAXA), ...env };
    }
  }
  return { tier: "none", radiusKm: TIERS[TIERS.length - 1][1], taxa: [], ...env };
}
