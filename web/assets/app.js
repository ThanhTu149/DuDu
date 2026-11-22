/* DuDu — giao diện điều phối.
   Không framework, không thư viện: SVG tự vẽ + fetch API. */

const $ = (sel) => document.querySelector(sel);
const SVG_NS = "http://www.w3.org/2000/svg";

/* XSS protection: escape HTML entities in user/API data before innerHTML */
function esc(str) {
  if (str == null) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

/* Focus trap for modals/drawers (accessibility) */
function trapFocus(container) {
  if (!container._returnFocus) container._returnFocus = document.activeElement;
  const focusable = container.querySelectorAll(
    'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
  );
  if (!focusable.length) return;
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  first.focus();
  const handler = (e) => {
    if (e.key !== "Tab") return;
    if (e.shiftKey) {
      if (document.activeElement === first) { e.preventDefault(); last.focus(); }
    } else {
      if (document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
  };
  container.addEventListener("keydown", handler);
  container._trapCleanup = () => container.removeEventListener("keydown", handler);
}
function releaseFocus(container) {
  if (container._trapCleanup) { container._trapCleanup(); delete container._trapCleanup; }
}

const W = 1000;
const H = 640;
const PAD = 56;

const ROUTE_FALLBACK = ["#c9490e", "#2c6b52", "#2f5d8c", "#8a6100", "#6b3f8c", "#a3402d", "#2f7c7c", "#5c6b2f"];
// Màu tuyến đọc từ biến CSS (nguồn duy nhất: tokens.json → :root → [data-theme="dark"]).
// Đổi theme thì đọc lại rồi vẽ lại, nên tuyến tự sáng lên trên nền tối.
let ROUTE_COLORS = readRouteColors();

function readRouteColors() {
  const styles = getComputedStyle(document.documentElement);
  return ROUTE_FALLBACK.map((fallback, index) => {
    const value = styles.getPropertyValue(`--route-${index + 1}`).trim();
    return value || fallback;
  });
}

const state = {
  hubs: [],
  hubsById: new Map(),
  bounds: null,
  scenario: null,
  plan: null,
  vehiclesById: {},
  ordersById: {},
  activeVehicle: null,
  geometry: new Map(),
  geometryDone: false,
  projecting: null,
  search: "",
};

/* ---------------------------------------------------------------- helpers */
function debounce(fn, ms = 150) {
  let timer;
  return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), ms); };
}

const viNum = (value, digits = 0) =>
  Number(value).toLocaleString("vi-VN", { minimumFractionDigits: digits, maximumFractionDigits: digits });

const fmtKm = (value) => viNum(value, 0);
const fmt1 = (value) => viNum(value, 1);

function clockLabel(minutes) {
  const h = Math.floor(minutes / 60) % 24;
  const m = Math.round(minutes % 60);
  return `${String(h).padStart(2, "0")}:${String(m === 60 ? 0 : m).padStart(2, "0")}`;
}

function el(tag, attrs = {}, children = []) {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
  for (const child of [].concat(children)) node.appendChild(child);
  return node;
}

function project(lat, lon) {
  const b = state.bounds;
  const x = PAD + ((lon - b.min_lon) / (b.max_lon - b.min_lon)) * (W - 2 * PAD);
  const y = H - PAD - ((lat - b.min_lat) / (b.max_lat - b.min_lat)) * (H - 2 * PAD);
  return [x, y];
}

/* ------------------------------------------------------------ khung nhìn */
function applyView() {
  if (!state.view) return;
  const v = state.view;
  $("#map").setAttribute("viewBox", `${v.x.toFixed(1)} ${v.y.toFixed(1)} ${v.w.toFixed(1)} ${v.h.toFixed(1)}`);
  const note = $("#map-note");
  if (note) note.textContent = `zoom ${((state.fitW || v.w) / v.w).toFixed(1)}×`;
  updateMarkerScale();
  updateHubGlyphs();
}

function fitView() {
  if (!state.hubs.length) return;
  const rect = $(".map-wrap").getBoundingClientRect();
  const aspect = Math.max(rect.width, 1) / Math.max(rect.height, 1);
  const points = state.hubs.map((hub) => project(hub.lat, hub.lon));
  const minX = Math.min(...points.map((p) => p[0])) - 62;
  const maxX = Math.max(...points.map((p) => p[0])) + 62;
  const minY = Math.min(...points.map((p) => p[1])) - 74;
  const maxY = Math.max(...points.map((p) => p[1])) + 74;
  let w = maxX - minX;
  let h = maxY - minY;
  if (w / h < aspect) w = h * aspect; else h = w / aspect;
  const cx = (minX + maxX) / 2;
  const cy = (minY + maxY) / 2;
  const zoom = 1.12;
  w /= zoom;
  h /= zoom;
  state.view = { x: cx - w / 2, y: cy - h / 2, w, h };
  state.fitW = w;
  applyView();
}

function zoomAt(factor, clientX, clientY) {
  if (!state.view) fitView();
  const v = state.view;
  const rect = $("#map").getBoundingClientRect();
  const fx = clientX == null ? 0.5 : Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
  const fy = clientY == null ? 0.5 : Math.min(1, Math.max(0, (clientY - rect.top) / rect.height));
  const w = Math.min(2200, Math.max(120, v.w * factor));
  const h = Math.min(1400, Math.max(80, v.h * factor));
  state.view = { x: v.x + (v.w - w) * fx, y: v.y + (v.h - h) * fy, w, h };
  applyView();
}

async function toggleFullscreen() {
  const panel = document.querySelector(".map-panel");
  try {
    if (!document.fullscreenElement) await panel.requestFullscreen?.();
    else await document.exitFullscreen?.();
  } catch { /* trình duyệt từ chối thì thôi */ }
}

function initMapControls() {
  const svg = $("#map");
  const note = document.createElement("div");
  note.id = "map-note";
  note.className = "map-note";
  $(".map-wrap").appendChild(note);

  $("#zoom-in").addEventListener("click", () => zoomAt(0.8));
  $("#zoom-out").addEventListener("click", () => zoomAt(1.25));
  $("#zoom-fit").addEventListener("click", fitView);
  $("#zoom-full").addEventListener("click", toggleFullscreen);

  svg.addEventListener("wheel", (event) => {
    event.preventDefault();
    zoomAt(event.deltaY > 0 ? 1.14 : 0.88, event.clientX, event.clientY);
  }, { passive: false });
  svg.addEventListener("click", () => closeMapCard());

  const activePointers = new Map();
  let drag = null;
  let pinchStart = null;

  svg.addEventListener("pointerdown", (event) => {
    if (event.pointerType === "mouse" && event.button !== 0) return;
    activePointers.set(event.pointerId, { x: event.clientX, y: event.clientY });

    if (activePointers.size === 1) {
      drag = { x: event.clientX, y: event.clientY, view: { ...state.view }, moved: 0, captured: false };
      pinchStart = null;
    } else if (activePointers.size === 2) {
      const pts = Array.from(activePointers.values());
      const dist = Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y) || 1;
      const rect = svg.getBoundingClientRect();
      const midX = (pts[0].x + pts[1].x) / 2;
      const midY = (pts[0].y + pts[1].y) / 2;
      pinchStart = {
        dist,
        view: { ...state.view },
        midX,
        midY,
        fx: Math.min(1, Math.max(0, (midX - rect.left) / rect.width)),
        fy: Math.min(1, Math.max(0, (midY - rect.top) / rect.height)),
      };
      drag = null;
      state.suppressClick = true;
      $(".map-wrap").classList.add("is-panning");
    }
  });

  svg.addEventListener("pointermove", (event) => {
    if (!activePointers.has(event.pointerId)) return;
    activePointers.set(event.pointerId, { x: event.clientX, y: event.clientY });

    if (activePointers.size >= 2 && pinchStart) {
      const pts = Array.from(activePointers.values());
      const dist = Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y) || 1;
      const factor = pinchStart.dist / dist;
      const w = Math.min(2200, Math.max(120, pinchStart.view.w * factor));
      const h = Math.min(1400, Math.max(80, pinchStart.view.h * factor));
      state.view = {
        x: pinchStart.view.x + (pinchStart.view.w - w) * pinchStart.fx,
        y: pinchStart.view.y + (pinchStart.view.h - h) * pinchStart.fy,
        w,
        h,
      };
      applyView();
      return;
    }

    if (drag && activePointers.size === 1) {
      const rect = svg.getBoundingClientRect();
      drag.moved += Math.abs(event.movementX || 0) + Math.abs(event.movementY || 0);
      if (drag.moved > 6 && !drag.captured) {
        drag.captured = true;
        state.suppressClick = true;
        $(".map-wrap").classList.add("is-panning");
        try { svg.setPointerCapture(event.pointerId); } catch {}
      }
      state.view = {
        x: drag.view.x - ((event.clientX - drag.x) * drag.view.w) / rect.width,
        y: drag.view.y - ((event.clientY - drag.y) * drag.view.h) / rect.height,
        w: drag.view.w,
        h: drag.view.h,
      };
      applyView();
    }
  });

  const stopPointer = (event) => {
    activePointers.delete(event.pointerId);
    try { svg.releasePointerCapture(event.pointerId); } catch {}
    if (activePointers.size === 1) {
      const remaining = Array.from(activePointers.values())[0];
      drag = { x: remaining.x, y: remaining.y, view: { ...state.view }, moved: 0, captured: true };
      pinchStart = null;
    } else if (activePointers.size === 0) {
      drag = null;
      pinchStart = null;
      $(".map-wrap").classList.remove("is-panning");
      setTimeout(() => { state.suppressClick = false; }, 0);
    }
  };

  svg.addEventListener("pointerup", stopPointer);
  svg.addEventListener("pointercancel", stopPointer);

  window.addEventListener("resize", debounce(() => {
    if (!document.fullscreenElement) fitView();
  }, 120));
  document.addEventListener("fullscreenchange", () => setTimeout(fitView, 80));
  fitView();
}

async function api(path, options) {
  const response = await fetch(path, options);
  if (!response.ok) throw new Error(`${response.status} ${path}`);
  return response.json();
}

