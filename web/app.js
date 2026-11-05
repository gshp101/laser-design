// laserdesign in the browser: the five-step wizard of the Qt GUI, with the
// physics computed by the laserdesign Python package running under Pyodide
// in a Web Worker (worker.js). This file only builds forms, keeps the design
// (a DesignSpec as plain JSON, SI units) and draws the reports.

import { drawPlot } from "./plot.js";

// ---------------------------------------------------------------------- //
// Configuration
// ---------------------------------------------------------------------- //
const CONFIG = Object.assign(
  { pyodideIndexURL: "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/", packageURL: "laserdesign.zip" },
  window.LASERDESIGN_CONFIG || {},
);
const params = new URLSearchParams(location.search);
if (params.get("pyodide")) CONFIG.pyodideIndexURL = params.get("pyodide");
const abs = (u) => new URL(u, location.href).href;
CONFIG.pyodideIndexURL = abs(CONFIG.pyodideIndexURL.replace(/\/?$/, "/"));
CONFIG.packageURL = abs(CONFIG.packageURL);

const UM = 1e-6, MM = 1e-3, CM = 1e-2;
const STORAGE_KEY = "laserdesign.design";
const $ = (id) => document.getElementById(id);

// ---------------------------------------------------------------------- //
// Worker RPC
// ---------------------------------------------------------------------- //
const worker = new Worker(new URL("./worker.js", import.meta.url), { type: "module" });
let nextId = 1;
const waiting = new Map();
worker.onmessage = (ev) => {
  const msg = ev.data;
  if (msg.status) { $("loading-text").textContent = msg.status; return; }
  const p = waiting.get(msg.id);
  if (!p) return;
  waiting.delete(msg.id);
  if ("error" in msg) p.reject(new Error(msg.error)); else p.resolve(msg.result);
};
worker.onerror = (ev) => fatal(`The worker failed to start: ${ev.message || "unknown error"}`);
function call(cmd, args = {}) {
  const id = nextId++;
  return new Promise((resolve, reject) => {
    waiting.set(id, { resolve, reject });
    worker.postMessage({ id, cmd, ...args });
  });
}

// ---------------------------------------------------------------------- //
// Design state. Infinite radii are Infinity here and "inf" in JSON files.
// ---------------------------------------------------------------------- //
let catalog = null;
let spec = null;
let step = 0;

const INF_KEYS = ["R", "f"];
function fromWire(d) {
  const s = structuredClone(d);
  for (const k of ["R1", "R2"]) if (typeof s[k] === "string") s[k] = Number(s[k].replace("inf", "Infinity"));
  s.elements = (s.elements || []).map((e) => {
    const o = { ...e };
    for (const k of INF_KEYS) if (typeof o[k] === "string") o[k] = Number(o[k].replace("inf", "Infinity"));
    return o;
  });
  return s;
}
function toWire(s) {
  const fix = (v) => (v === Infinity ? "inf" : v === -Infinity ? "-inf" : v);
  const d = { ...s, R1: fix(s.R1), R2: fix(s.R2) };
  d.elements = s.elements.map((e) => Object.fromEntries(Object.entries(e).map(([k, v]) => [k, fix(v)])));
  return d;
}

function persist() {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(toWire(spec))); } catch { /* private mode */ }
}

function b64encode(text) {
  const bytes = new TextEncoder().encode(text);
  let bin = "";
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}
function b64decode(text) {
  const bin = atob(text.replace(/-/g, "+").replace(/_/g, "/"));
  return new TextDecoder().decode(Uint8Array.from(bin, (c) => c.charCodeAt(0)));
}

async function setSpec(wire, { render = true } = {}) {
  const clean = await call("normalise", { spec: wire });
  spec = fromWire(clean);
  persist();
  if (render) renderStep();
}

function changed({ rerender = false } = {}) {
  persist();
  if (rerender) renderInputs();
  schedule();
}

