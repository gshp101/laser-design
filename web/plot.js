// Small SVG line-plot renderer for the reports made by laserdesign.web.report.
// No dependencies: linear and log axes, an optional second y axis, reference
// lines, a shaded band, markers, a legend and a hover read-out.

const SVG = "http://www.w3.org/2000/svg";
const DASH = { solid: "", dash: "6 4", dot: "1.5 3" };

function el(name, attrs = {}, parent = null) {
  const node = document.createElementNS(SVG, name);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (parent) parent.appendChild(node);
  return node;
}

function finite(v) {
  return v !== null && v !== undefined && Number.isFinite(v);
}

export function fmt(v) {
  if (!finite(v)) return "–";
  const a = Math.abs(v);
  if (a !== 0 && (a >= 1e5 || a < 1e-3)) return v.toExponential(2).replace("e+", "e");
  return String(Number(v.toPrecision(4)));
}

function niceStep(span, count) {
  const raw = span / Math.max(count, 1);
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const r = raw / mag;
  return (r < 1.5 ? 1 : r < 3 ? 2 : r < 7 ? 5 : 10) * mag;
}

function linearScale(lo, hi, count) {
  if (lo === hi) { const d = Math.abs(lo) * 0.1 || 1; lo -= d; hi += d; }
  const step = niceStep(hi - lo, count);
  const t0 = Math.ceil(lo / step - 1e-9) * step;
  const ticks = [];
  for (let t = t0; t <= hi + step * 1e-9; t += step) ticks.push(Math.abs(t) < step * 1e-9 ? 0 : t);
  return { lo, hi, ticks, log: false };
}

function logScale(lo, hi) {
  lo = Math.log10(lo); hi = Math.log10(hi);
  if (lo === hi) { lo -= 0.5; hi += 0.5; }
  const ticks = [];
  const decades = hi - lo;
  const mult = decades < 1.2 ? [1, 2, 3, 5] : decades < 3 ? [1, 2, 5] : [1];
  for (let d = Math.floor(lo); d <= Math.ceil(hi); d++) {
    for (const m of mult) {
      const t = Math.log10(m) + d;
      if (t >= lo - 1e-9 && t <= hi + 1e-9) ticks.push(t);
    }
  }
  return { lo, hi, ticks, log: true };
}

function extent(values, log) {
  let lo = Infinity, hi = -Infinity;
  for (const v of values) {
    if (!finite(v) || (log && v <= 0)) continue;
    if (v < lo) lo = v;
    if (v > hi) hi = v;
  }
  return lo <= hi ? [lo, hi] : null;
}

function pad([lo, hi], log) {
  if (log) return [lo, hi];
  const d = (hi - lo) * 0.05 || Math.abs(hi) * 0.05 || 1;
  return [lo - d, hi + d];
}