let toastTimer = null;
function toast(message, kind = "ok") {
  const box = $("#toast");
  box.innerHTML = `<img class="toast-avatar" src="/assets/avatar.jpg" alt="" />${message}`;
  box.classList.toggle("is-error", kind === "error");
  box.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { box.hidden = true; }, 3800);
}

/* ------------------------------------------------- biệt đội DuDu (mascot) */
function setMascot(html) {
  const line = $("#mascot-status");
  if (line) line.innerHTML = html;
}

function updateMascotFromPlan() {
  const metrics = state.plan?.metrics;
  if (!metrics) {
    setMascot("Biệt đội đang chờ lệnh — bấm <b>Lập kế hoạch</b> nhé!");
    return;
  }
  setMascot(`<b>${metrics.orders} đơn</b> tối ưu · Đúng giờ ${fmt1(metrics.on_time_rate)}%`);
}

const INCIDENT_PENDING = {
  breakdown: "Xe hỏng rồi! Tác tử đang chia lại tuyến…",
  congestion: "Kẹt xe diện rộng — đang tính lại ETA & tuyến…",
  depot_closed: "Kho đóng — đang tìm kho thay thế…",
  truck_ban: "Xe tải bị chặn — đang đổi xe…",
};

function updateMascotFromIncident(kind, result) {
  if (!result) { updateMascotFromPlan(); return; }
  const metrics = result.metrics;
  if (kind === "breakdown") {
    setMascot(`Đã gánh lại <b>${metrics.orders} đơn</b> cho các xe còn lại!`);
  } else if (kind === "congestion") {
    setMascot(`Kẹt xe diện rộng — đã tính lại ETA &amp; tuyến mới · <b>${metrics.late_count} trễ</b>`);
  } else if (kind === "depot_closed") {
    setMascot("Kho đóng — đã điều xe sang kho khác và lập lại tuyến!");
  } else {
    setMascot(`Đã xử lý sự cố · <b>${metrics.late_count} trễ</b>`);
  }
}

function setMascotFolded(folded) {
  state.mascotFolded = folded;
  const card = $("#mascot");
  const pill = $("#mascot-pill");
  if (!card || !pill) return;
  card.hidden = folded;
  pill.hidden = !folded;
}

function syncMascotWidth() {
  const wrap = $(".map-wrap");
  if (!wrap) return;
  if (wrap.clientWidth < 820) setMascotFolded(true);
  else if (state.mascotFoldedNarrow) setMascotFolded(false);
  state.mascotFoldedNarrow = wrap.clientWidth < 820;
}

/* ---------------------------------------------------------------- bản đồ */
function drawBase() {
  const svg = $("#map");
  svg.innerHTML = "";

  const defs = el("defs");
  const marker = el("marker", { id: "arrow", viewBox: "0 0 10 10", refX: "5", refY: "5", markerWidth: "5", markerHeight: "5", orient: "auto-start-reverse" });
  marker.appendChild(el("path", { d: "M0,0 L10,5 L0,10 z", class: "arrow" }));
  defs.appendChild(marker);
  svg.appendChild(defs);

  // lưới phủ toàn khung nhìn (không chỉ vùng 1000×640) để khi zoom/kéo không lộ nền trống
  const pattern = el("pattern", { id: "grid-pattern", width: "80", height: "80", patternUnits: "userSpaceOnUse" });
  pattern.appendChild(el("path", { d: "M80 0H0V80", fill: "none", class: "grid-path", "stroke-width": "1" }));
  defs.appendChild(pattern);
  svg.appendChild(el("rect", {
    x: -4000, y: -3000, width: 11000, height: 9000, fill: "url(#grid-pattern)", "pointer-events": "none",
  }));

  // vùng đô thị (bao lồi của các nút) để bản đồ có bối cảnh
  const points = state.hubs.map((hub) => project(hub.lat, hub.lon)).sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const cross = (o, a, b) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
  const lower = [];
  for (const point of points) {
    while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], point) <= 0) lower.pop();
    lower.push(point);
  }
  const upper = [];
  for (const point of [...points].reverse()) {
    while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], point) <= 0) upper.pop();
    upper.push(point);
  }
  const hull = lower.concat(upper.slice(1, -1));
  const hullPath = hull.map((point, index) => `${index ? "L" : "M"}${point[0].toFixed(1)},${point[1].toFixed(1)}`).join("") + "Z";
  svg.appendChild(el("path", { d: hullPath, class: "city-hull" }));

  // nhãn quận: trung bình vị trí các nút cùng quận
  const byDistrict = {};
  for (const hub of state.hubs) {
    const point = project(hub.lat, hub.lon);
    byDistrict[hub.district] = byDistrict[hub.district] || { x: 0, y: 0, n: 0 };
    byDistrict[hub.district].x += point[0];
    byDistrict[hub.district].y += point[1];
    byDistrict[hub.district].n += 1;
  }
  // đẩy nhãn quận ra phía ngoài và tránh đè lên nhãn nút
  const centre = project((state.bounds.min_lat + state.bounds.max_lat) / 2, (state.bounds.min_lon + state.bounds.max_lon) / 2);
  for (const [district, box] of Object.entries(byDistrict)) {
    let x = box.x / box.n;
    let y = box.y / box.n;
    const dx = x - centre[0];
    const dy = y - centre[1];
    const len = Math.hypot(dx, dy) || 1;
    let placed = null;
    for (const push of [58, 96, 132]) {
      const cx = x + (dx / len) * push;
      const cy = y + (dy / len) * push;
      const clash = state.hubs.some((hub) => {
        const [hx, hy] = project(hub.lat, hub.lon);
        return Math.hypot(hx - cx, hy - cy - 2) < 78;
      });
      if (!clash) { placed = [cx, cy]; break; }
    }
    if (!placed) continue;
    const label = el("text", { x: placed[0], y: placed[1], class: "district-label" });
    label.textContent = district;
    svg.appendChild(label);
  }
}

// Icon 24×24 (stroke) dùng lại đúng tệp web/assets/icons/: warehouse & package
const HUB_GLYPHS = {
  depot: [
    "M3 21V9l9-5 9 5v12",
    "M7 21v-7h10v7",
    "M7 17h10",
  ],
  hub: [
    "M12 3 3 7.5v9L12 21l9-4.5v-9z",
    "m3 7.5 9 4.5 9-4.5M12 12v9",
    "m7.5 5.3 9 4.5",
  ],
};

function drawHubs() {
  const svg = $("#map");
  document.querySelector("#hub-layer")?.remove();
  const layer = el("g", { id: "hub-layer" });
  state.hubGlyphs = [];
  for (const hub of state.hubs) {
    const [x, y] = project(hub.lat, hub.lon);
    const isDepot = hub.kind === "depot" || hub.kind === "port" || hub.kind === "market";
    const size = isDepot ? 18 : 16;
    const glyph = el("g", { class: `hub-glyph ${isDepot ? "hub-glyph--depot" : "hub-glyph--hub"}` });

    // Huy hiệu vẽ theo "đơn vị pixel" rồi scale ngược theo zoom → luôn đúng 18/16px trên màn hình
    if (isDepot) {
      glyph.appendChild(el("rect", {
        x: -size / 2, y: -size / 2, width: size, height: size, rx: 5, class: "hub-badge",
      }));
    } else {
      glyph.appendChild(el("circle", { cx: 0, cy: 0, r: size / 2, class: "hub-badge" }));
    }
    const iconSize = isDepot ? 11 : 10;
    const icon = el("g", {
      class: "hub-ico",
      transform: `translate(${-iconSize / 2} ${-iconSize / 2}) scale(${(iconSize / 24).toFixed(4)})`,
    });
    for (const d of HUB_GLYPHS[isDepot ? "depot" : "hub"]) {
      icon.appendChild(el("path", { d, class: "hub-ico-path" }));
    }
    glyph.appendChild(icon);

    const label = el("text", { x: size / 2 + 5, y: 3.5, class: "hub-label" });
    label.textContent = hub.name;
    glyph.appendChild(label);

    layer.appendChild(glyph);
    state.hubGlyphs.push({ group: glyph, x, y });
  }
  svg.appendChild(layer);
  updateHubGlyphs();
}

function updateHubGlyphs() {
  if (!state.hubGlyphs?.length) return;
  const rect = $("#map").getBoundingClientRect();
  const viewW = state.view ? state.view.w : W;
  const pxPerWorld = Math.max(rect.width / Math.max(viewW, 1), 0.0001);
  const scale = 1 / pxPerWorld;
  for (const { group, x, y } of state.hubGlyphs) {
    group.setAttribute("transform", `translate(${x.toFixed(2)} ${y.toFixed(2)}) scale(${scale.toFixed(3)})`);
  }
}

function drawScale() {
  const b = state.bounds;
  const meanLat = (b.min_lat + b.max_lat) / 2;
  const kmPerDegLon = 111.32 * Math.cos((meanLat * Math.PI) / 180);
  const kmPerPx = (kmPerDegLon * (b.max_lon - b.min_lon)) / (W - 2 * PAD);
  const target = [2, 5, 10, 20].find((km) => km / kmPerPx > 70) || 20;
  const width = target / kmPerPx;
  const group = el("g", { class: "scale-bar", transform: `translate(${PAD}, ${H - 22})` });
  group.appendChild(el("line", { x1: 0, y1: 0, x2: width, y2: 0 }));
  group.appendChild(el("line", { x1: 0, y1: -4, x2: 0, y2: 4 }));
  group.appendChild(el("line", { x1: width, y1: -4, x2: width, y2: 4 }));
  const label = el("text", { x: width / 2, y: -8, "text-anchor": "middle" });
  label.textContent = `${target} km`;
  group.appendChild(label);
  $("#map").appendChild(group);
}

/* ------------------------------------------------------- hình học tuyến */
function straightPoints(a, b) {
  const [x1, y1] = project(a.lat, a.lon);
  const [x2, y2] = project(b.lat, b.lon);
  return [[x1, y1], [x2, y2]];
}

async function geometryFor(a, b) {
  const key = `${a}|${b}`;
  if (state.geometry.has(key)) return state.geometry.get(key);
  const promise = api(`/api/geometry?a=${a}&b=${b}`)
    .then((geo) => {
      const points = geo.coordinates.map(([lon, lat]) => project(lat, lon));
      state.geometry.set(key, points);
      return points;
    })
    .catch(() => {
      state.geometry.set(key, null);
      return null;
    });
  state.geometry.set(key, promise);
  return promise;
}