// ---------------------------------------------------------------------- //
// Icons (SVG line drawings using currentColor, shared with the Qt GUI)
// ---------------------------------------------------------------------- //
const ICONS = ["app", "step-gain-medium", "step-pump", "step-resonator", "step-operation", "step-results",
  "pump-end", "pump-side", "cavity-standing", "cavity-ring", "mode-cw", "mode-qswitch", "mode-passive",
  "mode-modelock", "mode-klm"];
const iconSVG = {};
async function loadIcons() {
  await Promise.all(ICONS.map(async (name) => {
    try {
      const r = await fetch(`icons/${name}.svg`);
      if (r.ok) iconSVG[name] = (await r.text()).replace(/<metadata>[\s\S]*?<\/metadata>/, "");
    } catch { /* icons are decoration */ }
  }));
  document.querySelectorAll("[data-icon]").forEach((n) => { n.innerHTML = iconSVG[n.dataset.icon] || ""; });
}
function icon(name, cls = "icon") {
  const s = document.createElement("span");
  s.className = cls;
  s.innerHTML = iconSVG[name] || "";
  return s;
}

// ---------------------------------------------------------------------- //
// Form helpers
// ---------------------------------------------------------------------- //
function h(tag, attrs = {}, ...children) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") n.className = v;
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else if (v === true) n.setAttribute(k, "");
    else if (v !== false && v !== null && v !== undefined) n.setAttribute(k, v);
  }
  for (const c of children.flat()) if (c !== null && c !== undefined) n.append(c);
  return n;
}

function card(title, ...children) {
  return h("div", { class: "card" }, title ? h("h2", {}, title) : null, ...children);
}

let fieldCount = 0;
function round(v, decimals) {
  if (!Number.isFinite(v)) return "";
  return String(Number(v.toFixed(decimals)));
}

/** A number input in display units: value = SI / scale. */
function num(label, get, set, { scale = 1, unit = "", step = "any", min = null, max = null,
  decimals = 4, title = "", integer = false } = {}) {
  const id = "f" + fieldCount++;
  const input = h("input", { type: "number", id, step, min, max, title: title || null,
    value: round(get() / scale, decimals), inputmode: "decimal" });
  input.addEventListener("change", () => {
    let v = parseFloat(input.value);
    if (!Number.isFinite(v)) { input.value = round(get() / scale, decimals); return; }
    if (integer) v = Math.round(v);
    set(v * scale);
    changed();
  });
  return [h("label", { for: id, title: title || null }, label),
    h("div", { class: "field" }, input, h("span", { class: "unit" }, unit))];
}

function select(label, options, get, set, { rerender = false, title = "" } = {}) {
  const id = "f" + fieldCount++;
  const sel = h("select", { id, title: title || null },
    options.map(([v, text]) => h("option", { value: v, selected: String(get()) === String(v) }, text)));
  sel.addEventListener("change", () => { set(sel.value); changed({ rerender }); });
  return [h("label", { for: id }, label), h("div", { class: "field" }, sel)];
}

function check(label, get, set, { rerender = false } = {}) {
  const box = h("input", { type: "checkbox", checked: !!get() });
  box.addEventListener("change", () => { set(box.checked); changed({ rerender }); });
  return h("label", { class: "check" }, box, label);
}

function hint(text) { return h("div", { class: "hint" }, text); }

/** Mirror radius in mm with a "flat" checkbox (R = inf). */
function radius(label, key, disabled) {
  const id = "f" + fieldCount++;
  const flat = !Number.isFinite(spec[key]);
  const input = h("input", { type: "number", id, step: "any", disabled: disabled || flat,
    value: flat ? "" : round(spec[key] / MM, 4), title: "Radius of curvature; positive = concave" });
  const box = h("input", { type: "checkbox", checked: flat, disabled });
  input.addEventListener("change", () => {
    const v = parseFloat(input.value);
    if (Number.isFinite(v) && v !== 0) { spec[key] = v * MM; changed(); }
  });
  box.addEventListener("change", () => {
    spec[key] = box.checked ? Infinity : (parseFloat(input.value) || 100) * MM;
    changed({ rerender: true });
  });
  return [h("label", { for: id }, label),
    h("div", { class: "field" }, input, h("span", { class: "unit" }, "mm"),
      h("label", { class: "unit" }, box, " flat"))];
}

