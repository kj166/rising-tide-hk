<script>
  // Bottom sheet on phones (< 900 px): drag handle, three snap points (peek / half / full, % of the map area).
  // On desktop the CSS ignores --sheet-h and the handle is hidden, so the panel keeps its floating / drawer layout.
  let { snap = $bindable("half"), class: cls = "", label = "panel", children, ...rest } = $props();
  const SNAPS = { peek: 25, half: 55, full: 90 };
  const ORDER = ["peek", "half", "full"];
  let el, drag = $state(null);
  const pct = $derived(drag ?? SNAPS[snap]);

  function down(e) {
    if (e.button > 0) return;
    const parent = el.parentElement.getBoundingClientRect(), y0 = e.clientY, h0 = SNAPS[snap];
    let moved = false;
    e.currentTarget.setPointerCapture(e.pointerId);
    const move = (ev) => {
      const d = ((y0 - ev.clientY) / parent.height) * 100;
      if (Math.abs(ev.clientY - y0) > 4) moved = true;
      if (moved) drag = Math.max(12, Math.min(94, h0 + d));
    };
    const up = () => {
      e.target.removeEventListener("pointermove", move);
      if (moved) snap = ORDER.reduce((a, b) => (Math.abs(SNAPS[b] - drag) < Math.abs(SNAPS[a] - drag) ? b : a));
      else snap = ORDER[(ORDER.indexOf(snap) + 1) % ORDER.length];   // tap cycles peek -> half -> full
      drag = null;
    };
    e.target.addEventListener("pointermove", move);
    e.target.addEventListener("pointerup", up, { once: true });
  }
  function key(e) {
    const i = ORDER.indexOf(snap);
    if (e.key === "ArrowUp" && i < 2) { snap = ORDER[i + 1]; e.preventDefault(); }
    if (e.key === "ArrowDown" && i > 0) { snap = ORDER[i - 1]; e.preventDefault(); }
  }
</script>

<aside bind:this={el} class="sheet {cls}" class:dragging={drag != null} data-snap={snap} style="--sheet-h:{pct}%" {...rest}>
  <div class="sheet-grip">
    <button class="sheet-handle" aria-label="Resize {label}: {snap === 'full' ? 'full height' : snap === 'half' ? 'half height' : 'peek'}. Tap to cycle, or use the arrow keys."
      onpointerdown={down} onkeydown={key} onclick={(e) => e.detail === 0 && key({ key: snap === "full" ? "ArrowDown" : "ArrowUp", preventDefault() {} })}><span aria-hidden="true"></span></button>
  </div>
  {@render children()}
</aside>