function legPoints(fromId, toId) {
  const cached = state.geometry.get(`${fromId}|${toId}`);
  if (Array.isArray(cached) && cached.length) return cached;
  const a = state.hubsById.get(fromId) || state.hubs.find((hub) => hub.id === fromId);
  const b = state.hubsById.get(toId) || state.hubs.find((hub) => hub.id === toId);
  return straightPoints(a, b);
}

function toPath(points) {
  return points.map((point, index) => `${index ? "L" : "M"}${point[0].toFixed(1)},${point[1].toFixed(1)}`).join("");
}

function hubSequence(route) {
  const start = state.vehiclesById[route.vehicle_id]?.start_hub;
  const seq = route.stops.map((stop) => stop.hub_id);
  return start ? [start, ...seq] : seq;
}

function drawRoutes() {
  closeMapCard();
  const svg = $("#map");
  document.getElementById("route-layer")?.remove();
  document.getElementById("stop-layer")?.remove();
  if (!state.plan) return;

  const layer = el("g", { id: "route-layer" });
  state.plan.routes.forEach((route, index) => {
    if (!route.stops.length) return;
    const color = ROUTE_COLORS[index % ROUTE_COLORS.length];
    const seq = hubSequence(route);
    const group = el("g", { "data-vehicle": route.vehicle_id, class: "route-group" });

    const arrows = el("g");
    let d = "";
    for (let i = 0; i < seq.length - 1; i += 1) {
      const points = legPoints(seq[i], seq[i + 1]);
      d += toPath(points).replace(/^M/, i === 0 ? "M" : "L");
      if (points.length > 3) {
        const mid = Math.floor(points.length * 0.55);
        const [x1, y1] = points[mid - 1];
        const [x2, y2] = points[mid];
        const angle = (Math.atan2(y2 - y1, x2 - x1) * 180) / Math.PI;
        arrows.appendChild(el("path", {
          d: "M-4,-3 L4,0 L-4,3 Z",
          transform: `translate(${x2.toFixed(1)},${y2.toFixed(1)}) rotate(${angle.toFixed(0)})`,
          fill: color, opacity: "0.85",
        }));
      }
    }

    group.appendChild(el("path", { d, class: "leg leg-base" }));
    group.appendChild(el("path", { d, class: "leg", stroke: color, "stroke-width": 3, opacity: 0.92 }));
    group.appendChild(arrows);
    group.appendChild(el("path", { d, class: "route-hit" }));
    group.addEventListener("mouseenter", () => setActiveRoute(route.vehicle_id));
    group.addEventListener("mouseleave", () => setActiveRoute(state.activeVehicle, true));
    group.addEventListener("click", () => { if (!state.suppressClick) openVehicle(route.vehicle_id); });
    layer.appendChild(group);
  });
  svg.appendChild(layer);

  const dots = el("g", { id: "stop-layer" });
  state.plan.routes.forEach((route, index) => {
    const color = ROUTE_COLORS[index % ROUTE_COLORS.length];
    route.stops.forEach((stop, order) => {
      const [x, y] = project(stop.lat, stop.lon);
      if (stop.late) {
        dots.appendChild(el("circle", {
          cx: x, cy: y, r: 5, class: "stop-ring is-late", "data-vehicle": route.vehicle_id,
        }));
      }
      const dot = el("circle", {
        cx: x, cy: y, r: stop.late ? 4.2 : 2.9,
        fill: color,
        class: `stop-dot${stop.late ? " is-late" : ""}`,
        "data-order": stop.order_id, "data-vehicle": route.vehicle_id,
      });
      dot.style.pointerEvents = "none";
      const hit = el("circle", {
        cx: x, cy: y, r: 9, class: "stop-hit", "data-order": stop.order_id, "data-vehicle": route.vehicle_id,
      });
      hit.addEventListener("mouseenter", (event) => showTip(event, stop, route));
      hit.addEventListener("mouseleave", hideTip);
      hit.addEventListener("click", (event) => {
        event.stopPropagation();
        if (state.suppressClick) return;
        showMapCard(event, stop, route);
      });
      dots.appendChild(hit);
      dots.appendChild(dot);

      const number = el("text", {
        x, y: y + 2.7, class: "stop-num", "data-vehicle": route.vehicle_id,
      });
      number.textContent = String(order + 1);
      dots.appendChild(number);
    });
  });
  svg.appendChild(dots);

  if (state.incident?.kind) drawIncidentMarker(svg);

  if (!state.geometryDone) refineGeometry();
  applySearch();
}

function drawIncidentMarker(svg) {
  svg.querySelectorAll(".incident-marker").forEach((node) => node.remove());
  let point = null;
  let label = "SỰ CỐ";
  if (state.incident.kind === "breakdown") {
    const vehicle = state.vehiclesById[state.incident.vehicle_id];
    const hub = vehicle && (state.hubsById.get(vehicle.start_hub) || state.hubs.find((item) => item.id === vehicle.start_hub));
    if (hub) { point = project(hub.lat, hub.lon); label = "XE HỎNG"; }
  } else if (state.incident.kind === "depot_closed") {
    const hub = state.hubsById.get(state.incident.hub_id) || state.hubs.find((item) => item.id === state.incident.hub_id);
    if (hub) { point = project(hub.lat, hub.lon); label = "KHO ĐÓNG"; }
  } else {
    const lat = state.hubs.reduce((sum, hub) => sum + hub.lat, 0) / state.hubs.length;
    const lon = state.hubs.reduce((sum, hub) => sum + hub.lon, 0) / state.hubs.length;
    point = project(lat, lon);
    label = "KẸT XE";
  }
  if (!point) return;
  const layer = el("g", { class: "incident-marker" });
  const slug = state.incident.kind === "congestion" ? "ket-xe"
    : state.incident.kind === "depot_closed" ? "kho-dong" : "xe-hong";
  layer.appendChild(el("circle", { cx: point[0], cy: point[1], r: 40, class: "inc-pulse" }));
  layer.appendChild(el("image", {
    href: `/assets/markers/${slug}.svg`,
    x: point[0] - 22, y: point[1] - 53, width: 44, height: 53,
    class: "inc-pin", preserveAspectRatio: "xMidYMid meet",
  }));
  const text = el("text", { x: point[0] + 30, y: point[1] + 6, class: "inc-label" });
  text.textContent = label;
  layer.appendChild(text);
  svg.appendChild(layer);
  state.incidentMarker = { group: layer, x: point[0], y: point[1] };
  updateMarkerScale();
}

function updateMarkerScale() {
  // Giữ marker luôn ~26px trên màn hình: quy đổi từ pixel sang đơn vị thế giới của viewBox
  const marker = state.incidentMarker;
  if (!marker || !state.view) return;
  const rect = $("#map").getBoundingClientRect();
  const pxPerWorld = Math.max(rect.width / state.view.w, 0.001);
  const scale = Math.min(4, Math.max(0.2, 26 / (44 * pxPerWorld)));
  marker.group.setAttribute(
    "transform",
    `translate(${marker.x.toFixed(2)} ${marker.y.toFixed(2)}) scale(${scale.toFixed(3)}) translate(${(-marker.x).toFixed(2)} ${(-marker.y).toFixed(2)})`
  );
}

function refineGeometry() {
  if (state.projecting || state.geometryDone) return;
  state.projecting = (async () => {
    const pairs = new Set();
    for (const route of state.plan.routes) {
      const seq = hubSequence(route);
      for (let i = 0; i < seq.length - 1; i += 1) pairs.add(`${seq[i]}|${seq[i + 1]}`);
    }
    for (const pair of pairs) {
      const [a, b] = pair.split("|");
      await geometryFor(a, b);
    }
    state.projecting = null;
    state.geometryDone = true;
    if (state.plan) drawRoutes();
  })();
}

function showTip(event, stop, route) {
  const tip = $("#map-tip");
  const rect = event.target.getBoundingClientRect();
  const wrap = $(".map-wrap").getBoundingClientRect();
  tip.hidden = false;
  tip.style.left = `${rect.left - wrap.left + rect.width / 2}px`;
  tip.style.top = `${rect.top - wrap.top}px`;
  tip.textContent = `${stop.code} · ${clockLabel(stop.arrive_min)} · ${route.plate}`;
}

function hideTip() {
  $("#map-tip").hidden = true;
}

function showMapCard(event, stop, route) {
  hideTip();
  const order = state.ordersById[stop.order_id] || {};
  let card = $("#map-card");
  if (!card) {
    card = document.createElement("div");
    card.id = "map-card";
    card.className = "map-card";
    $(".map-wrap").appendChild(card);
  }
  const wrap = $(".map-wrap").getBoundingClientRect();
  const left = Math.min(Math.max(event.clientX - wrap.left - 118, 8), wrap.width - 252);
  const top = Math.min(Math.max(event.clientY - wrap.top - 150, 8), wrap.height - 190);
  card.style.left = `${left}px`;
  card.style.top = `${top}px`;
  card.innerHTML = `
    <button class="mc-close" aria-label="Đóng" title="Đóng">×</button>
    <h4>${esc(order.shop || stop.code)}</h4>
    <p class="mc-meta">${esc(stop.code)} · ${esc(route.plate)}</p>
    <dl>
      <dt>Hạn giao</dt><dd class="mono">${clockLabel(8 * 60 + (order.promised_min || 0))}</dd>
      <dt>Tới nơi</dt><dd class="mono">${clockLabel(stop.arrive_min)} ${stop.late ? `<span class="tag-late">+${fmtKm(stop.late_min)}′</span>` : ""}</dd>
      <dt>Thu hộ</dt><dd class="mono">${order.cod ? `${viNum(order.cod)} đ` : "—"}</dd>
      <dt>Hàng</dt><dd>${esc(order.goods_label || "")} · ${fmt1(stop.weight_kg)} kg</dd>
    </dl>
    <div class="mc-actions">
      <button class="btn btn-ghost" id="mc-detail">Chi tiết</button>
    </div>`;
  card.hidden = false;
  card.querySelector(".mc-close").addEventListener("click", () => { card.hidden = true; });
  card.querySelector("#mc-detail").addEventListener("click", () => {
    card.hidden = true;
    openOrder(stop.order_id, route, { back: true });
  });
  card.addEventListener("click", (clickEvent) => clickEvent.stopPropagation());
}