function choices(options, get, set) {
  return h("div", { class: "choices", role: "group" }, options.map(([value, text, iconName]) =>
    h("button", { type: "button", class: "choice", "aria-pressed": String(get() === value),
      onclick: () => { set(value); changed({ rerender: true }); } }, icon(iconName), text)));
}

// ---------------------------------------------------------------------- //
// Step 1: gain medium
// ---------------------------------------------------------------------- //
function material() { return catalog.materials[spec.material]; }

function gainMediumInputs() {
  const mat = material();
  const props = h("div", { class: "form" });
  for (const f of catalog.material_fields) {
    const base = mat.values[f.attr];
    props.append(...num(f.label,
      () => spec.material_overrides[f.attr] ?? base,
      (v) => {
        if (Math.abs(v - base) <= Math.abs(base) * 1e-6) delete spec.material_overrides[f.attr];
        else spec.material_overrides[f.attr] = v;
      },
      { scale: f.scale, unit: f.unit, decimals: f.decimals + 3 }));
  }
  const reset = h("button", { type: "button", onclick: () => { spec.material_overrides = {}; changed({ rerender: true }); } },
    "Reset to database values");
  const overridden = Object.keys(spec.material_overrides).length;
  return [
    card("Design",
      h("div", { class: "form" },
        h("label", { for: "design-name" }, "Name"),
        (() => {
          const i = h("input", { type: "text", id: "design-name", value: spec.name });
          i.addEventListener("change", () => { spec.name = i.value || "Untitled design"; changed(); });
          return i;
        })())),
    card("Crystal",
      h("div", { class: "form" },
        ...select("Material", Object.entries(catalog.materials).map(([k, m]) => [k, m.name]),
          () => spec.material, (v) => { spec.material = v; spec.material_overrides = {}; }, { rerender: true }),
        ...num("Doping", () => spec.doping, (v) => { spec.doping = v; }, { unit: mat.doping_unit, min: 0, decimals: 3 }),
        ...num("Crystal / rod length", () => spec.crystal_length, (v) => { spec.crystal_length = v; },
          { scale: MM, unit: "mm", min: 0, title: "Path length in the crystal, or rod length" }),
        check("Brewster-cut (faces at Brewster's angle)", () => spec.crystal_brewster, (v) => { spec.crystal_brewster = v; }))),
    card(`Material properties${overridden ? ` (${overridden} edited)` : " (edit to override)"}`, props,
      h("div", { class: "add-row" }, reset)),
  ];
}

