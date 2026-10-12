// MapLibre helpers (loaded lazily by the pages). Basemap: OpenFreeMap positron, no API key.
import { COLORS } from "./data.js";

export const OFM_STYLE = "https://tiles.openfreemap.org/styles/positron";
export const HK_BOUNDS = [[113.88, 22.18], [114.36, 22.53]];
export const DTM_BOUNDS = [113.8242, 22.138, 114.4441, 22.5719];

import cssUrl from "maplibre-gl/dist/maplibre-gl.css?url";

// MapLibre JS and CSS load only on pages that show a map (keeps them out of the render-blocking path)
export async function loadMapLibre() {
  if (!document.querySelector("link[data-maplibre]")) {
    const l = Object.assign(document.createElement("link"), { rel: "stylesheet", href: cssUrl });
    l.dataset.maplibre = "";
    document.head.append(l);
  }
  const { default: maplibregl } = await import("maplibre-gl");
  return maplibregl;
}

export function themeLight(map) {
  const set = (id, prop, v) => map.getLayer(id) && map.setPaintProperty(id, prop, v);
  set("background", "background-color", COLORS.paper);
  set("water", "fill-color", COLORS.seaMap);
  set("park", "fill-color", "#E3EEE6");
  set("landcover_wood", "fill-color", "#E3EEE6");
  set("building", "fill-color", "#ECEAE3");
}

// 3D buildings from OpenFreeMap (OpenMapTiles render_height), shown from zoom 14.5
export function add3dBuildings(map, before) {
  if (map.getLayer("bldg-3d")) return;
  map.addLayer({ id: "bldg-3d", type: "fill-extrusion", source: "openmaptiles", "source-layer": "building", minzoom: 14.5,
    paint: { "fill-extrusion-color": "#E4E1D8", "fill-extrusion-opacity": 0.85,
      "fill-extrusion-height": ["coalesce", ["get", "render_height"], 8], "fill-extrusion-base": ["coalesce", ["get", "render_min_height"], 0] } }, before);
}

// our terrain tiles (LandsD 5 m DTM, terrarium) from meta.json; hillshade always, 3D terrain on request
export function terrainSource(meta, dataUrl) {
  const t = meta.terrain;
  return { type: "raster-dem", tiles: [new URL(dataUrl(t.tiles), location.href).href.replaceAll("%7B", "{").replaceAll("%7D", "}")],
    encoding: t.encoding, tileSize: 256, minzoom: t.minzoom, maxzoom: t.maxzoom, bounds: DTM_BOUNDS, attribution: t.attribution };
}
export function addHillshade(map, meta, dataUrl, before) {
  if (!map.getSource("dem")) map.addSource("dem", terrainSource(meta, dataUrl));
  if (!map.getSource("dem-shade")) map.addSource("dem-shade", { ...terrainSource(meta, dataUrl), attribution: undefined });
  if (!map.getLayer("hillshade")) map.addLayer({ id: "hillshade", type: "hillshade", source: "dem-shade",
    paint: { "hillshade-shadow-color": "#9FB2BF", "hillshade-highlight-color": "#FFFFFF", "hillshade-exaggeration": 0.35 } }, before);
}

// Compact attribution: on phones start collapsed to its "i" button (still visible; tap to read), so it does not cover
// the small map. Desktop keeps MapLibre's default (expanded until the map is first moved).
export function attribution(maplibregl, map, position) {
  const ctrl = new maplibregl.AttributionControl({ compact: true });
  map.addControl(ctrl, position);
  if (innerWidth < 900) {
    // MapLibre switches to compact (and shows the text) once attributions arrive; collapse it the first time that happens
    const collapse = () => {
      const el = map.getContainer().querySelector(".maplibregl-ctrl-attrib.maplibregl-compact");
      if (!el) return;
      el.classList.remove("maplibregl-compact-show");
      el.removeAttribute("open");
      el.dataset.ready = "";      // from now on the "i" button opens and closes the text as usual
      map.off("idle", collapse);
    };
    map.on("idle", collapse);
  }
  return ctrl;
}