function closeMapCard() {
  const card = $("#map-card");
  if (card) card.hidden = true;
}

function setActiveRoute(vehicleId, reset = false) {
  if (reset && !vehicleId) return;
  state.activeVehicle = vehicleId || null;
  const active = state.activeVehicle;
  document.querySelectorAll(".route-group").forEach((group) => {
    const isActive = group.dataset.vehicle === active;
    group.classList.toggle("is-dim", Boolean(active) && !isActive);
  });
  document.querySelectorAll(".route").forEach((card) => {
    card.classList.toggle("is-active", card.dataset.vehicle === active);
  });
  document.querySelectorAll(".stop-num").forEach((label) => {
    label.classList.toggle("is-on", Boolean(active) && label.dataset.vehicle === active);
  });
  document.querySelectorAll(".g-row").forEach((row) => {
    row.classList.toggle("is-active", row.dataset.vehicle === active);
  });
}

/* ---------------------------------------------------------------- panels */
function renderKpis(metrics) {
  const blocked = metrics.blocked ?? 0;
  const total = metrics.violations ?? 0;
  $("#kpi-km").innerHTML = `${fmtKm(metrics.total_km)} <small>km</small>`;
  $("#kpi-ontime").innerHTML = `${fmt1(metrics.on_time_rate)}<small>%</small>`;
  $("#kpi-late").innerHTML = `${metrics.late_count} <small>/ ${metrics.orders}</small>`;
  $("#kpi-violations").innerHTML = `${blocked} <small>chặn</small><span class="kpi-extra"> · ${total - blocked} <small>cảnh báo</small></span>`;
  // vòng tiến độ 30px cho thẻ "Đúng giờ"
  const ring = $("#kpi-ring");
  if (ring) {
    const circumference = 2 * Math.PI * 13;
    const rate = Math.max(0, Math.min(100, Number(metrics.on_time_rate) || 0));
    ring.style.strokeDasharray = `${circumference.toFixed(1)}`;
    ring.style.strokeDashoffset = `${(circumference * (1 - rate / 100)).toFixed(1)}`;
    ring.classList.toggle("is-low", rate < 90);
  }
  const note = $("#kpi-note");
  if (note) {
    note.textContent = `${metrics.vehicles_used} xe · ${metrics.orders} điểm giao · ${fmt1(metrics.total_min)} phút xe chạy`;
  }
}

function renderRoutes(routes) {
  const container = $("#routes");
  container.innerHTML = "";
  const used = routes.filter((route) => route.stops.length);
  $("#route-count").textContent = `${used.length} tuyến`;
  if (!used.length) {
    container.innerHTML = '<p class="empty">Chưa có kế hoạch. Bấm <b>Lập kế hoạch</b> ở góc trên.</p>';
    return;
  }

  const blockedByVehicle = {};
  const warningByVehicle = {};
  for (const violation of state.plan?.violations || []) {
    const bucket = violation.level === "chan" ? blockedByVehicle : warningByVehicle;
    bucket[violation.vehicle_id] = (bucket[violation.vehicle_id] || 0) + 1;
  }

  used.sort((a, b) => b.stops.length - a.stops.length);
  for (const route of used) {
    const color = ROUTE_COLORS[routes.indexOf(route) % ROUTE_COLORS.length];
    const vehicle = state.vehiclesById[route.vehicle_id];
    const loadPct = Math.min(100, (route.load_kg / vehicle.capacity_kg) * 100);
    const blocked = blockedByVehicle[route.vehicle_id] || 0;
    const warnings = warningByVehicle[route.vehicle_id] || 0;
    const card = document.createElement("div");
    card.className = "route";
    card.dataset.vehicle = route.vehicle_id;
    card.tabIndex = 0;
    card.setAttribute("role", "button");
    card.setAttribute("aria-label", `Tuyến ${esc(route.plate)}, ${esc(route.driver)}, ${route.stops.length} điểm`);
    card.innerHTML = `
      <div class="route-top">
        <span class="route-dot" style="background:${color}"></span>
        <div>
          <div class="route-driver">${esc(route.driver)}</div>
          <div class="route-sub"><span class="route-plate">${esc(route.plate)}</span><span class="ic route-veh" style="--icon:url('/assets/icons/${vehicle.kind === "xe_may" ? "scooter" : "truck"}.svg')"></span>${esc(vehicle.label)}</div>
        </div>
        <span class="route-meta">${route.stops.length} điểm · ${fmtKm(route.total_km)} km</span>
      </div>
      <div class="route-bar">
        <div class="route-bar-track"><i class="${route.over_capacity || loadPct >= 95 ? "is-over" : loadPct >= 80 ? "is-high" : ""}" style="width:${Math.max(2, loadPct)}%;${route.over_capacity || loadPct >= 80 ? "" : `background:${color}`}"></i></div>
        <span class="route-load-pct">${Math.round(loadPct)}%</span>
      </div>
      <div class="route-foot">
        <span><b>${fmt1(route.load_kg)}/${fmtKm(vehicle.capacity_kg)}</b> kg</span>
        <span>xong <b>${clockLabel(lastArrival(route))}</b></span>
        ${route.late_count ? `<span class="badge-late">${route.late_count} trễ</span>` : ""}
        ${blocked ? `<span class="badge-block">${blocked} chặn</span>` : ""}
        ${warnings ? `<span class="badge-warn">${warnings} cảnh báo</span>` : ""}
      </div>`;
    card.addEventListener("mouseenter", () => setActiveRoute(route.vehicle_id));
    card.addEventListener("mouseleave", () => setActiveRoute(null, true));
    card.addEventListener("click", () => openVehicle(route.vehicle_id));
    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openVehicle(route.vehicle_id);
      } else if (event.key === "ArrowDown") {
        event.preventDefault();
        const next = card.nextElementSibling || container.firstElementChild;
        if (next && next.focus) next.focus();
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        const prev = card.previousElementSibling || container.lastElementChild;
        if (prev && prev.focus) prev.focus();
      }
    });
    container.appendChild(card);
  }
}

function lastArrival(route) {
  if (!route.stops.length) return 8 * 60;
  const last = route.stops[route.stops.length - 1];
  return last.arrive_min + last.service_min;
}

function renderSteps(steps) {
  const list = $("#steps");
  list.innerHTML = "";
  if (!steps?.length) {
    list.innerHTML = `<li class="steps-empty">
      <img src="/assets/stickers/dudu.png" alt="DuDu" />
      <span>Biệt đội chưa chạy — bấm <b>Lập kế hoạch</b> để xem các bước suy luận tại đây.</span>
    </li>`;
    return;
  }
  for (const step of steps) {
    const li = document.createElement("li");
    li.className = `stage-${step.stage}`;
    li.innerHTML = `
      <span class="step-stage">${stageLabel(step.stage)}</span>
      <span class="step-body"><strong>${esc(step.title)}</strong> — <span>${esc(step.detail)}</span></span>
      <span class="step-ms">+${step.ms ?? 0} ms</span>`;
    list.appendChild(li);
  }
}

function stageLabel(stage) {
  return { perceive: "nhận biết", decide: "quyết định", act: "hành động", verify: "kiểm tra" }[stage] || stage;
}

let violationFilter = "all";

function renderViolations(violations, initial) {
  const box = $("#violations");
  const meta = $("#violations-meta");
  state.violations = violations || [];
  state.violationsInitial = initial;
  const blocked = (violations || []).filter((violation) => violation.level === "chan").length;
  const total = violations?.length ?? 0;
  if (meta) {
    meta.textContent = total ? `${total} vi phạm` : "0 vi phạm";
    meta.title = initial == null ? "Vi phạm còn lại sau khi tác tử sửa"
      : `Vòng kiểm tra đầu có ${initial} vi phạm, sau khi sửa còn ${total}`;
  }
  document.querySelectorAll("#rule-filters .tab").forEach((tab) => {
    const filter = tab.dataset.filter;
    const count = filter === "all" ? total
      : (violations || []).filter((violation) => violation.level === filter).length;
    const label = { all: "Tất cả", chan: "Chặn", canh_bao: "Cảnh báo" }[filter];
    tab.textContent = `${label} (${count})`;
    tab.classList.toggle("is-active", filter === violationFilter);
  });

  if (!total) {
    box.innerHTML = '<p class="empty">Không có vi phạm — kế hoạch chạy sạch.</p>';
    return;
  }
  const shown = violationFilter === "all"
    ? violations
    : violations.filter((violation) => violation.level === violationFilter);
  box.innerHTML = shown.length ? shown
    .map((violation) => {
      const order = state.ordersById[violation.order_id];
      const vehicle = state.vehiclesById[violation.vehicle_id];
      const driverLevel = violation.rule_id === "R06" || violation.rule_id === "R10";
      const who = driverLevel && vehicle
        ? `${esc(vehicle.plate)} · ${esc(vehicle.label)}`
        : order ? `${esc(order.code)} · ${esc(order.shop)}` : "";
      return `<div class="violation" data-order="${violation.order_id}" data-vehicle="${violation.vehicle_id}" role="button" aria-label="Xem trên bản đồ">
        <span class="v-id">${esc(violation.rule_id)}</span>
        <span class="v-detail"><b>${esc(violation.title)}</b><br><span>${esc(violation.detail)}${who ? ` · ${who}` : ""}</span></span>
        <span class="v-level ${violation.level}"><span class="ic" style="--icon:url('/assets/icons/warning.svg')"></span>${violation.level === "chan" ? "chặn" : "cảnh báo"}</span>
        <span class="v-pin" aria-hidden="true">↗</span>
      </div>`;
    })
    .join("") : '<p class="empty">Không có vi phạm ở mức này.</p>';

  document.querySelectorAll(".violation[data-order]").forEach((row) => {
    row.addEventListener("click", () => {
      document.querySelectorAll(".violation").forEach((other) => other.classList.remove("is-hot"));
      row.classList.add("is-hot");
      focusOrder(row.dataset.order);
    });
  });
}