// ---------------------------------------------------------------------- //
// Step 2: pump
// ---------------------------------------------------------------------- //
function pumpInputs() {
  const side = spec.pump_geometry === "side";
  const out = [card("Pump geometry",
    choices([["end", "End-pumped (focused beam)", "pump-end"], ["side", "Side-pumped rod (uniform)", "pump-side"]],
      () => spec.pump_geometry, (v) => { spec.pump_geometry = v; }),
    h("div", { class: "form", style: "margin-top:10px" },
      ...num("Pump power", () => spec.pump_power, (v) => { spec.pump_power = v; }, { unit: "W", min: 0, decimals: 3 })))];
  if (!side) {
    out.push(card("Pump beam", h("div", { class: "form" },
      ...num("Waist radius", () => spec.pump_waist, (v) => { spec.pump_waist = v; }, { scale: UM, unit: "µm", min: 0, decimals: 1 }),
      ...num("Beam quality M²", () => spec.pump_m2, (v) => { spec.pump_m2 = v; }, { min: 1, decimals: 2 }),
      hint("Fibre-coupled diode: M² ≈ π × core radius × NA / λ."),
      ...num("Waist depth in crystal", () => spec.pump_waist_position, (v) => { spec.pump_waist_position = v; },
        { scale: MM, unit: "mm", decimals: 3 }),
      ...select("Pumping", [[1, "Single pass"], [2, "Double pass"]], () => spec.pump_passes,
        (v) => { spec.pump_passes = Number(v); }),
      ...num("Effective absorption", () => spec.effective_absorption ?? 0,
        (v) => { spec.effective_absorption = v > 0 ? v : null; },
        { scale: 1 / CM, unit: "/cm", min: 0, decimals: 3, title: "0 = from the material and doping" }),
      hint("0 uses the material value; enter a measured value for a broad diode spectrum."))));
  } else {
    out.push(card("Rod", h("div", { class: "form" },
      ...num("Rod radius", () => spec.rod_radius, (v) => { spec.rod_radius = v; }, { scale: MM, unit: "mm", min: 0, decimals: 3 }),
      ...num("Absorption efficiency", () => spec.absorption_efficiency, (v) => { spec.absorption_efficiency = v; },
        { scale: 0.01, unit: "%", min: 0, max: 100, decimals: 1, title: "Fraction of the pump light absorbed in the rod" }),
      ...select("Thermal lens in resonator", [["average", "Average of radial and tangential"],
        ["radial", "Radial polarisation"], ["tangential", "Tangential polarisation"], ["dn_dT", "dn/dT only (no stress)"]],
      () => spec.rod_thermal_lens, (v) => { spec.rod_thermal_lens = v; }),
      ...num("Multimode fill", () => spec.multimode_fill ?? 0, (v) => { spec.multimode_fill = v > 0 ? v : null; },
        { scale: 0.01, unit: "%", min: 0, max: 100, decimals: 0 }),
      hint("0 = TEM00 (aperture-limited); otherwise the multimode beam radius as a fraction of the rod radius."))));
  }
  return out;
}

// ---------------------------------------------------------------------- //
// Step 3: resonator
// ---------------------------------------------------------------------- //
const ELEMENT_LABELS = { crystal: "Gain crystal", space: "Air gap", mirror: "Fold mirror", lens: "Thin lens",
  medium: "Medium / Q-switch", brewster: "Brewster plate" };
const ELEMENT_DEFAULTS = {
  space: { type: "space", length: 0.05 },
  mirror: { type: "mirror", R: 0.2, angle_deg: 5.0 },
  lens: { type: "lens", f: 0.1 },
  medium: { type: "medium", length: 0.02, n: 1.45, name: "Q-switch" },
  brewster: { type: "brewster", thickness: 0.005, n: 1.45 },
};

function cellNumber(e, key, scale, { allowInf = false, label = "" } = {}) {
  const v = e[key];
  const shown = !Number.isFinite(v) ? (allowInf ? "inf" : "") : round(v / scale, 5);
  const input = h("input", { type: allowInf ? "text" : "number", step: "any", value: shown, "aria-label": label,
    inputmode: "decimal", title: allowInf ? "Type inf for a flat mirror" : null });
  input.addEventListener("change", () => {
    const t = input.value.trim().toLowerCase();
    let x;
    if (allowInf && ["inf", "∞", "flat", ""].includes(t)) x = Infinity;
    else x = parseFloat(t) * scale;
    if (Number.isNaN(x)) { input.value = shown; return; }
    e[key] = x;
    changed();
  });
  return input;
}

