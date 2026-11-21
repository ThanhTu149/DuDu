/* DuDu — giao diện điều phối. Không framework, không thư viện: SVG tự vẽ + fetch API. */

const $ = (sel) => document.querySelector(sel);
const SVG_NS = "http://www.w3.org/2000/svg";

const W = 1000;
const H = 640;
const PAD = 52;

const ROUTE_COLORS = ["#c9490e", "#2c6b52", "#2f5d8c", "#8a6100", "#6b3f8c", "#a3402d", "#2f7c7c", "#5c6b2f"];

const state = {
  hubs: [],
  bounds: null,
  scenario: null,
  plan: null,
  vehiclesById: {},
  activeVehicle: null,
  geometry: new Map(),
  projecting: null,
};

/* ---------- helpers ---------- */
const fmtKm = (v) => `${v.toFixed(0)}`;
const fmt1 = (v) => v.toFixed(1);

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

async function api(path, options) {
  const response = await fetch(path, options);
  if (!response.ok) throw new Error(`${response.status} ${path}`);
  return response.json();
}

/* ---------- map ---------- */
function drawGrid() {
  const svg = $("#map");
  svg.innerHTML = "";
  for (let i = 1; i < 8; i += 1) {
    const y = PAD + ((H - 2 * PAD) / 8) * i;
    svg.appendChild(el("line", { x1: PAD, x2: W - PAD, y1: y, y2: y, class: "grid-line" }));
  }
  for (let i = 1; i < 10; i += 1) {
    const x = PAD + ((W - 2 * PAD) / 10) * i;
    svg.appendChild(el("line", { x1: x, x2: x, y1: PAD, y2: H - PAD, class: "grid-line" }));
  }
}

function drawHubs() {
  const svg = $("#map");
  const layer = el("g", { id: "hub-layer" });
  for (const hub of state.hubs) {
    const [x, y] = project(hub.lat, hub.lon);
    const isDepot = hub.kind === "depot" || hub.kind === "port" || hub.kind === "market";
    if (isDepot) {
      layer.appendChild(el("rect", {
        x: x - 4, y: y - 4, width: 8, height: 8, rx: 1.5,
        fill: "#15171c", opacity: 0.85,
      }));
    } else {
      layer.appendChild(el("circle", {
        cx: x, cy: y, r: 4.5, fill: "#fff", stroke: "#858b94", "stroke-width": 1.4,
      }));
    }
    const label = el("text", { x: x + 8, y: y + 3.5, class: "hub-label" });
    label.textContent = hub.name;
    layer.appendChild(label);
  }
  svg.appendChild(layer);
}

/* ---------- geometry (đường đi thật, tải dần) ---------- */
function straightPath(a, b) {
  const [x1, y1] = project(...a);
  const [x2, y2] = project(...b);
  return `M${x1.toFixed(1)},${y1.toFixed(1)}L${x2.toFixed(1)},${y2.toFixed(1)}`;
}