function focusOrder(orderId) {
  const order = state.ordersById[orderId];
  if (!order) return;
  const point = project(order.lat, order.lon);
  const width = 260;
  const height = 160;
  state.view = { x: point[0] - width / 2, y: point[1] - height / 2, w: width, h: height };
  applyView();
  const hit = orderIndex().get(orderId);
  openOrder(orderId, hit?.route);
}

const INCIDENT_LABEL = { breakdown: "Xe hỏng", congestion: "Kẹt xe", depot_closed: "Kho đóng", truck_ban: "Cấm tải" };

function renderIncidentStrip(result) {
  const before = result.before;
  const after = result.metrics;
  if (!before) return;
  const strip = $("#incident-strip");
  const cell = (label, before_, after_, unit, digits = 0) => {
    const roundedBefore = Math.round(before_ * (digits ? 10 : 1)) / (digits ? 10 : 1);
    const roundedAfter = Math.round(after_ * (digits ? 10 : 1)) / (digits ? 10 : 1);
    const diff = roundedAfter - roundedBefore;
    const cls = Math.abs(diff) < 0.05 ? "flat" : diff > 0 ? "up" : "down";
    const arrow = Math.abs(diff) < 0.05 ? "±" : diff > 0 ? "+" : "−";
    return `<span class="inc-cell">
      <span class="inc-name">${label}</span>
      <b>${viNum(roundedAfter, digits)}${unit}</b>
      <span class="pill-delta ${cls}">${arrow}${viNum(Math.abs(diff), digits)}${unit}</span>
    </span>`;
  };
  strip.innerHTML = `
    <span class="inc-label">Sự cố <b>${INCIDENT_LABEL[result.incident?.kind] || ""}</b></span>
    <span class="inc-sep"></span>
    ${cell("Quãng đường", before.total_km, after.total_km, " km")}
    <span class="inc-sep"></span>
    ${cell("Đơn trễ", before.late_count, after.late_count, "")}
    <span class="inc-sep"></span>
    ${cell("Vi phạm chặn", before.blocked ?? 0, after.blocked ?? 0, "")}
    <button id="incident-undo" class="btn-quiet undo-btn" title="Hoàn tác sự cố, quay lại kế hoạch gốc" aria-label="Hoàn tác sự cố">↺ Hoàn tác</button>`;
  strip.hidden = false;
  state.incident = {
    kind: result.incident?.kind,
    vehicle_id: result.incident?.vehicle_id,
    hub_id: result.incident?.hub_id,
  };
  if (state.plan) drawRoutes();
  $("#incident-undo")?.addEventListener("click", () => runPlan());
  markIncident(result.incident?.kind);
}

function markIncident(kind) {
  const map = { breakdown: "incident-breakdown", congestion: "incident-congestion", depot_closed: "incident-depot" };
  document.querySelectorAll(".incident").forEach((button) => {
    button.classList.toggle("is-active", button.id === map[kind]);
  });
  if (!kind) {
    document.querySelectorAll(".incident").forEach((button) => button.classList.remove("is-active"));
    $("#incident-strip").hidden = true;
    state.incident = null;
  }
}

/* ---------------------------------------------------------------- drawer */
function openDrawer(kicker, title, html) {
  $("#drawer-kicker").textContent = kicker;
  $("#drawer-title").textContent = title;
  $("#drawer-body").innerHTML = html;
  const drawer = $("#drawer");
  drawer.hidden = false;
  trapFocus(drawer);
}

function closeDrawer() {
  const drawer = $("#drawer");
  releaseFocus(drawer);
  drawer.hidden = true;
  drawer.classList.remove("wide");
  setRailActive("dispatch");
  const back = drawer._returnFocus;
  drawer._returnFocus = null;
  if (back && document.contains(back)) back.focus?.();
}

function openOrder(orderId, route, options = {}) {
  const order = state.ordersById[orderId];
  if (!order) return;
  $("#drawer").classList.remove("wide");
  const stop = route?.stops.find((item) => item.order_id === orderId);
  const vehicle = route ? state.vehiclesById[route.vehicle_id] : null;
  const due = 8 * 60 + order.promised_min;
  const rules = (state.plan?.violations || []).filter((violation) => violation.order_id === orderId);

  const kv = [
    ["Mã đơn", esc(order.code)],
    ["Cửa hàng", esc(order.shop)],
    ["Địa chỉ", esc(order.address)],
    ["Hàng hoá", `${esc(order.goods_label)} · ${fmt1(order.weight_kg)} kg · ${fmt1(order.volume_l)} L`],
    ["Thu hộ", order.cod ? `${viNum(order.cod)} đ` : "Không thu hộ"],
    ["Ưu tiên", `${esc(order.priority_label)} · hạn ${order.promised_min} phút`],
    ["Hạn giao", clockLabel(due)],
  ];
  if (stop) kv.push(["Tới nơi", `${clockLabel(stop.arrive_min)} (${stop.late ? `trễ ${fmtKm(stop.late_min)} phút` : "đúng hạn"})`]);
  if (vehicle) kv.push(["Tài xế", `${esc(vehicle.driver)} · ${esc(route.plate)} (${esc(vehicle.label)})`]);
  if (stop && route) kv.push(["Thứ tự", `điểm ${route.stops.indexOf(stop) + 1} / ${route.stops.length}`]);

  const rulesHtml = rules.length
    ? rules.map((violation) => `<div class="drawer-rule">
         <b>${esc(violation.rule_id)} — ${esc(violation.title)}</b>
         <span>${esc(violation.detail)}</span>
         <span class="v-level ${violation.level}"><span class="ic" style="--icon:url('/assets/icons/warning.svg')"></span>${violation.level === "chan" ? "chặn" : "cảnh báo"}</span>
        <span class="v-pin" aria-hidden="true">↗</span>
       </div>`).join("")
    : '<p class="empty" style="margin:0">Không có luật nào kích hoạt trên đơn này.</p>';

  const back = options.back ? '<button class="btn-quiet" id="drawer-back" style="margin-bottom:12px">← Danh sách đơn</button>' : "";
  openDrawer(
    `Chi tiết đơn · ${order.code}`,
    order.shop,
    `${back}<div class="drawer-section">
       <dl class="kv">${kv.map(([key, value]) => `<dt>${key}</dt><dd>${value}</dd>`).join("")}</dl>
     </div>
     <div class="drawer-section">
       <h4>Cơ sở tri thức áp cho đơn này</h4>
       ${rulesHtml}
     </div>
     ${route ? '<div class="drawer-actions"><button class="btn btn-ghost" id="drawer-open-route">Xem cả tuyến</button></div>' : ""}`,
  );

  $("#drawer-back")?.addEventListener("click", openOrders);
  const button = $("#drawer-open-route");
  if (button) button.addEventListener("click", () => openVehicle(route.vehicle_id));
}

function openVehicle(vehicleId) {
  const route = state.plan?.routes.find((item) => item.vehicle_id === vehicleId);
  if (!route) return;
  $("#drawer").classList.remove("wide");
  const vehicle = state.vehiclesById[vehicleId];
  const lateMinutes = route.late_minutes ?? 0;

  const kv = [
    ["Tài xế", esc(vehicle.driver)],
    ["Loại xe", esc(vehicle.label)],
    ["Tải", `${fmt1(route.load_kg)} / ${fmtKm(vehicle.capacity_kg)} kg`],
    ["Quãng đường", `${fmtKm(route.total_km)} km`],
    ["Thời gian chạy", `${fmtKm(route.total_min)} phút`],
    ["Số điểm", `${route.stops.length}`],
    ["Đơn trễ", route.late_count ? `${route.late_count} (${fmtKm(lateMinutes)} phút)` : "không"],
  ];

  const timeline = route.stops
    .map((stop) => {
      const order = state.ordersById[stop.order_id];
      const tail = stop.late ? `<span class="t-late" title="trễ ${fmtKm(stop.late_min)} phút">+${fmtKm(stop.late_min)}′</span>`
        : '<span class="t-ok" title="đúng hạn">✓</span>';
      return `<li>
        <time>${clockLabel(stop.arrive_min)}</time>
        <span>${order ? `${esc(order.shop)}<em class="t-addr" title="${esc(order.address)}">${esc(order.address)}</em>` : esc(stop.code)}</span>
        ${tail}
      </li>`;
    })
    .join("");

  openDrawer(
    `Tuyến · ${route.plate}`,
    `${vehicle.driver} — ${route.stops.length} điểm`,
    `<div class="drawer-section">
       <dl class="kv">${kv.map(([key, value]) => `<dt>${key}</dt><dd>${value}</dd>`).join("")}</dl>
     </div>
     <div class="drawer-section">
       <h4>Lịch giao theo giờ</h4>
       <ol class="timeline">${timeline}</ol>
     </div>`,
  );
  setActiveRoute(vehicleId);
}

/* ------------------------------------------------------------ bảng đơn */
const ORDER_COLUMNS = [
  { key: "code", label: "Mã đơn" },
  { key: "shop", label: "Cửa hàng" },
  { key: "district", label: "Quận" },
  { key: "goods", label: "Hàng" },
  { key: "weight", label: "kg", num: true },
  { key: "due", label: "Hạn", num: true },
  { key: "arrive", label: "Tới", num: true },
  { key: "status", label: "Trạng thái" },
  { key: "driver", label: "Tài xế" },
];

function orderIndex() {
  const index = new Map();
  for (const route of state.plan?.routes || []) {
    for (const stop of route.stops) index.set(stop.order_id, { route, stop });
  }
  return index;
}

function orderRows() {
  const index = orderIndex();
  const rows = [];
  for (const order of Object.values(state.ordersById)) {
    const hub = state.hubsById.get(order.dest_hub);
    const hit = index.get(order.id);
    rows.push({
      id: order.id,
      code: order.code,
      shop: order.shop,
      district: hub?.district || "",
      goods: order.goods_label,
      weight: order.weight_kg,
      due: 8 * 60 + order.promised_min,
      arrive: hit ? hit.stop.arrive_min : null,
      status: hit ? (hit.stop.late ? "trễ" : "đúng") : "chưa xếp",
      driver: hit ? `${hit.route.plate}` : "—",
      route: hit?.route,
    });
  }
  return rows;
}