function resonatorInputs() {
  const ring = spec.cavity_type === "ring";
  const tbody = h("tbody");
  spec.elements.forEach((e, i) => {
    const t = e.type;
    const nameInput = t === "crystal" ? h("span", { class: "muted" }, "(from step 1)")
      : (() => {
        const n = h("input", { type: "text", value: e.name || "", "aria-label": "Element name", placeholder: "name" });
        n.addEventListener("change", () => {
          const v = n.value.trim();
          if (v) e.name = v; else delete e.name;
          changed();
        });
        return n;
      })();
    const lengthKey = t === "brewster" ? "thickness" : ["space", "medium"].includes(t) ? "length" : null;
    const rfKey = t === "mirror" ? "R" : t === "lens" ? "f" : null;
    const move = (d) => {
      const j = i + d;
      if (j < 0 || j >= spec.elements.length) return;
      [spec.elements[i], spec.elements[j]] = [spec.elements[j], spec.elements[i]];
      changed({ rerender: true });
    };
    tbody.append(h("tr", { class: t === "crystal" ? "crystal" : "" },
      h("td", { class: "kind" }, ELEMENT_LABELS[t] || t),
      h("td", {}, nameInput),
      h("td", {}, lengthKey ? cellNumber(e, lengthKey, MM, { label: "Length in mm" }) : ""),
      h("td", {}, rfKey ? cellNumber(e, rfKey, MM, { allowInf: t === "mirror", label: rfKey === "R" ? "Radius in mm" : "Focal length in mm" }) : ""),
      h("td", {}, t === "mirror" ? cellNumber(e, "angle_deg", 1, { label: "Angle in degrees" }) : ""),
      h("td", {}, ["medium", "brewster"].includes(t) ? cellNumber(e, "n", 1, { label: "Refractive index" }) : ""),
      h("td", { class: "ops" },
        h("button", { type: "button", class: "small", title: "Move up", "aria-label": "Move up", disabled: i === 0, onclick: () => move(-1) }, "↑"),
        h("button", { type: "button", class: "small", title: "Move down", "aria-label": "Move down", disabled: i === spec.elements.length - 1, onclick: () => move(1) }, "↓"),
        h("button", { type: "button", class: "small", title: "Remove", "aria-label": "Remove", disabled: t === "crystal",
          onclick: () => { spec.elements.splice(i, 1); changed({ rerender: true }); } }, "✕"))));
  });
  const table = h("table", { class: "elements" },
    h("thead", {}, h("tr", {}, ["Element", "Name", "Length [mm]", "R or f [mm]", "Angle [°]", "n", ""].map((c) => h("th", {}, c)))),
    tbody);
  const add = h("div", { class: "add-row" }, Object.keys(ELEMENT_DEFAULTS).map((t) =>
    h("button", { type: "button", onclick: () => { spec.elements.push(structuredClone(ELEMENT_DEFAULTS[t])); changed({ rerender: true }); } },
      "+ " + ELEMENT_LABELS[t])));
  return [
    card("Resonator type",
      choices([["standing", "Standing wave (two end mirrors)", "cavity-standing"], ["ring", "Ring (unidirectional)", "cavity-ring"]],
        () => spec.cavity_type, (v) => { spec.cavity_type = v; }),
      h("div", { class: "form", style: "margin-top:10px" },
        ...radius("End mirror 1 radius", "R1", ring),
        ...radius("End mirror 2 radius", "R2", ring),
        ring ? hint("A ring has no end mirrors; put its curved mirrors in the list as fold mirrors.") : null)),
    card(ring ? "Elements around the loop" : "Elements from mirror 1 to mirror 2",
      h("div", { class: "table-scroll" }, table), add),
  ];
}

// ---------------------------------------------------------------------- //
// Step 4: operation
// ---------------------------------------------------------------------- //
const MODES = [["cw", "Continuous wave", "mode-cw"], ["qswitch", "Active Q-switch", "mode-qswitch"],
  ["passive", "Passive Q-switch", "mode-passive"], ["modelock", "SESAM mode-locked", "mode-modelock"],
  ["klm", "Kerr-lens mode-locked", "mode-klm"]];

function locationOptions(current, allowCrystal = false) {
  const opts = [];
  if (spec.cavity_type === "standing") opts.push(["mirror1", "End mirror 1"], ["mirror2", "End mirror 2"]);
  if (allowCrystal) opts.push(["crystal", "Gain crystal (soft aperture)"]);
  for (const e of spec.elements) if (e.name) opts.push([e.name, `Element: ${e.name}`]);
  if (!opts.some(([v]) => v === current)) opts.push([current, `${current} (not found)`]);
  return opts;
}