async function geometryFor(a, b) {
  const key = `${a}|${b}`;
  if (state.geometry.has(key)) return state.geometry.get(key);
  const promise = api(`/api/geometry?a=${a}&b=${b}`)
    .then((geo) => {
      const d = geo.coordinates
        .map(([lon, lat], index) => {
          const [x, y] = project(lat, lon);
          return `${index === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
        })
        .join("");
      state.geometry.set(key, d);
      return d;
    })
    .catch(() => state.geometry.set(key, null));
  state.geometry.set(key, promise);
  return promise;
}

function pathForLegs(hubIds) {
  const parts = [];
  for (let i = 0; i < hubIds.length - 1; i += 1) {
    const a = state.hubs.find((h) => h.id === hubIds[i]);
    const b = state.hubs.find((h) => h.id === hubIds[i + 1]);
    const cached = state.geometry.get(`${a.id}|${b.id}`);
    parts.push(typeof cached === "string" && cached ? cached : straightPath([a.lat, a.lon], [b.lat, b.lon]));
  }
  return parts.join("");
}

function hubSequence(route) {
  const start = state.vehiclesById[route.vehicle_id]?.start_hub;
  const seq = route.stops.map((s) => s.hub_id);
  return start ? [start, ...seq] : seq;
}

function drawRoutes() {
  const svg = $("#map");
  document.getElementById("route-layer")?.remove();
  const layer = el("g", { id: "route-layer" });

  state.plan.routes.forEach((route, index) => {
    if (!route.stops.length) return;
    const color = ROUTE_COLORS[index % ROUTE_COLORS.length];
    const d = pathForLegs(hubSequence(route));
    const group = el("g", { "data-vehicle": route.vehicle_id, class: "route-group" });
    group.appendChild(el("path", { d, class: "leg leg-base" }));
    const main = el("path", { d, class: "leg", stroke: color, "stroke-width": 3, opacity: 0.92 });
    group.appendChild(main);
    group.appendChild(el("path", { d, class: "route-hit" }));
    group.addEventListener("mouseenter", () => setActiveRoute(route.vehicle_id));
    group.addEventListener("mouseleave", () => setActiveRoute(state.activeVehicle, true));
    layer.appendChild(group);
  });

  svg.appendChild(layer);

  const dots = el("g", { id: "stop-layer" });
  state.plan.routes.forEach((route, index) => {
    const color = ROUTE_COLORS[index % ROUTE_COLORS.length];
    for (const stop of route.stops) {
      const [x, y] = project(stop.lat, stop.lon);
      const dot = el("circle", {
        cx: x, cy: y, r: stop.late ? 4 : 2.8,
        fill: stop.late ? "#b3261e" : color,
        class: "stop-dot",
        "data-vehicle": route.vehicle_id,
      });
      dot.addEventListener("mouseenter", (event) => showTip(event, stop, route));
      dot.addEventListener("mouseleave", hideTip);
      dots.appendChild(dot);
    }
  });
  svg.appendChild(dots);

  // Nâng cấp dần sang đường đi thật (OSRM) mà không chặn lần vẽ đầu
  if (!state.geometryDone) refineGeometry();
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
  const clock = clockLabel(stop.arrive_min);
  tip.textContent = `${stop.code} · ${clock} · ${route.plate}`;
}

function hideTip() {
  $("#map-tip").hidden = true;
}

function clockLabel(minutes) {
  const h = Math.floor(minutes / 60) % 24;
  const m = Math.round(minutes % 60);
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

function setActiveRoute(vehicleId, reset = false) {
  if (reset && !vehicleId) return;
  state.activeVehicle = vehicleId || null;
  const active = state.activeVehicle;
  document.querySelectorAll(".route-group").forEach((group) => {
    const isActive = group.dataset.vehicle === active;
    group.style.opacity = active ? (isActive ? "1" : "0.18") : "1";
    const main = group.querySelector("path.leg:not(.leg-base)");
    if (main) main.setAttribute("stroke-width", isActive ? "4.5" : "3");
  });
  document.querySelectorAll(".route").forEach((card) => {
    card.classList.toggle("is-active", card.dataset.vehicle === active);
  });
}

/* ---------- panels ---------- */
function renderKpis(metrics) {
  $("#kpi-km").innerHTML = `${fmtKm(metrics.total_km)} <small>km</small>`;
  $("#kpi-ontime").innerHTML = `${fmt1(metrics.on_time_rate)} <small>%</small>`;
  $("#kpi-late").innerHTML = `${metrics.late_count} <small>/ ${metrics.orders}</small>`;
  $("#kpi-violations").innerHTML = `${metrics.blocked ?? 0} <small>chặn</small>`;
}

function renderRoutes(routes) {
  const container = $("#routes");
  container.innerHTML = "";
  const used = routes.filter((r) => r.stops.length);
  $("#route-count").textContent = `${used.length} tuyến`;
  if (!used.length) {
    container.innerHTML = '<p class="empty">Chưa có kế hoạch.</p>';
    return;
  }

  used.sort((a, b) => b.stops.length - a.stops.length);
  used.forEach((route, index) => {
    const color = ROUTE_COLORS[routes.indexOf(route) % ROUTE_COLORS.length];
    const vehicle = state.vehiclesById[route.vehicle_id];
    const loadPct = Math.min(100, (route.load_kg / vehicle.capacity_kg) * 100);
    const card = document.createElement("div");
    card.className = "route";
    card.dataset.vehicle = route.vehicle_id;
    card.innerHTML = `
      <div class="route-top">
        <span class="route-plate" style="background:${color}">${route.plate}</span>
        <span class="route-driver">${route.driver}</span>
        <span class="route-meta">${route.stops.length} điểm · ${fmtKm(route.total_km)} km</span>
      </div>
      <div class="route-bar"><i class="${route.over_capacity ? "is-over" : ""}" style="width:${loadPct}%;${route.over_capacity ? "" : `background:${color}`}"></i></div>
      <div class="route-foot">
        <span>Tải <b>${fmt1(route.load_kg)}/${fmtKm(vehicle.capacity_kg)} kg</b></span>
        <span>Về muộn nhất <b>${clockLabel(lastArrival(route))}</b></span>
        ${route.late_count ? `<span class="tag-late">${route.late_count} trễ</span>` : ""}
      </div>`;
    card.addEventListener("mouseenter", () => setActiveRoute(route.vehicle_id));
    card.addEventListener("mouseleave", () => setActiveRoute(null, true));
    card.addEventListener("click", () => setActiveRoute(route.vehicle_id));
    container.appendChild(card);
  });
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
    list.innerHTML = '<li class="empty">Chưa chạy.</li>';
    return;
  }
  for (const step of steps) {
    const li = document.createElement("li");
    li.innerHTML = `
      <span class="step-idx">${String(step.index).padStart(2, "0")}</span>
      <span class="step-stage is-${step.stage}">${stageLabel(step.stage)}</span>
      <span class="step-body"><strong>${step.title}</strong> — <span>${step.detail}</span></span>`;
    list.appendChild(li);
  }
}

function stageLabel(stage) {
  return { perceive: "nhận biết", decide: "quyết định", act: "hành động", verify: "kiểm tra" }[stage] || stage;
}

function renderViolations(violations, initial) {
  const box = $("#violations");
  const meta = $("#violations-meta");
  if (meta) {
    meta.textContent = initial == null ? `${violations?.length ?? 0} vi phạm`
      : `${initial} → ${violations?.length ?? 0}`;
    meta.title = "Số vi phạm ở vòng kiểm tra đầu → còn lại sau khi tác tử sửa";
  }
  if (!violations?.length) {
    box.innerHTML = '<p class="empty">Không có vi phạm — kế hoạch chạy sạch.</p>';
    return;
  }
  box.innerHTML = violations
    .map(
      (v) => `<div class="violation">
        <span class="v-id">${v.rule_id}</span>
        <span class="v-detail"><b>${v.title}</b><br><span>${v.detail}</span></span>
        <span class="v-level ${v.level}">${v.level === "chan" ? "chặn" : "cảnh báo"}</span>
      </div>`,
    )
    .join("");
}

/* ---------- actions ---------- */
async function loadScenario() {
  const seed = Number($("#seed").value) || 7;
  const orders = Number($("#orders").value) || 48;
  state.scenario = await api(`/api/scenario?seed=${seed}&orders=${orders}`);
  state.vehiclesById = Object.fromEntries(state.scenario.vehicles.map((v) => [v.id, v]));
  $("#scenario-meta").textContent = `${state.scenario.orders.length} đơn · ${state.scenario.vehicles.length} xe · seed ${state.scenario.seed}`;
}

async function runPlan() {
  const button = $("#plan-btn");
  button.disabled = true;
  button.lastChild.textContent = " Đang tính…";
  try {
    await loadScenario();
    const payload = {
      seed: Number($("#seed").value) || 7,
      orders: Number($("#orders").value) || 48,
      vehicles: state.scenario.vehicles.length,
      eta: $("#use-ml").checked ? "ml" : "osrm",
    };
    const plan = await api("/api/plan", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    });
    state.plan = plan;
    state.activeVehicle = null;
    state.geometryDone = false;
    drawGrid();
    drawHubs();
    drawRoutes();
    renderKpis(plan.metrics);
    renderRoutes(plan.routes);
    renderSteps(plan.steps);
    renderViolations(plan.violations, plan.violations_initial?.length);
    document.querySelectorAll(".incident").forEach((button) => { button.disabled = false; });
    $("#map-hint").textContent = `${plan.metrics.orders} điểm giao · ${fmt1(plan.metrics.total_min)} phút xe chạy`;
  } catch (error) {
    $("#map-hint").textContent = `Lỗi: ${error.message}`;
  } finally {
    button.disabled = false;
    button.lastChild.textContent = " Lập kế hoạch";
  }
}

async function simulateIncident(kind) {
  if (!state.plan) return;
  const used = state.plan.routes.filter((r) => r.stops.length).sort((a, b) => b.stops.length - a.stops.length);
  if (!used.length) return;

  const payload = {
    kind,
    seed: Number($("#seed").value) || 7,
    orders: Number($("#orders").value) || 48,
    eta: $("#use-ml").checked ? "ml" : "osrm",
  };
  if (kind === "breakdown") payload.vehicle_id = used[0].vehicle_id;

  const result = await api("/api/incident", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });

  state.plan = result;
  state.geometryDone = false;
  drawGrid();
  drawHubs();
  drawRoutes();
  renderKpis(result.metrics);
  renderRoutes(result.routes);
  renderSteps(result.steps);
  renderViolations(result.violations, result.violations_initial?.length);
  renderIncidentStrip(result);
}

const INCIDENT_LABEL = { breakdown: "Xe hỏng", congestion: "Kẹt xe", depot_closed: "Kho đóng", truck_ban: "Cấm tải" };

function renderIncidentStrip(result) {
  const before = result.before;
  const after = result.metrics;
  if (!before) return;
  const strip = $("#incident-strip");
  const delta = (a, b, unit, digits = 0) => {
    const diff = b - a;
    const cls = Math.abs(diff) < 0.05 ? "" : diff > 0 ? "up" : "down";
    const text = `${diff > 0 ? "+" : ""}${diff.toFixed(digits)}${unit}`;
    return `<i class="${cls}">${text}</i>`;
  };
  const cells = [
    ["Quãng đường", `${before.total_km.toFixed(0)}→${after.total_km.toFixed(0)} km`, delta(before.total_km, after.total_km, " km")],
    ["Đơn trễ", `${before.late_count}→${after.late_count}`, delta(before.late_count, after.late_count, "")],
    ["Vi phạm", `${before.violations}→${after.violations}`, delta(before.violations, after.violations, "")],
  ];
  strip.innerHTML = `
    <div class="incident-cell" style="grid-column:1 / -1; background:#fff; padding:6px 10px">
      <span>Sự cố ${INCIDENT_LABEL[result.incident?.kind] || ""} — kế hoạch trước → sau</span>
    </div>` + cells
    .map(([label, value, diff]) => `<div class="incident-cell"><span>${label}</span><b>${value}</b> ${diff}</div>`)
    .join("");
  strip.hidden = false;
}

async function openRules() {
  const data = await api("/api/rules");
  const initial = state.plan?.violations_initial ?? [];
  const left = state.plan?.violations ?? [];
  const countOf = (list, id) => list.filter((v) => v.rule_id === id).length;

  const sections = [
    ["chan", "Mức chặn — tác tử buộc phải sửa trước khi chốt kế hoạch"],
    ["canh_bao", "Mức cảnh báo — không chặn, nhưng tài xế phải xử lý thêm"],
    ["uu_tien", "Mức ưu tiên"],
  ];

  const rules = [...data.rules].sort((a, b) => a.priority - b.priority);
  const html = sections
    .map(([level, title]) => {
      const group = rules.filter((rule) => rule.level === level);
      if (!group.length) return "";
      const rows = group
        .map((rule) => {
          const before = countOf(initial, rule.id);
          const after = countOf(left, rule.id);
          const num = state.plan ? `${before} → ${after}` : "—";
          return `<tr>
            <td>${rule.id}</td>
            <td><span class="rule-title">${rule.title}</span><span class="rule-clause">${rule.clause}</span></td>
            <td class="num">${num}</td>
          </tr>`;
        })
        .join("");
      return `<p class="cmp-title" style="margin-top:16px">${title}</p>
        <table class="rules"><thead><tr><th></th><th>Luật</th><th style="text-align:right">Đầu → còn</th></tr></thead>
        <tbody>${rows}</tbody></table>`;
    })
    .join("");

  $("#modal-title").textContent = "Cơ sở tri thức";
  $("#modal-body").innerHTML = `${html}
    <p class="rules-foot">Suy diễn tiến: duyệt luật theo thứ tự ưu tiên, gặp luật mức chặn thì dừng
    việc đánh giá đơn đó và chuyển sang đơn kế tiếp. Cột phải là số lần luật kích hoạt ở vòng kiểm
    tra đầu và số còn lại sau khi tác tử sửa kế hoạch.</p>`;
  $("#modal").hidden = false;
}

async function openCompare() {
  const seed = Number($("#seed").value) || 7;
  const orders = Number($("#orders").value) || 48;
  const data = await api(`/api/compare?seed=${seed}&orders=${orders}`);
  const best = (rows, key, mode = "min") =>
    rows.reduce((a, b) => ((mode === "min" ? b[key] < a[key] : b[key] > a[key]) ? b : a), rows[0]);

  const assignmentHtml = table(
    ["Chiến lược", "km", "phút", "trễ", "quan tải"],
    data.assignment.map((r) => [
      strategyLabel(r.strategy),
      fmt1(r.total_km),
      fmt1(r.total_min),
      String(r.late_count),
      String(r.over_capacity_routes),
    ]),
    data.assignment.indexOf(best(data.assignment, "total_km")),
  );

  const routingHtml = table(
    ["Chiến lược xếp tuyến", "km", "phút", "trễ", "phút trễ"],
    data.routing.map((r) => [
      r.routing,
      fmt1(r.total_km),
      fmt1(r.total_min),
      String(r.late_count),
      String(Math.round(r.late_minutes)),
    ]),
    data.routing.indexOf(best(data.routing, "on_time_rate", "max")),
  );

  $("#modal-body").innerHTML = `
    <p class="cmp-title">Cách chia đơn cho tài xế</p>${assignmentHtml}
    <p class="cmp-title" style="margin-top:18px">Cách xếp thứ tự giao trong tuyến</p>${routingHtml}
    <p class="hint" style="margin-top:12px">Cùng một lô ${orders} đơn, seed ${seed}, cùng cách xếp tuyến. Dòng tô cam là chiến lược tốt nhất theo cột km / đúng giờ. Số ở đây tính trên thuật toán thuần, chưa qua bước tác tử sửa vi phạm nên có thể lệch nhẹ so với kế hoạch đang hiển thị.</p>`;
  $("#modal").hidden = false;
}

function strategyLabel(key) {
  return {
    random: "Chia vòng tròn (thủ công)",
    greedy: "Tham lam — xe gần nhất",
    savings: "Clarke–Wright — tự gộp tuyến",
    hungarian: "Hungary — bài toán gán",
  }[key] || key;
}

function table(headers, rows, highlightIndex) {
  const head = `<tr>${headers.map((h) => `<th>${h}</th>`).join("")}</tr>`;
  const body = rows
    .map((cells, index) => `<tr class="${index === highlightIndex ? "is-best" : ""}">${cells.map((c) => `<td>${c}</td>`).join("")}</tr>`)
    .join("");
  return `<table class="cmp">${head}${body}</table>`;
}

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

/* ---------- boot ---------- */
(async function boot() {
  const hubs = await api("/api/hubs");
  state.hubs = hubs.hubs;
  state.bounds = hubs.bounds;
  await loadScenario();
  drawGrid();
  drawHubs();
  await loadEtaInfo();

  $("#plan-btn").addEventListener("click", runPlan);
  document.querySelectorAll(".incident").forEach((button) => {
    button.addEventListener("click", () => simulateIncident(button.id.replace("incident-", "").replace("depot", "depot_closed")));
  });
  $("#compare-btn").addEventListener("click", openCompare);
  document.querySelectorAll(".rail-btn").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".rail-btn").forEach((other) => other.classList.remove("is-active"));
      button.classList.add("is-active");
      if (button.dataset.view === "rules") openRules();
      if (button.dataset.view === "routes") $("#routes").scrollIntoView({ behavior: "smooth", block: "start" });
      if (button.dataset.view === "dispatch") $("#modal").hidden = true;
    });
  });
  $("#modal-close").addEventListener("click", () => { $("#modal").hidden = true; });
  $("#modal").addEventListener("click", (event) => {
    if (event.target.id === "modal") $("#modal").hidden = true;
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") $("#modal").hidden = true;
  });
})();