function openOrders() {
  const drawer = $("#drawer");
  drawer.classList.add("wide");
  drawer.hidden = false;
  state.orderSort = state.orderSort || { key: "code", dir: 1 };
  $("#drawer-kicker").textContent = `${Object.keys(state.ordersById).length} đơn trong ca`;
  $("#drawer-title").textContent = "Danh sách đơn";

  const districts = [...new Set(Object.values(state.ordersById).map(
    (order) => state.hubsById.get(order.dest_hub)?.district).filter(Boolean))].sort();

  $("#drawer-body").innerHTML = `
    <div class="orders-head">
      <input id="orders-q" type="search" placeholder="Tìm mã đơn, cửa hàng…" aria-label="Tìm trong danh sách" />
      <select id="orders-status" aria-label="Lọc trạng thái">
        <option value="all">Mọi trạng thái</option>
        <option value="late">Chỉ đơn trễ</option>
        <option value="ok">Đúng hạn</option>
        <option value="none">Chưa xếp</option>
      </select>
      <select id="orders-district" aria-label="Lọc quận">
        <option value="all">Mọi quận</option>
        ${districts.map((district) => `<option value="${district}">${district}</option>`).join("")}
      </select>
    </div>
    <div style="overflow:auto; max-height: calc(100vh - 190px)">
      <table class="orders-table">
        <thead><tr>${ORDER_COLUMNS.map((column) => `<th data-key="${column.key}" class="${column.num ? "num" : ""}">${column.label}</th>`).join("")}</tr></thead>
        <tbody id="orders-body"></tbody>
      </table>
    </div>`;

  const ordersDrawer = $("#drawer");
  releaseFocus(ordersDrawer);
  trapFocus(ordersDrawer);

  const apply = () => {
    const query = $("#orders-q").value.trim().toLowerCase();
    const status = $("#orders-status").value;
    const district = $("#orders-district").value;
    const { key, dir } = state.orderSort;

    let rows = orderRows();
    if (query) rows = rows.filter((row) => `${row.code} ${row.shop} ${row.district} ${row.goods}`.toLowerCase().includes(query));
    if (status === "late") rows = rows.filter((row) => row.status === "trễ");
    if (status === "ok") rows = rows.filter((row) => row.status === "đúng");
    if (status === "none") rows = rows.filter((row) => row.status === "chưa xếp");
    if (district !== "all") rows = rows.filter((row) => row.district === district);

    rows.sort((a, b) => {
      const left = a[key] ?? -1;
      const right = b[key] ?? -1;
      if (typeof left === "number" && typeof right === "number") return (left - right) * dir;
      return String(left).localeCompare(String(right), "vi") * dir;
    });

    $("#orders-body").innerHTML = rows.length ? rows.map((row) => `
      <tr data-order="${row.id}">
        <td class="mono">${esc(row.code)}</td>
        <td>${esc(row.shop)}</td>
        <td>${esc(row.district)}</td>
        <td>${esc(row.goods)}</td>
        <td class="num">${fmt1(row.weight)}</td>
        <td class="num">${clockLabel(row.due)}</td>
        <td class="num">${row.arrive == null ? "—" : clockLabel(row.arrive)}</td>
        <td>${row.status === "trễ" ? '<span class="badge-late">trễ</span>'
          : row.status === "đúng" ? '<span class="badge-ok">đúng</span>'
          : '<span class="badge-none">chưa xếp</span>'}</td>
        <td class="mono">${esc(row.driver)}</td>
      </tr>`).join("") : `<tr><td colspan="9">
        <div class="drawer-empty">
          <img src="/assets/stickers/gau-nau.png" alt="Gấu Nâu" />
          <p>Không tìm thấy đơn hàng khớp bộ lọc</p>
        </div>
      </td></tr>`;

    document.querySelectorAll(".orders-table th").forEach((th) => {
      th.classList.toggle("is-sorted", th.dataset.key === key);
      th.textContent = ORDER_COLUMNS.find((column) => column.key === th.dataset.key).label
        + (th.dataset.key === key ? (dir > 0 ? " ↑" : " ↓") : "");
    });

    document.querySelectorAll("#orders-body tr[data-order]").forEach((tr) => {
      tr.addEventListener("click", () => {
        const row = rows.find((item) => item.id === tr.dataset.order);
        openOrder(row.id, row.route, { back: true });
      });
    });
  };

  document.querySelectorAll(".orders-table th").forEach((th) => {
    th.dataset.label = th.textContent;
    th.addEventListener("click", () => {
      const key = th.dataset.key;
      state.orderSort = state.orderSort.key === key
        ? { key, dir: -state.orderSort.dir }
        : { key, dir: 1 };
      apply();
    });
  });

  ["#orders-q", "#orders-status", "#orders-district"].forEach((selector) => {
    $(selector).addEventListener("input", apply);
    $(selector).addEventListener("change", apply);
  });

  apply();
}

/* ------------------------------------------------------- dòng thời gian */
function renderGantt() {
  const box = $("#gantt");
  if (!state.plan) {
    box.innerHTML = '<p class="gantt-empty">Chưa có kế hoạch.</p>';
    return;
  }
  const routes = state.plan.routes.filter((route) => route.stops.length);
  const start = 8 * 60;
  const end = Math.max(12 * 60, ...routes.map((route) => lastArrival(route)));
  const width = Math.max(560, (box.clientWidth || 640) - 46);
  const left = 88;
  const top = 30;
  const rowHeight = 24;
  const height = top + routes.length * rowHeight + 18;
  const x = (minute) => left + ((minute - start) / (end - start)) * (width - left - 12);
  const parts = [];

  for (let minute = Math.ceil(start / 60) * 60; minute <= end; minute += 60) {
    const edge = minute >= end ? -2 : 0;
    parts.push(`<line class="g-grid" x1="${x(minute).toFixed(1)}" y1="${top - 8}" x2="${x(minute).toFixed(1)}" y2="${height - 8}"/>`);
    parts.push(`<text class="g-tick" x="${(x(minute) + edge).toFixed(1)}" y="14" text-anchor="${minute >= end ? "end" : "middle"}">${clockLabel(minute)}</text>`);
  }

  routes.forEach((route, index) => {
    const y = top + index * rowHeight;
    const color = ROUTE_COLORS[state.plan.routes.indexOf(route) % ROUTE_COLORS.length];
    parts.push(`<rect class="g-row${route.vehicle_id === state.activeVehicle ? " is-active" : ""}" data-vehicle="${route.vehicle_id}" x="0" y="${y}" width="${width}" height="${rowHeight}" fill="transparent"/>`);
    parts.push(`<text class="g-label" x="0" y="${y + 13}">${esc(route.plate)}</text>`);
    parts.push(`<rect class="g-track" x="${left}" y="${y + 3}" width="${(width - left - 12).toFixed(1)}" height="16" rx="6"/>`);
    for (const stop of route.stops) {
      const from = x(stop.arrive_min);
      const to = Math.max(from + 2, x(stop.arrive_min + stop.service_min));
      parts.push(`<rect class="g-block${stop.late ? " is-late" : ""}" x="${from.toFixed(1)}" y="${y + 3}" width="${(to - from).toFixed(1)}" height="16" fill="${stop.late ? "#b3261e" : color}"><title>${esc(stop.code)} · ${clockLabel(stop.arrive_min)}${stop.late ? " · trễ" : ""}</title></rect>`);
    }
  });

  box.innerHTML = `<svg width="${width}" height="${height}" role="img" aria-label="Dòng thời gian giao hàng theo giờ">${parts.join("")}</svg>`;
}

/* ------------------------------------------------------------ in phiếu */
function printPlan() {
  if (!state.plan) return;
  let area = $("#print-area");
  if (!area) {
    document.body.insertAdjacentHTML("beforeend", '<div id="print-area"></div>');
    area = $("#print-area");
  }
  const blocks = state.plan.routes
    .filter((route) => route.stops.length)
    .map((route) => {
      const vehicle = state.vehiclesById[route.vehicle_id];
      const rows = route.stops.map((stop, index) => {
        const order = state.ordersById[stop.order_id] || {};
        return `<tr><td>${index + 1}</td><td>${stop.code}</td><td>${order.shop || ""}</td>
          <td>${order.address || ""}</td><td>${clockLabel(stop.arrive_min)}</td>
          <td>${stop.late ? "trễ" : ""}</td><td></td></tr>`;
      }).join("");
      return `<div class="p-route">
        <h2>${esc(route.plate)} — ${esc(vehicle.driver)} (${esc(vehicle.label)}) · ${route.stops.length} điểm · ${fmtKm(route.total_km)} km</h2>
        <table><thead><tr><th>TT</th><th>Mã đơn</th><th>Cửa hàng</th><th>Địa chỉ</th><th>Giờ tới</th><th>Trạng thái</th><th>Ký nhận</th></tr></thead>
        <tbody>${rows}</tbody></table></div>`;
    }).join("");

  area.innerHTML = `<h1>Phiếu giao hàng — DuDu</h1>
    <p class="p-meta">Ca 08:00 · ${state.plan.metrics.orders} đơn · ${state.plan.metrics.total_km.toFixed(0)} km ·
    ${state.plan.metrics.late_count} đơn trễ · in lúc ${new Date().toLocaleString("vi-VN")}</p>
    ${blocks}`;
  window.print();
}
/* ---------------------------------------------------------------- tìm kiếm */
function matchesSearch(order) {
  if (!state.search) return true;
  const needle = state.search.toLowerCase();
  const hub = state.hubsById.get(order.dest_hub);
  return [order.code, order.shop, order.address, order.goods_label, order.priority_label,
    order.dest_hub, hub?.name ?? "", hub?.district ?? ""].join(" ").toLowerCase().includes(needle);
}

function applySearch() {
  const chip = $("#search-count");
  const dots = document.querySelectorAll(".stop-dot");
  if (!state.search) {
    dots.forEach((dot) => dot.classList.remove("is-dim", "is-hit"));
    chip.hidden = true;
    document.querySelectorAll(".route-group").forEach((group) => group.classList.remove("is-dim"));
    return;
  }
  let hits = 0;
  dots.forEach((dot) => {
    const order = state.ordersById[dot.dataset.order];
    const hit = order ? matchesSearch(order) : false;
    dot.classList.toggle("is-hit", hit);
    dot.classList.toggle("is-dim", !hit);
    if (hit) hits += 1;
  });
  const total = Object.keys(state.ordersById).length;
  chip.textContent = `${hits}/${total} đơn khớp`;
  chip.hidden = false;
}