function operationInputs() {
  const out = [
    card("Losses", h("div", { class: "form" },
      ...num("Output coupler transmission", () => spec.output_coupling, (v) => { spec.output_coupling = v; },
        { scale: 0.01, unit: "%", min: 0, max: 99, decimals: 3 }),
      ...num("Other round-trip losses", () => spec.passive_loss, (v) => { spec.passive_loss = v; },
        { scale: 0.01, unit: "%", min: 0, max: 50, decimals: 3 }))),
    card("Operating mode", choices(MODES, () => spec.mode, (v) => { spec.mode = v; })),
  ];
  const m = spec.mode;
  if (m === "qswitch") {
    out.push(card("Active Q-switch", h("div", { class: "form" },
      ...num("Repetition rate", () => spec.rep_rate, (v) => { spec.rep_rate = v; }, { scale: 1e3, unit: "kHz", min: 0, decimals: 4 }))));
  } else if (m === "passive") {
    out.push(card("Saturable absorber", h("div", { class: "form" },
      ...select("Absorber", Object.entries(catalog.absorbers), () => spec.absorber, (v) => { spec.absorber = v; }),
      ...num("Initial transmission T0", () => spec.absorber_transmission, (v) => { spec.absorber_transmission = v; },
        { scale: 0.01, unit: "%", min: 1, max: 99.9, decimals: 2, title: "Small-signal single-pass transmission T0" }),
      ...select("Absorber location", locationOptions(spec.absorber_location), () => spec.absorber_location,
        (v) => { spec.absorber_location = v; }))));
  } else if (m === "modelock") {
    out.push(card("SESAM", h("div", { class: "form" },
      ...num("Saturation fluence", () => spec.sesam_saturation_fluence, (v) => { spec.sesam_saturation_fluence = v; },
        { scale: 1e-2, unit: "µJ/cm²", min: 0, decimals: 2 }),
      ...num("Modulation depth", () => spec.sesam_modulation_depth, (v) => { spec.sesam_modulation_depth = v; },
        { scale: 0.01, unit: "%", min: 0, max: 50, decimals: 3 }),
      ...select("SESAM location", locationOptions(spec.sesam_location), () => spec.sesam_location,
        (v) => { spec.sesam_location = v; }))));
  } else if (m === "klm") {
    out.push(card("Kerr-lens mode locking", h("div", { class: "form" },
      ...select("Aperture (where the Kerr effect is read)", locationOptions(spec.klm_aperture, true),
        () => spec.klm_aperture, (v) => { spec.klm_aperture = v; }),
      ...num("Crystal slices", () => spec.klm_slices, (v) => { spec.klm_slices = v; }, { min: 2, max: 40, step: 1, integer: true, decimals: 0 }),
      ...num("Target pulse width", () => spec.klm_pulse_width, (v) => { spec.klm_pulse_width = v; },
        { scale: 1e-15, unit: "fs", min: 0, decimals: 2 }))));
  } else {
    out.push(card("", h("p", { class: "muted" }, "No further settings for CW operation.")));
  }
  out.push(card("", h("p", { class: "muted small" },
    "Absorbers, SESAMs and apertures sit at an end mirror or at a named element; name elements in step 3.")));
  return out;
}

// ---------------------------------------------------------------------- //
// Step 5: results (table in the left column)
// ---------------------------------------------------------------------- //
let resultRows = null;
function resultsInputs() {
  resultRows = h("tbody");
  return [h("table", { class: "rows" }, resultRows)];
}

