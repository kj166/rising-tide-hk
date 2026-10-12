<script>
  // Mangkhut replay at one asset as one elevation profile: sea on the left, ground rising to the entrance, a step up to
  // the lowest floor inside the building. Relative offsets only (cm from margins.json); no site levels in mPD.
  // Vertical scale exaggerated (1 cm = PX px); horizontal distances schematic.
  import { COLORS } from "$lib/data.js";
  let { aboveCm, belowCm, name = "the property" } = $props();
  const PX = 3.2, yE = 132, X_WALL = 170, X_END = 250, X_LAB = 274, X_BEND = 258;
  const yW = $derived(yE - aboveCm * PX), yF = $derived(yE - (aboveCm + belowCm) * PX);
  // right-hand labels: each starts centred on its level, then is pushed down until it clears the one above by GAP
  // (viewBox units; >= 8 px on screen at 390 px wide). Short leader lines join a moved label to its level.
  const GAP = 11, H = [14, 30, 14];   // label heights: "Lowest floor", two-line sea label, "Entrance"
  const lab = $derived.by(() => {
    const top = [];
    [yF, yW, yE].forEach((c, i) => { top[i] = Math.max(c - H[i] / 2, i ? top[i - 1] + H[i - 1] + GAP : -Infinity); });
    return top.map((t, i) => t + H[i] / 2);   // label centres
  });
  const ground = $derived(`M0 214 V182 L30 182 C70 182 80 ${yE} 120 ${yE} H${X_WALL} V${yF} H${X_END} V210 Z`);
  const water = $derived(`M0 ${yW} H${X_WALL} V${yE} H120 C80 ${yE} 70 182 30 182 H0 Z`);
</script>

<figure class="gauge">
  <svg viewBox="0 0 420 214" role="img" aria-labelledby="gauge-t gauge-d">
    <title id="gauge-t">Typhoon Mangkhut replayed at {name}</title>
    <desc id="gauge-d">Elevation profile from the sea to the building: the replayed sea level is {aboveCm} cm above the entrance and {belowCm} cm below the lowest floor. Vertical scale exaggerated.</desc>
    <path class="water" d={water} fill={COLORS.tealLight} opacity=".75" />
    <path d={ground} fill="#E9E4DA" stroke={COLORS.navy} stroke-width="1.5" stroke-linejoin="round" />
    <rect x={X_WALL} y="14" width={X_END - X_WALL} height={yF - 14} fill="none" stroke={COLORS.navy} stroke-width="1.5" stroke-dasharray="3 3" />
    <text x={(X_WALL + X_END) / 2} y="34" text-anchor="middle" font-size="13" fill={COLORS.inkMuted}>Building</text>
    <text x="8" y="204" font-size="13" fill={COLORS.navy}>Sea</text>
    <!-- level guides with leader lines to the right-hand labels -->
    <g stroke={COLORS.inkMuted} stroke-width="1" fill="none">
      <polyline points="{X_END},{yF} {X_BEND},{yF} {X_LAB - 4},{lab[0]}" stroke-dasharray="1 3" />
      <polyline points="{X_WALL},{yE} {X_BEND},{yE} {X_LAB - 4},{lab[2]}" stroke-dasharray="1 3" />
      <line x1={X_BEND} x2={X_LAB - 4} y1={yW} y2={lab[1]} />
    </g>
    <line x1="0" x2={X_BEND} y1={yW} y2={yW} stroke={COLORS.navy} stroke-width="2" stroke-dasharray="6 4" />
    <g font-size="14" fill={COLORS.navy}>
      <text class="g-floor" x={X_LAB} y={lab[0] + 5}>Lowest floor</text>
      <text class="g-sea" x={X_LAB} y={lab[1] - 3} font-weight="600"><tspan>Mangkhut sea</tspan><tspan x={X_LAB} dy="16">level, replayed</tspan></text>
      <text class="g-entr" x={X_LAB} y={lab[2] + 5}>Entrance</text>
    </g>
    <!-- offsets -->
    <g font-size="13" font-weight="600" fill={COLORS.navy} stroke={COLORS.navy}>
      <line x1="164" x2="164" y1={yE} y2={yW} stroke-width="1.5" />
      <text x="158" y={(yE + yW) / 2 + 5} text-anchor="end" stroke="none">+{aboveCm} cm above entrance</text>
      <line x1="178" x2="178" y1={yW} y2={yF} stroke-width="1.5" />
      <text x="164" y={(yW + yF) / 2 + 5} text-anchor="end" stroke="none">{belowCm} cm below floor</text>
    </g>
  </svg>
  <figcaption>Vertical scale exaggerated.</figcaption>
</figure>