/* ---------------------------------------------------------------- actions */
async function loadScenario() {
  const seed = Number($("#seed").value) || 7;
  const orders = Number($("#orders").value) || 48;
  state.scenario = await api(`/api/scenario?seed=${seed}&orders=${orders}`);
  state.vehiclesById = Object.fromEntries(state.scenario.vehicles.map((item) => [item.id, item]));
  state.ordersById = Object.fromEntries(state.scenario.orders.map((item) => [item.id, item]));
  $("#scenario-meta").textContent = `${state.scenario.orders.length} đơn · ${state.scenario.vehicles.length} xe · seed ${state.scenario.seed}`;
}

function paintPlan(plan) {
  state.plan = plan;
  state.activeVehicle = null;
  state.geometryDone = false;
  drawBase();
  drawScale();
  drawRoutes();
  drawHubs();
  renderKpis(plan.metrics);
  renderRoutes(plan.routes);
  renderSteps(plan.steps);
  renderViolations(plan.violations, plan.violations_initial?.length);
  renderGantt();
  markIncident(null);
  $("#export-btn").disabled = false;
  $("#print-btn").disabled = false;
  document.querySelectorAll(".incident").forEach((button) => { button.disabled = false; });
  $("#kpi-note").textContent = `${plan.metrics.vehicles_used} xe · ${plan.metrics.orders} điểm giao · ${fmt1(plan.metrics.total_min)} phút xe chạy`;
  updateMascotFromPlan();
}

async function runPlan() {
  const button = $("#plan-btn");
  button.disabled = true;
  button.classList.add("is-busy");
  try {
    await loadScenario();
    const plan = await api("/api/plan", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        seed: Number($("#seed").value) || 7,
        orders: Number($("#orders").value) || 48,
        vehicles: state.scenario.vehicles.length,
        eta: $("#use-ml").checked ? "ml" : "osrm",
      }),
    });
    paintPlan(plan);
    updateMascotFromPlan();
    toast(`Đã lập kế hoạch: ${plan.metrics.orders} đơn · ${fmtKm(plan.metrics.total_km)} km · ${plan.metrics.late_count} trễ`);
  } catch (error) {
    toast(`Không lập được kế hoạch: ${error.message}`, "error");
  } finally {
    button.disabled = false;
    button.classList.remove("is-busy");
  }
}

async function simulateIncident(kind) {
  if (!state.plan) return;
  const used = state.plan.routes.filter((route) => route.stops.length).sort((a, b) => b.stops.length - a.stops.length);
  if (!used.length) return;
  const payload = {
    kind,
    seed: Number($("#seed").value) || 7,
    orders: Number($("#orders").value) || 48,
    eta: $("#use-ml").checked ? "ml" : "osrm",
  };
  if (kind === "breakdown") payload.vehicle_id = used[0].vehicle_id;
  setMascot(INCIDENT_PENDING[kind] || "Đang xử lý sự cố…");

  const incidentBtns = document.querySelectorAll(".incident");
  const targetBtn = $(`#incident-${kind === "depot_closed" ? "depot" : kind}`);
  incidentBtns.forEach((btn) => { btn.disabled = true; });
  if (targetBtn) targetBtn.classList.add("is-busy");

  try {
    const result = await api("/api/incident", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    });
    state.plan = result;
    state.geometryDone = false;
    drawBase();
    drawScale();
    drawRoutes();
    drawHubs();
    renderKpis(result.metrics);
    renderRoutes(result.routes);
    renderSteps(result.steps);
    renderViolations(result.violations, result.violations_initial?.length);
    renderIncidentStrip(result);
    updateMascotFromIncident(kind, result);
    toast(`${INCIDENT_LABEL[kind]} — đã lập lại kế hoạch`);
  } catch (error) {
    updateMascotFromPlan();
    toast(`Không xử lý được sự cố: ${error.message}`, "error");
  } finally {
    incidentBtns.forEach((btn) => { btn.disabled = false; });
    if (targetBtn) targetBtn.classList.remove("is-busy");
  }
}

function exportCsv() {
  if (!state.plan) return;
  const rows = [["Tài xế", "Biển số", "Xe", "Thứ tự", "Mã đơn", "Cửa hàng", "Địa chỉ", "Giờ tới", "Trạng thái", "Khối lượng (kg)"]];
  for (const route of state.plan.routes) {
    const vehicle = state.vehiclesById[route.vehicle_id];
    route.stops.forEach((stop, index) => {
      const order = state.ordersById[stop.order_id] || {};
      rows.push([
        vehicle.driver, route.plate, vehicle.label, index + 1, stop.code,
        order.shop || "", order.address || "", clockLabel(stop.arrive_min),
        stop.late ? `trễ ${Math.round(stop.late_min)} phút` : "đúng hạn",
        String(stop.weight_kg),
      ]);
    });
  }
  const csv = "\ufeff" + rows.map((row) => row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(",")).join("\r\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `dudu-ke-hoach-${$("#seed").value}-${$("#orders").value}.csv`;
  link.click();
  URL.revokeObjectURL(link.href);
  toast("Đã tải phiếu giao dạng CSV");
}

/* ---------------------------------------------------------------- modal */
async function openRules() {
  const data = await api("/api/rules");
  const initial = state.plan?.violations_initial ?? [];
  const left = state.plan?.violations ?? [];
  const countOf = (list, id) => list.filter((violation) => violation.rule_id === id).length;

  const sections = [
    ["chan", "Mức chặn — tác tử buộc phải sửa trước khi chốt kế hoạch"],
    ["canh_bao", "Mức cảnh báo — không chặn, nhưng tài xế phải xử lý thêm"],
    ["uu_tien", "Mức ưu tiên"],
  ];

  const rules = [...data.rules].sort((a, b) => a.priority - b.priority);
  const incidentMode = Boolean(state.incident);
  const html = sections
    .map(([level, title]) => {
      const group = rules.filter((rule) => rule.level === level);
      if (!group.length) return "";
      const rows = [...group]
        .sort((a, b) => Number(a.id.slice(1)) - Number(b.id.slice(1)))
        .map((rule) => {
          const before = countOf(initial, rule.id);
          const after = countOf(left, rule.id);
          const num = !state.plan ? "—" : incidentMode ? `${after}` : `${before} → ${after}`;
          const cls = !state.plan ? ""
            : before === 0 && after === 0 ? "zero"
            : after === 0 ? "done"
            : level === "chan" ? "bad"
            : "same";
          return `<tr>
            <td>${esc(rule.id)}</td>
            <td><span class="rule-title">${esc(rule.title)}</span><span class="rule-clause">${esc(rule.clause)}</span></td>
            <td class="num ${cls}">${num}</td>
          </tr>`;
        })
        .join("");
      const head = incidentMode ? "Sau sự cố" : "Đầu → còn";
      return `<p class="cmp-title" style="margin-top:16px">${title}</p>
        <table class="rules"><thead><tr><th></th><th>Luật</th><th style="text-align:right">${head}</th></tr></thead>
        <tbody>${rows}</tbody></table>`;
    })
    .join("");

  $("#modal-title").textContent = "Cơ sở tri thức";
  $("#modal-body").innerHTML = `${html}
    <p class="rules-foot">Suy diễn tiến: duyệt luật theo thứ tự ưu tiên, gặp luật mức chặn thì dừng
    việc đánh giá đơn đó và chuyển sang đơn kế tiếp. Cột phải là số lần luật kích hoạt ở vòng kiểm
    tra đầu và số còn lại sau khi tác tử sửa kế hoạch.</p>`;
  $("#modal").hidden = false;
  trapFocus($("#modal"));
}

async function openCompare() {
  const seed = Number($("#seed").value) || 7;
  const orders = Number($("#orders").value) || 48;
  const data = await api(`/api/compare?seed=${seed}&orders=${orders}`);
  const best = (rows, key, mode = "min") =>
    rows.reduce((a, b) => ((mode === "min" ? b[key] < a[key] : b[key] > a[key]) ? b : a), rows[0]);

  const assignmentHtml = table(
    ["Chiến lược", "km", "phút", "trễ", "quá tải"],
    data.assignment.map((row) => [
      strategyLabel(row.strategy) + (row.strategy === state.plan?.strategy?.assignment
        ? '<span class="pill-now">Đang dùng</span>' : ""),
      fmt1(row.total_km),
      fmt1(row.total_min),
      row.late_count > 0 ? `<span class="bad">${row.late_count}</span>` : "0",
      row.over_capacity_routes > 0 ? `<span class="bad">${row.over_capacity_routes}</span>` : "0",
    ]),
    data.assignment.indexOf(best(data.assignment, "total_km")),
  );

  const ROUTING_KEY = {
    "Thứ tự nhập": "random",
    "Nearest Neighbor": "nearest",
    "NN + 2-opt": "two_opt",
    "Clarke–Wright": "savings",
    "C-W + 2-opt": "savings_2opt",
    "NN + 2-opt (hạn giao)": "deadline",
  };
  const currentRouting = state.plan?.strategy?.routing;
  const routingHtml = table(
    ["Chiến lược xếp tuyến", "km", "phút", "trễ", "phút trễ"],
    data.routing.map((row) => [
      row.routing + (ROUTING_KEY[row.routing] === currentRouting
        ? '<span class="pill-now">Đang dùng</span>' : ""),
      fmt1(row.total_km),
      fmt1(row.total_min),
      String(row.late_count),
      String(Math.round(row.late_minutes)),
    ]),
    data.routing.indexOf(best(data.routing, "on_time_rate", "max")),
  );

  $("#modal-title").textContent = "So sánh chiến lược";
  $("#modal-body").innerHTML = `
    <p class="cmp-title">Cách chia đơn cho tài xế</p>${assignmentHtml}
    <p class="cmp-title" style="margin-top:18px">Cách xếp thứ tự giao trong tuyến</p>${routingHtml}
    <p class="hint" style="margin-top:12px">Cùng một lô ${orders} đơn, seed ${seed}, cùng cách xếp tuyến. Dòng tô cam là chiến lược tốt nhất theo cột km / đúng giờ. Số ở đây tính trên thuật toán thuần, chưa qua bước tác tử sửa vi phạm nên có thể lệch nhẹ so với kế hoạch đang hiển thị.</p>`;
  $("#modal").hidden = false;
  trapFocus($("#modal"));
}

function strategyLabel(key) {
  return {
    random: "Chia vòng tròn (thủ công)",
    greedy: "Tham lam — xe gần nhất",
    savings: "Clarke–Wright — tự gộp tuyến",
    hungarian: "Hungarian — bài toán gán",
  }[key] || key;
}

function table(headers, rows, highlightIndex) {
  const head = `<tr>${headers.map((header) => `<th>${header}</th>`).join("")}</tr>`;
  const body = rows
    .map((cells, index) => `<tr class="${index === highlightIndex ? "is-best" : ""}">${cells.map((cell) => `<td>${cell}</td>`).join("")}</tr>`)
    .join("");
  return `<table class="cmp">${head}${body}</table>`;
}

function setCompact(on) {
  const shell = document.querySelector(".shell");
  shell.classList.toggle("is-compact", on);
  const button = $("#log-toggle");
  if (button) {
    button.textContent = on ? "Mở rộng" : "Thu gọn";
    button.setAttribute("aria-expanded", String(!on));
  }
  localStorage.setItem("dudu:compact", on ? "1" : "0");
  if (!document.fullscreenElement) setTimeout(fitView, 80);
}

function setRailActive(view) {
  document.querySelectorAll(".rail-btn").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.view === view);
  });
}