// ---------------------------------------------------------------------- //
// Steps
// ---------------------------------------------------------------------- //
const STEPS = [
  { key: "gain_medium", title: "1. Gain medium", icon: "step-gain-medium", inputs: gainMediumInputs,
    help: "Choose the crystal, its doping and length. The material values are typical literature numbers; edit any of them to match your crystal's data sheet." },
  { key: "pump", title: "2. Pump", icon: "step-pump", inputs: pumpInputs,
    help: "Choose end pumping (a focused beam along the laser axis) or side pumping (a rod pumped uniformly from the side by diodes or lamps). Fibre-coupled diodes are best described by their M² (fibre radius × NA × π / λ)." },
  { key: "resonator", title: "3. Resonator", icon: "step-resonator", inputs: resonatorInputs,
    help: "For a standing-wave resonator, list the elements met going from end mirror 1 (usually the pumped face) to end mirror 2. For a unidirectional ring, list one full loop, with the curved mirrors as fold mirrors. Name elements you want to refer to later (absorber, SESAM, aperture). The plots show the TEM00 mode at full pump power and how the stability parameter m = (A+D)/2 moves as the thermal lens changes; the resonator is stable for −1 < m < 1." },
  { key: "operation", title: "4. Operation", icon: "step-operation", inputs: operationInputs,
    help: "Choose the output coupling, the other losses and how the laser is run: continuous wave, actively Q-switched with CW pumping, passively Q-switched with a saturable absorber, SESAM mode-locked, or Kerr-lens mode-locked." },
  { key: "results", title: "5. Results", icon: "step-results", inputs: resultsInputs,
    help: "Performance of the design. Go back to any step to change it; results update." },
];

function renderNav() {
  const ol = $("steps");
  ol.replaceChildren(...STEPS.map((s, i) => h("li", {},
    h("button", { type: "button", "aria-current": i === step ? "step" : null, onclick: () => go(i) },
      icon(s.icon), s.title))));
}

function renderInputs() {
  fieldCount = 0;
  const s = STEPS[step];
  const focusId = document.activeElement && document.activeElement.id;
  $("inputs").replaceChildren(...s.inputs());
  if (focusId && $(focusId)) $(focusId).focus();
}

function renderStep() {
  const s = STEPS[step];
  renderNav();
  $("page-icon").replaceChildren(icon(s.icon, "icon big"));
  $("page-title").textContent = s.title;
  $("page-help").textContent = s.help;
  $("btn-back").disabled = step === 0;
  $("btn-next").disabled = step === STEPS.length - 1;
  $("page").querySelector(".columns").classList.toggle("wide-inputs", s.key === "resonator");
  renderInputs();
  $("info").replaceChildren();
  $("notes").replaceChildren();
  $("plots").replaceChildren();
  compute();
}

function go(i) {
  step = Math.max(0, Math.min(STEPS.length - 1, i));
  try { sessionStorage.setItem("laserdesign.step", String(step)); } catch { /* ignore */ }
  renderStep();
  window.scrollTo({ top: 0 });
}

// ---------------------------------------------------------------------- //
// Computing and drawing reports
// ---------------------------------------------------------------------- //
let timer = null, inflight = false, pending = false, lastReport = null;
function schedule() {
  clearTimeout(timer);
  timer = setTimeout(compute, 250);
}

async function compute() {
  if (inflight) { pending = true; return; }
  inflight = true;
  pending = false;
  const key = STEPS[step].key;
  const busy = setTimeout(() => { $("busy").hidden = false; }, 300);
  try {
    const rep = await call("run", { spec: toWire(spec), step: key });
    if (STEPS[step].key === key && !pending) show(rep);
  } catch (err) {
    status(`Error: ${err.message}`, true);
  } finally {
    clearTimeout(busy);
    $("busy").hidden = true;
    inflight = false;
    if (pending) compute();
  }
}

function show(rep) {
  lastReport = rep;
  $("info").replaceChildren(...rep.info.map((line) => { const p = h("p"); p.innerHTML = line; return p; }));
  const notes = rep.notes.map((n) => { const d = h("div", { class: `note ${n.level}` }); d.innerHTML = n.text; return d; });
  if (rep.error && !rep.info.length) notes.unshift(h("div", { class: "note warn error" }, rep.error));
  $("notes").replaceChildren(...notes);
  if (resultRows && STEPS[step].key === "results") {
    resultRows.replaceChildren(...rep.rows.map(([k, v]) => h("tr", {}, h("td", {}, k), h("td", {}, v))));
  }
  drawPlots(rep.plots);
  if (rep.problems && rep.problems.length) status(rep.problems.join("; "), true);
  else if (rep.error) status(rep.error, true);
  else status(spec.name);
}