/** Draw plot spec `p` into container `host` (replaces its content). */
export function drawPlot(host, p) {
  host.replaceChildren();
  host.classList.add("plot");
  if (p.message) {
    const m = document.createElement("div");
    m.className = "plot-message";
    m.textContent = p.message;
    host.appendChild(m);
    return;
  }
  const title = document.createElement("div");
  title.className = "plot-title";
  title.textContent = p.title;
  host.appendChild(title);

  const width = Math.max(host.clientWidth || 480, 260);
  const height = Math.round(Math.min(300, Math.max(210, width * 0.55)));
  const hasY2 = p.series.some((s) => s.axis === "y2") || p.hlines.some((h) => h.axis === "y2");
  const m = { l: 58, r: hasY2 ? 58 : 14, t: 10, b: 40 };
  const W = width - m.l - m.r, H = height - m.t - m.b;

  // Ranges
  const xs = p.series.flatMap((s) => s.x).concat(p.vlines.map((v) => v.x));
  let xr = extent(xs, p.xlog);
  if (!xr) { host.appendChild(Object.assign(document.createElement("div"), { className: "plot-message", textContent: "No data to plot" })); return; }
  const yrFor = (axis) => {
    const ys = p.series.filter((s) => (s.axis || "y") === axis).flatMap((s) => s.y)
      .concat(p.hlines.filter((h) => (h.axis || "y") === axis).map((h) => h.y));
    if (axis === "y" && p.hspan && !p.ylim) ys.push(...p.hspan);
    const e = extent(ys, axis === "y" && p.ylog);
    return e ? pad(e, axis === "y" && p.ylog) : null;
  };
  let yr = p.ylim ? p.ylim : yrFor("y");
  const y2r = hasY2 ? yrFor("y2") : null;
  if (!yr) yr = [0, 1];
  const xs_ = p.xlog ? logScale(...xr) : linearScale(...xr, Math.max(3, Math.round(W / 80)));
  const ys_ = p.ylog ? logScale(...yr) : linearScale(...yr, Math.max(3, Math.round(H / 45)));
  const y2s_ = y2r ? linearScale(...y2r, Math.max(3, Math.round(H / 45))) : null;
  if (!p.xlog && !p.vlines.length) { xs_.lo = xr[0]; xs_.hi = xr[1]; }

  const tx = (v) => m.l + ((xs_.log ? Math.log10(v) : v) - xs_.lo) / (xs_.hi - xs_.lo) * W;
  const tyFor = (s) => (v) => m.t + H - ((s.log ? Math.log10(v) : v) - s.lo) / (s.hi - s.lo) * H;
  const ty = tyFor(ys_);
  const ty2 = y2s_ ? tyFor(y2s_) : ty;

  const svg = el("svg", { viewBox: `0 0 ${width} ${height}`, width, height, role: "img",
    "aria-label": p.title || "plot" }, host);
  const clipId = "c" + Math.random().toString(36).slice(2);
  el("rect", { x: m.l, y: m.t, width: W, height: H }, el("clipPath", { id: clipId }, el("defs", {}, svg)));

  // Grid and ticks
  const grid = el("g", { class: "grid" }, svg);
  const axes = el("g", { class: "axis" }, svg);
  for (const t of xs_.ticks) {
    const x = m.l + (t - xs_.lo) / (xs_.hi - xs_.lo) * W;
    el("line", { x1: x, x2: x, y1: m.t, y2: m.t + H }, grid);
    el("text", { x, y: m.t + H + 15, "text-anchor": "middle" }, axes).textContent = fmt(xs_.log ? 10 ** t : t);
  }
  for (const t of ys_.ticks) {
    const y = m.t + H - (t - ys_.lo) / (ys_.hi - ys_.lo) * H;
    el("line", { x1: m.l, x2: m.l + W, y1: y, y2: y }, grid);
    el("text", { x: m.l - 6, y: y + 4, "text-anchor": "end" }, axes).textContent = fmt(ys_.log ? 10 ** t : t);
  }
  if (y2s_) {
    for (const t of y2s_.ticks) {
      const y = m.t + H - (t - y2s_.lo) / (y2s_.hi - y2s_.lo) * H;
      el("text", { x: m.l + W + 6, y: y + 4, "text-anchor": "start", class: "y2" }, axes).textContent = fmt(t);
    }
  }
  el("rect", { x: m.l, y: m.t, width: W, height: H, class: "frame" }, svg);
  el("text", { x: m.l + W / 2, y: height - 6, "text-anchor": "middle", class: "label" }, axes).textContent = p.xlabel;
  el("text", { x: 14, y: m.t + H / 2, "text-anchor": "middle", class: "label",
    transform: `rotate(-90 14 ${m.t + H / 2})` }, axes).textContent = p.ylabel;
  if (y2s_ && p.y2label) {
    const x = width - 10;
    el("text", { x, y: m.t + H / 2, "text-anchor": "middle", class: "label y2",
      transform: `rotate(90 ${x} ${m.t + H / 2})` }, axes).textContent = p.y2label;
  }

  const body = el("g", { "clip-path": `url(#${clipId})` }, svg);
  if (p.hspan) {
    const [a, b] = p.hspan.map(ty);
    el("rect", { x: m.l, width: W, y: Math.min(a, b), height: Math.abs(a - b), class: "band" }, body);
  }
  for (const v of p.vlines) {
    if (!finite(v.x)) continue;
    el("line", { x1: tx(v.x), x2: tx(v.x), y1: m.t, y2: m.t + H, class: "ref", "stroke-dasharray": DASH.dot }, body);
  }
  for (const h of p.hlines) {
    if (!finite(h.y)) continue;
    const y = (h.axis === "y2" ? ty2 : ty)(h.y);
    el("line", { x1: m.l, x2: m.l + W, y1: y, y2: y, class: "ref", "stroke-dasharray": DASH[h.dash] ?? DASH.dot }, body);
  }

  // Series
  const legend = [];
  let auto = 0;
  const drawn = [];
  p.series.forEach((s) => {
    const color = s.color ?? auto++ % 6;
    const yf = s.axis === "y2" ? ty2 : ty;
    const ylog = s.axis !== "y2" && p.ylog;
    let d = "", pen = false;
    const pts = [];
    for (let i = 0; i < s.x.length; i++) {
      const x = s.x[i], y = s.y[i];
      if (!finite(x) || !finite(y) || (p.xlog && x <= 0) || (ylog && y <= 0)) { pen = false; continue; }
      const X = tx(x), Y = yf(y);
      d += (pen ? "L" : "M") + X.toFixed(1) + " " + Y.toFixed(1);
      pen = true;
      pts.push([X, Y, x, y]);
    }
    el("path", { d, class: `line c${color}`, "stroke-dasharray": DASH[s.dash] ?? "" }, body);
    if (s.markers) for (const [X, Y] of pts) el("circle", { cx: X, cy: Y, r: 2.6, class: `dot c${color}` }, body);
    drawn.push({ s, pts, color });
    if (s.label) legend.push({ label: s.label + (hasY2 ? (s.axis === "y2" ? " (right)" : " (left)") : ""), color, dash: s.dash });
  });
  for (const h of p.hlines) if (h.label) legend.push({ label: h.label, color: "ref", dash: h.dash });

  if (legend.length) {
    const lg = document.createElement("div");
    lg.className = "legend";
    for (const it of legend) {
      const item = document.createElement("span");
      const sw = document.createElementNS(SVG, "svg");
      sw.setAttribute("width", 22); sw.setAttribute("height", 8);
      el("line", { x1: 1, x2: 21, y1: 4, y2: 4, class: it.color === "ref" ? "ref" : `line c${it.color}`,
        "stroke-dasharray": DASH[it.dash] ?? "" }, sw);
      item.append(sw, document.createTextNode(it.label));
      lg.appendChild(item);
    }
    host.appendChild(lg);
  }

  // Hover read-out: nearest point in x on each series
  const cross = el("line", { y1: m.t, y2: m.t + H, class: "cross", visibility: "hidden" }, svg);
  const tip = document.createElement("div");
  tip.className = "tip";
  tip.hidden = true;
  host.appendChild(tip);
  const hit = el("rect", { x: m.l, y: m.t, width: W, height: H, fill: "transparent" }, svg);
  const move = (ev) => {
    const box = svg.getBoundingClientRect();
    const X = (ev.clientX - box.left) * (width / box.width);
    const lines = [];
    let xval = null;
    for (const { s, pts } of drawn) {
      if (!pts.length || !s.label) continue;
      let best = pts[0];
      for (const q of pts) if (Math.abs(q[0] - X) < Math.abs(best[0] - X)) best = q;
      xval = best[2];
      lines.push(`${s.label}: ${fmt(best[3])}`);
    }
    if (!lines.length) return;
    cross.setAttribute("x1", X); cross.setAttribute("x2", X);
    cross.setAttribute("visibility", "visible");
    tip.textContent = `${p.xlabel.split(" [")[0]} ≈ ${fmt(xval)}\n` + lines.join("\n");
    tip.hidden = false;
    const left = (ev.clientX - host.getBoundingClientRect().left);
    tip.style.left = Math.min(left + 12, host.clientWidth - tip.offsetWidth - 4) + "px";
    tip.style.top = (m.t + 30) + "px";
  };
  hit.addEventListener("pointermove", move);
  hit.addEventListener("pointerleave", () => { tip.hidden = true; cross.setAttribute("visibility", "hidden"); });
}