function closeModal() {
  const modal = $("#modal");
  releaseFocus(modal);
  modal.hidden = true;
  setRailActive("dispatch");
  const back = modal._returnFocus;
  modal._returnFocus = null;
  if (back && document.contains(back)) back.focus?.();
}

function openIntro() {
  $("#intro").hidden = false;
}

function closeIntro(save) {
  const box = $("#intro");
  if (box.hidden) return;
  box.hidden = true;
  if (save) {
    if ($("#intro-hide").checked) localStorage.setItem("dudu_intro_seen", "1");
    else localStorage.removeItem("dudu_intro_seen");
  }
}

/* ---------------------------------------------------------------- boot */
async function loadEtaInfo() {
  try {
    const info = await api("/api/eta/info");
    const box = $("#use-ml");
    const label = $("#eta-label");
    if (!info.available) {
      box.disabled = true;
      box.closest(".field").classList.add("is-off");
      label.textContent = "ETA mô hình (chưa huấn luyện)";
      return;
    }
    label.textContent = `ETA mô hình · MAE ${info.test_mae.toFixed(1)}′`;
    label.title = `Random Forest, ${info.rows.train.toLocaleString("vi-VN")} chuyến, nguồn ${info.source}`;
  } catch {
    $("#use-ml").disabled = true;
  }
}

(async function boot() {
  try {
  const hubs = await api("/api/hubs");
  state.hubs = hubs.hubs;
  state.bounds = hubs.bounds;
  state.hubsById = new Map(hubs.hubs.map((h) => [h.id, h]));
  await loadScenario();
  drawBase();
  drawScale();
  drawHubs();
  await loadEtaInfo();

  $("#plan-btn").addEventListener("click", runPlan);
  $("#compare-btn").addEventListener("click", openCompare);
  $("#export-btn").addEventListener("click", exportCsv);
  $("#print-btn").addEventListener("click", printPlan);

  /* Dark mode: áp ngay khi boot để khớp cả hệ điều hành lẫn lựa chọn đã lưu */
  const THEME_ICONS = {
    dark: '<path d="M12 4V2m0 20v-2M4.2 4.2l1.4 1.4m12.8 12.8 1.4 1.4M2 12h2m16 0h2M4.2 19.8l1.4-1.4m12.8-12.8 1.4-1.4" stroke="currentColor" stroke-width="2" stroke-linecap="round" fill="none"/><circle cx="12" cy="12" r="4.2" fill="currentColor"/>',
    light: '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z"/>',
  };
  const prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  const savedTheme = localStorage.getItem("dudu:theme");
  const initialTheme = savedTheme || (prefersDark ? "dark" : "light");
  const applyTheme = (theme) => {
    document.documentElement.setAttribute("data-theme", theme);
    const icon = $("#theme-icon");
    if (icon) icon.innerHTML = THEME_ICONS[theme] || THEME_ICONS.light;
    const button = $("#theme-btn");
    if (button) {
      button.setAttribute("aria-pressed", String(theme === "dark"));
      button.title = theme === "dark" ? "Chuyển sang giao diện sáng" : "Chuyển sang giao diện tối";
    }
    ROUTE_COLORS = readRouteColors();
    if (state.plan) {
      drawBase();
      drawScale();
      drawRoutes();
      drawHubs();
      if (typeof renderGantt === "function") renderGantt();
    } else if (state.hubs.length) {
      drawBase();
      drawScale();
      drawHubs();
    }
  };
  applyTheme(initialTheme);
  $("#theme-btn").addEventListener("click", () => {
    const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
    localStorage.setItem("dudu:theme", next);
    applyTheme(next);
  });

  $("#config-btn").addEventListener("click", () => {
    const pop = $("#config-pop");
    pop.hidden = !pop.hidden;
    $("#config-btn").setAttribute("aria-expanded", String(!pop.hidden));
  });
  document.addEventListener("click", (event) => {
    if (!event.target.closest(".config-wrap")) {
      $("#config-pop").hidden = true;
      $("#config-btn").setAttribute("aria-expanded", "false");
    }
  });
  document.querySelectorAll("#rule-filters .tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      violationFilter = tab.dataset.filter;
      renderViolations(state.violations || [], state.violationsInitial);
    });
  });
  document.querySelectorAll(".tabs[role='tablist'] .tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      const group = tab.closest(".tabs");
      group.querySelectorAll(".tab").forEach((other) => {
        const active = other === tab;
        other.classList.toggle("is-active", active);
        other.setAttribute("aria-selected", String(active));
      });
      const showSteps = tab.dataset.tab === "steps";
      $("#steps").hidden = !showSteps;
      $("#gantt").hidden = showSteps;
      document.querySelector(".shell").classList.toggle("is-timeline", !showSteps);
      if (!showSteps) {
        if (document.querySelector(".shell").classList.contains("is-compact")) setCompact(false);
        renderGantt();
      }
    });
  });
  document.querySelectorAll(".incident").forEach((button) => {
    button.addEventListener("click", () => simulateIncident(button.id.replace("incident-", "").replace("depot", "depot_closed")));
  });
  document.querySelectorAll(".rail-btn").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".rail-btn").forEach((other) => other.classList.remove("is-active"));
      button.classList.add("is-active");
      if (button.dataset.view === "rules") { closeDrawer(); openRules(); }
      if (button.dataset.view === "orders") { closeModal(); openOrders(); }
      if (button.dataset.view === "compare") { closeDrawer(); openCompare(); }
      if (button.dataset.view === "intro") { openIntro(); setRailActive("dispatch"); }
      if (button.dataset.view === "dispatch") { closeModal(); closeDrawer(); }
    });
  });

  $("#search").addEventListener("input", (event) => {
    state.search = event.target.value.trim();
    applySearch();
  });

  initMapControls();
  const compact = localStorage.getItem("dudu:compact") === "1";
  setCompact(compact);
  $("#log-toggle").addEventListener("click", () => {
    setCompact(!document.querySelector(".shell").classList.contains("is-compact"));
  });

  $("#brand-btn").addEventListener("click", openIntro);
  $("#mascot-photo").addEventListener("click", openIntro);
  $("#mascot-fold").addEventListener("click", () => setMascotFolded(true));
  $("#mascot-pill").addEventListener("click", () => setMascotFolded(false));
  window.addEventListener("resize", debounce(syncMascotWidth, 100));
  window.addEventListener("resize", debounce(updateMarkerScale, 100));
  window.addEventListener("resize", debounce(updateHubGlyphs, 100));
  syncMascotWidth();
  $("#brand-title").addEventListener("click", openIntro);
  $("#intro-close").addEventListener("click", () => closeIntro(true));
  $("#intro-start").addEventListener("click", () => closeIntro(true));
  $("#intro").addEventListener("click", (event) => { if (event.target.id === "intro") closeIntro(true); });
  if (!localStorage.getItem("dudu_intro_seen")) openIntro();

  /* Mobile bottom nav */
  document.querySelectorAll(".mob-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".mob-btn").forEach((b) => b.classList.remove("is-active"));
      btn.classList.add("is-active");
      if (btn.dataset.view === "rules") { closeDrawer(); openRules(); }
      if (btn.dataset.view === "orders") { closeModal(); openOrders(); }
      if (btn.dataset.view === "compare") { closeDrawer(); openCompare(); }
      if (btn.dataset.view === "dispatch") { closeModal(); closeDrawer(); }
    });
  });

  $("#drawer-close").addEventListener("click", closeDrawer);
  $("#modal-close").addEventListener("click", closeModal);
  $("#modal").addEventListener("click", (event) => { if (event.target.id === "modal") closeModal(); });
  document.addEventListener("keydown", (event) => {
    const typing = event.target.matches("input, select, textarea");
    if (event.key === "Escape") {
      if (typing) { event.target.blur(); return; }
      if (!$("#intro").hidden) { closeIntro(true); return; }
      closeModal();
      closeDrawer();
      return;
    }
    if (typing || event.metaKey || event.ctrlKey || event.altKey) return;
    if (event.key === "/") { event.preventDefault(); $("#search").focus(); }
    else if (event.key === "f" || event.key === "F") toggleFullscreen();
    else if (event.key === "0") fitView();
    else if (event.key === "+" || event.key === "=") zoomAt(0.8);
    else if (event.key === "-") zoomAt(1.25);
  });
  } catch (err) {
    console.error("Boot failed:", err);
    document.body.innerHTML = `<div class="boot-error">
      <h2>Không kết nối được máy chủ</h2>
      <p>DuDu cần API backend để hoạt động. Hãy chắc chắn rằng server đang chạy và thử tải lại trang.</p>
      <p style="font-family:var(--mono);font-size:12px;color:var(--ink-3)">${esc(err.message)}</p>
      <button class="btn btn-primary" onclick="location.reload()">Tải lại trang</button>
    </div>`;
  }
})();