function drawPlots(plots) {
  const box = $("plots");
  box.replaceChildren(...plots.map(() => h("div")));
  plots.forEach((p, i) => drawPlot(box.children[i], p));
}

let resizeTimer = null;
window.addEventListener("resize", () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => { if (lastReport) drawPlots(lastReport.plots); }, 150);
});

function status(text, bad = false) {
  const s = $("status");
  s.textContent = text;
  s.classList.toggle("bad", bad);
}

function fatal(text) {
  $("loading").replaceChildren(h("div", { class: "error" }, text,
    h("p", { class: "muted" }, "Check your connection, or see the documentation for hosting Pyodide yourself.")));
}

// ---------------------------------------------------------------------- //
// Toolbar: examples, new, open, save, link
// ---------------------------------------------------------------------- //
function wireToolbar() {
  const presets = $("presets");
  for (const name of Object.keys(catalog.presets)) presets.append(h("option", { value: name }, name));
  presets.addEventListener("change", async () => {
    if (!presets.value) return;
    await setSpec(catalog.presets[presets.value]);
    presets.value = "";
  });
  $("btn-new").addEventListener("click", async () => { await setSpec(catalog.default, { render: false }); go(0); });
  $("btn-open").addEventListener("click", () => $("file").click());
  $("file").addEventListener("change", async () => {
    const f = $("file").files[0];
    if (!f) return;
    try {
      await setSpec(JSON.parse(await f.text()));
      status(`Opened ${f.name}`);
    } catch (err) {
      status(`Could not open ${f.name}: ${err.message}`, true);
    }
    $("file").value = "";
  });
  $("btn-save").addEventListener("click", () => {
    const blob = new Blob([JSON.stringify(toWire(spec), null, 2)], { type: "application/json" });
    const a = h("a", { href: URL.createObjectURL(blob),
      download: (spec.name || "design").replace(/[^\w.-]+/g, "_").replace(/^_+|_+$/g, "") + ".json" });
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  });
  $("btn-link").addEventListener("click", async () => {
    const url = `${location.origin}${location.pathname}${location.search}#design=${b64encode(JSON.stringify(toWire(spec)))}`;
    try { await navigator.clipboard.writeText(url); status("Link copied to the clipboard."); }
    catch { history.replaceState(null, "", url); status("Link placed in the address bar."); }
  });
  $("btn-back").addEventListener("click", () => go(step - 1));
  $("btn-next").addEventListener("click", () => go(step + 1));
  for (const id of ["presets", "btn-new", "btn-open", "btn-save", "btn-link"]) $(id).disabled = false;
}

function initialDesign() {
  const m = location.hash.match(/design=([\w-]+)/);
  if (m) {
    // Use the design from a shared link once; later edits are kept locally.
    history.replaceState(null, "", location.pathname + location.search);
    try { return JSON.parse(b64decode(m[1])); } catch { /* fall through */ }
  }
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) return JSON.parse(stored);
  } catch { /* ignore */ }
  return Object.values(catalog.presets)[0];
}

// ---------------------------------------------------------------------- //
// Start
// ---------------------------------------------------------------------- //
async function main() {
  loadIcons();
  try {
    const info = await call("init", { config: CONFIG });
    catalog = await call("catalog");
    $("version").textContent = `${catalog.version} · Python ${info.python} (Pyodide ${info.pyodide})`;
  } catch (err) {
    fatal(`Could not start Python: ${err.message}`);
    return;
  }
  wireToolbar();
  try {
    await setSpec(initialDesign(), { render: false });
  } catch {
    await setSpec(Object.values(catalog.presets)[0], { render: false });
  }
  try { step = Number(sessionStorage.getItem("laserdesign.step")) || 0; } catch { step = 0; }
  $("loading").hidden = true;
  $("page").hidden = false;
  go(step);
}

main();
