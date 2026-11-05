/* =========================================================================
   AETHER front-end — vanilla JS single-page app (no build step)
   ========================================================================= */
"use strict";

const AUTHOR = { name: "Sara Castrillón", url: "https://github.com/saracastrillons" };

// ---------- tiny helpers ----------
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const md = (s) => esc(s).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const debounce = (fn, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };
const MN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const ml = (m) => (/^\d{4}-\d{2}$/.test(m) ? `${MN[+m.slice(5) - 1]} ’${m.slice(2, 4)}` : m);
const mlong = (m) => `${MN[+m.slice(5) - 1]} ${m.slice(0, 4)}`;
const fmt = {
  usd: (n) => (n < 0 ? "−$" : "$") + Math.abs(Math.round(n)).toLocaleString("en-US"),
  k: (n) => { const a = Math.abs(n), s = n < 0 ? "−$" : "$"; return a >= 1e6 ? s + (a / 1e6).toFixed(2) + "M" : a >= 1e3 ? s + (a / 1e3).toFixed(1) + "K" : s + Math.round(a); },
  num: (n) => Math.round(n).toLocaleString("en-US"),
  pct: (n, d = 1) => (n > 0 ? "+" : n < 0 ? "−" : "") + Math.abs(n).toFixed(d) + "%",
};
const sum = (a) => a.reduce((x, y) => x + y, 0);
const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const rgba = (hex, a) => { const h = hex.replace("#", ""); const n = parseInt(h.length === 3 ? h.replace(/./g, "$&$&") : h, 16); return `rgba(${n >> 16},${(n >> 8) & 255},${n & 255},${a})`; };
const initials = (s) => String(s || "?").replace(/[^a-zA-Z0-9 ]/g, " ").trim().split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase() || "?";

// ---------- icons (lucide-style, stroke) ----------
const ICONS = {
  home: '<path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/>',
  spark: '<path d="M12 3l1.9 5.6 5.6 1.9-5.6 1.9L12 18l-1.9-5.6-5.6-1.9 5.6-1.9z"/><path d="M19 3v4M17 5h4"/>',
  lab: '<path d="M9 3h6M10 3v6L4.5 19a1.5 1.5 0 0 0 1.3 2h12.4a1.5 1.5 0 0 0 1.3-2L14 9V3"/><path d="M7 15h10"/>',
  sliders: '<path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6"/>',
  users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>',
  db: '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/><path d="M3 12c0 1.66 4 3 9 3s9-1.34 9-3"/>',
  bell: '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/>',
  shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/>',
  report: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M16 13H8M16 17H8M10 9H8"/>',
  search: '<circle cx="11" cy="11" r="7.5"/><path d="m21 21-4.3-4.3"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M6.3 17.7l-1.4 1.4M19.1 4.9l-1.4 1.4"/>',
  moon: '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
  logout: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/>',
  menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
  trend: '<path d="m22 7-8.5 8.5-5-5L2 17"/><path d="M16 7h6v6"/>',
  region: '<circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15 15 0 0 1 4 10 15 15 0 0 1-4 10 15 15 0 0 1-4-10 15 15 0 0 1 4-10z"/>',
  product: '<path d="m21 8-9-5-9 5 9 5 9-5z"/><path d="M3 8v8l9 5 9-5V8M12 13v8"/>',
  alert: '<path d="m21.7 18-8-14a2 2 0 0 0-3.4 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.7-3z"/><path d="M12 9v4M12 17h.01"/>',
  forecast: '<path d="M3 3v18h18"/><path d="m7 15 4-4 3 3 6-6"/><path d="M17 8h3v3"/>',
  pulse: '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
  upload: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12"/>',
  download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/>',
  send: '<path d="m22 2-7 20-4-9-9-4z"/><path d="M22 2 11 13"/>',
  print: '<path d="M6 9V2h12v7M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/>',
  trash: '<path d="M3 6h18M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6M10 11v6M14 11v6M9 6V4h6v2"/>',
  copy: '<rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  refresh: '<path d="M21 12a9 9 0 1 1-3-6.7L21 8"/><path d="M21 3v5h-5"/>',
  arrow: '<path d="M5 12h14M13 5l7 7-7 7"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
  mail: '<rect x="2" y="4" width="20" height="16" rx="2"/><path d="m22 7-10 6L2 7"/>',
  cpu: '<rect x="5" y="5" width="14" height="14" rx="2"/><path d="M9 9h6v6H9zM9 1v4M15 1v4M9 19v4M15 19v4M1 9h4M1 15h4M19 9h4M19 15h4"/>',
};
const icon = (n) => `<svg class="i" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[n] || ""}</svg>`;
const paintIcons = (root = document) => $$("[data-i]", root).forEach((el) => { if (!el.firstChild) el.innerHTML = icon(el.dataset.i); });

// ---------- state ----------
const S = { token: null, sess: null, D: null, charts: {}, chat: [], pendingAsk: null, alerts: [], h: 6, lab: null, labModel: null, range: 12, info: null };
const ROLE_CAN = { write: ["admin", "analyst"], admin: ["admin"] };
const can = (k) => S.sess && ROLE_CAN[k].includes(S.sess.role);

// ---------- toasts ----------
function toast(msg, kind = "ok") {
  const t = document.createElement("div");
  t.className = `toast ${kind}`;
  t.innerHTML = `<span class="ti">${kind === "ok" ? "✓" : kind === "err" ? "!" : "i"}</span><span>${esc(msg)}</span>`;
  $("#toasts").append(t);
  setTimeout(() => { t.classList.add("out"); setTimeout(() => t.remove(), 300); }, 3600);
}

// ---------- API ----------
async function api(path, { method = "GET", body } = {}) {
  const r = await fetch("/api/" + path, {
    method, body: body ? JSON.stringify(body) : undefined,
    headers: { "Content-Type": "application/json", ...(S.token ? { Authorization: "Bearer " + S.token } : {}) },
  });
  const j = await r.json().catch(() => ({}));
  if (r.status === 401 && S.token) { logout(); toast("Your session expired. Please sign in again.", "err"); throw new Error("401"); }
  if (!r.ok) {
    const msg = Array.isArray(j.detail) ? j.detail.map((d) => d.msg).join(", ") : j.detail || "Something went wrong";
    throw new Error(msg);
  }
  return j;
}

// =========================================================================
//  LANDING
// =========================================================================
function initLanding() {
  $("#credit").innerHTML = `Designed &amp; built by <a href="${esc(AUTHOR.url)}" target="_blank" rel="noopener">${esc(AUTHOR.name)}</a> · ${new Date().getFullYear()}`;
  const io = new IntersectionObserver((es) => es.forEach((e) => e.isIntersecting && (e.target.classList.add("in"), io.unobserve(e.target))), { threshold: 0.12 });
  $$(".reveal").forEach((el) => io.observe(el));
  const pv = $(".preview");
  const onScroll = () => { if (!$("#landing").hidden) pv.style.setProperty("--tilt", Math.max(0, 22 - (scrollY / (innerHeight * 0.55)) * 22).toFixed(2) + "deg"); };
  addEventListener("scroll", onScroll, { passive: true });
  field();
}

/* Animated "aether field": a perspective-projected wave surface of points that follows the cursor. */
function field() {
  const cv = $("#field"), ctx = cv.getContext("2d");
  const COLS = 76, ROWS = 36; let w = 0, h = 0, dpr = 1, t = 0, mx = 0, my = 0, tx = 0, ty = 0;
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const resize = () => { dpr = Math.min(devicePixelRatio || 1, 2); w = cv.clientWidth; h = cv.clientHeight; cv.width = w * dpr; cv.height = h * dpr; ctx.setTransform(dpr, 0, 0, dpr, 0, 0); };
  resize(); addEventListener("resize", resize);
  addEventListener("pointermove", (e) => { tx = e.clientX / innerWidth - 0.5; ty = e.clientY / innerHeight - 0.5; }, { passive: true });
  const A = [167, 139, 250], B = [34, 211, 238], C = [244, 114, 182];
  function frame() {
    requestAnimationFrame(frame);
    if ($("#landing").hidden || document.hidden || scrollY > innerHeight * 1.3) return;
    t += reduce ? 0 : 0.0075; mx += (tx - mx) * 0.04; my += (ty - my) * 0.04;
    ctx.clearRect(0, 0, w, h);
    const f = Math.max(w, 700) * 0.42, hor = Math.min(h * 0.42, innerHeight * 0.5) + my * 30, light = document.documentElement.dataset.theme === "light";
    ctx.globalCompositeOperation = light ? "source-over" : "lighter";
    for (let i = 0; i < ROWS; i++) {
      const Z = 13 - i * 0.33;
      for (let j = 0; j < COLS; j++) {
        const u = j / (COLS - 1), X = (u - 0.5) * 26;
        const Y = Math.sin(X * 0.42 + t * 2.1) * 0.55 + Math.cos(Z * 0.55 - t * 1.6) * 0.6 + Math.sin((X + Z) * 0.28 + t) * 0.45;
        const px = w / 2 + ((X + mx * 3) / Z) * f, py = hor + ((Y + 3.2) / Z) * f * 0.62;
        if (px < -10 || px > w + 10 || py > h + 10) continue;
        const near = 1 - Z / 13, lift = (Y + 1.6) / 3.2;
        const col = u < 0.5 ? A.map((a, k) => a + (B[k] - a) * u * 2) : B.map((b, k) => b + (C[k] - b) * (u - 0.5) * 2);
        const alpha = Math.min(1, 0.12 + near * 1.05) * (0.4 + lift * 0.75) * (light ? 0.8 : 0.85);
        const s = 0.8 + near * 2.6;
        ctx.fillStyle = `rgba(${col[0] | 0},${col[1] | 0},${col[2] | 0},${alpha.toFixed(3)})`;
        ctx.fillRect(px, py, s, s);
      }
    }
  }
  frame();
}

// spotlight that follows the cursor on cards
document.addEventListener("pointermove", (e) => {
  const c = e.target.closest?.(".card"); if (!c) return;
  const r = c.getBoundingClientRect(); c.style.setProperty("--mx", e.clientX - r.left + "px"); c.style.setProperty("--my", e.clientY - r.top + "px");
}, { passive: true });

// =========================================================================
//  AUTH
// =========================================================================
let AUTH_MODE = "in", INVITE = new URLSearchParams(location.search).get("invite");
function openAuth(mode = "in") {
  AUTH_MODE = mode;
  const card = $(".auth"); card.classList.toggle("reg", mode === "reg");
  $$("#auth-tabs button").forEach((b) => b.classList.toggle("on", b.dataset.m === mode));
  $("#auth-tabs").hidden = mode === "inv"; $("#demo-accts").hidden = mode === "inv";
  if (mode !== "inv") {
    $("#auth-title").textContent = mode === "reg" ? "Create your workspace" : "Welcome back";
    $("#auth-sub").textContent = mode === "reg" ? "A new organization with you as admin. Start empty and import your data." : "Sign in to your workspace.";
  }
  $("#auth-go").textContent = { in: "Sign in →", reg: "Create organization →", inv: "Join team →" }[mode];
  $("#f-pass").autocomplete = mode === "in" ? "current-password" : "new-password";
  $("#f-pass").placeholder = mode === "in" ? "••••••••" : "At least 8 characters";
  $("#auth-err").textContent = ""; $("#auth").hidden = false;
  setTimeout(() => (mode === "reg" ? $("#f-org") : $("#f-user")).focus(), 50);
}
const closeModal = (id) => { $(id).hidden = true; };

async function submitAuth(e) {
  e.preventDefault();
  const btn = $("#auth-go"), label = btn.textContent; btn.disabled = true; btn.textContent = "Please wait…"; $("#auth-err").textContent = "";
  const username = $("#f-user").value.trim(), password = $("#f-pass").value;
  try {
    const j = AUTH_MODE === "reg" ? await api("auth/register", { method: "POST", body: { org_name: $("#f-org").value, email: $("#f-email").value, username, password } })
      : AUTH_MODE === "inv" ? await api("invites/accept", { method: "POST", body: { token: INVITE, username, password } })
      : await api("auth/login", { method: "POST", body: { username, password } });
    enterApp(j, username);
  } catch (err) { $("#auth-err").textContent = err.message; }
  finally { btn.disabled = false; btn.textContent = label; }
}

async function loginAs(u) {
  try { const j = await api("auth/login", { method: "POST", body: { username: u, password: u } }); enterApp(j, u); }
  catch (e) { toast(e.message, "err"); }
}

function decode(tok) { try { return JSON.parse(atob(tok.split(".")[1].replace(/-/g, "+").replace(/_/g, "/"))); } catch { return null; } }

function enterApp(j, username) {
  const p = decode(j.token);
  S.token = j.token; S.sess = { token: j.token, role: j.role, org: j.org, user: p?.sub || username };
  try { sessionStorage.setItem("aether.session", JSON.stringify(S.sess)); } catch {}
  if (INVITE) { history.replaceState(null, "", "/"); INVITE = null; }
  $("#auth").hidden = true; $("#landing").hidden = true; $("#app").hidden = false;
  scrollTo(0, 0); buildShell();
  if (!location.hash.startsWith("#/")) location.hash = "#/overview"; else route();
  refreshBell();
  toast(`Signed in to ${S.sess.org} as ${S.sess.role}`, "info");
}

function logout() {
  S.token = null; S.sess = null; S.D = null; S.chat = []; S.lab = null; destroyCharts();
  try { sessionStorage.removeItem("aether.session"); } catch {}
  $("#app").hidden = true; $("#landing").hidden = false; $("#view").innerHTML = "";
  history.replaceState(null, "", "/"); scrollTo(0, 0);
}

// =========================================================================
//  SHELL / ROUTER
// =========================================================================
const NAV = [
  { grp: "Analytics" },
  { id: "overview", label: "Overview", icon: "home", sub: "Revenue, forecast and signals at a glance" },
  { id: "analyst", label: "AI Analyst", icon: "spark", sub: "Ask questions — every answer shows its reasoning" },
  { id: "forecast", label: "Forecast Lab", icon: "lab", sub: "Four models compared with rolling-origin backtesting", badge: "ML" },
  { id: "scenarios", label: "Scenarios", icon: "sliders", sub: "What-if simulation on top of the forecast" },
  { id: "churn", label: "Churn Risk", icon: "users", sub: "Classifier performance and customers at risk", badge: "ML" },
  { grp: "Workspace" },
  { id: "data", label: "Data", icon: "db", sub: "Import, validate and export your dataset" },
  { id: "alerts", label: "Alerts", icon: "bell", sub: "KPI thresholds evaluated on every refresh" },
  { id: "team", label: "Team & Audit", icon: "shield", sub: "Members, roles, invitations and activity log" },
  { id: "report", label: "Executive Report", icon: "report", sub: "A print-ready summary for stakeholders" },
];
const VIEWS = {};

function buildShell() {
  const s = S.sess;
  $("#org-name").textContent = s.org; $("#org-av").textContent = initials(s.org);
  $("#me-name").textContent = s.user; $("#me-role").textContent = s.role; $("#me-av").textContent = initials(s.user);
  $("#side-nav").innerHTML = NAV.map((n) => n.grp ? `<div class="grp">${n.grp}</div>`
    : `<a href="#/${n.id}" data-id="${n.id}">${icon(n.icon)}<span>${n.label}</span>${n.badge ? `<span class="new">${n.badge}</span>` : ""}</a>`).join("");
  $("#theme-btn").innerHTML = icon(document.documentElement.dataset.theme === "light" ? "moon" : "sun");
  $("#logout-btn").innerHTML = icon("logout"); $("#menu-btn").innerHTML = icon("menu"); $("#bell-btn").insertAdjacentHTML("afterbegin", $("#bell-btn svg") ? "" : icon("bell"));
  paintIcons($("#app"));
}

function destroyCharts() { Object.values(S.charts).forEach((c) => c?.destroy()); S.charts = {}; }

// Tokens last 8h; while the user is active we swap in a fresh one when less than 2h remain.
async function renew() {
  const p = decode(S.token); if (!p || p.exp * 1000 - Date.now() > 2 * 3600e3) return;
  try {
    const j = await api("auth/refresh", { method: "POST" });
    S.token = j.token; Object.assign(S.sess, { token: j.token, role: j.role, org: j.org });
    try { sessionStorage.setItem("aether.session", JSON.stringify(S.sess)); } catch {}
  } catch {}
}

async function openAccount() {
  const a = await api("account").catch(() => null); if (!a) return;
  $("#acct-info").innerHTML = `<div class="li"><span>Username</span><b>${esc(a.username)}</b></div><div class="li"><span>Email</span><b>${esc(a.email)}</b></div>
    <div class="li"><span>Role</span><span class="tag vi">${esc(a.role)}</span></div><div class="li"><span>Organization</span><b>${esc(a.org)}</b></div>`;
  $("#acct-form").reset(); $("#acct-err").textContent = ""; $("#acct").hidden = false;
}

async function route() {
  if (!S.token) return;
  renew();
  const id = (location.hash.match(/^#\/(\w+)/) || [])[1] || "overview";
  const n = NAV.find((x) => x.id === id) || NAV[1];
  $$("#side-nav a").forEach((a) => a.classList.toggle("on", a.dataset.id === n.id));
  $("#v-title").textContent = n.label; $("#v-sub").textContent = n.sub; document.title = `${n.label} · AETHER`;
  $("#app").classList.remove("side-open");
  destroyCharts();
  const v = $("#view"); v.innerHTML = skeleton(); v.scrollTop = 0; scrollTo(0, 0);
  try { await VIEWS[n.id](v); paintIcons(v); }
  catch (e) { if (e.message !== "401") v.innerHTML = `<div class="card empty"><div class="eic">${icon("alert")}</div><h3>Couldn’t load this view</h3><p>${esc(e.message)}</p><button class="btn ghost" onclick="route()">Retry</button></div>`; }
}

function skeleton() {
  return `<div class="vw"><div class="skel" style="height:56px;width:40%"></div><div class="kpis">${'<div class="skel" style="height:140px"></div>'.repeat(5)}</div>
  <div class="g2"><div class="skel" style="height:380px"></div><div class="skel" style="height:380px"></div></div></div>`;
}

async function overviewData(force) { if (!S.D || force) S.D = await api("overview"); return S.D; }

// ---------- charts ----------
const PALETTE = () => [css("--violet2") || "#a78bfa", css("--cyan") || "#22d3ee", "#f472b6", "#fbbf24", "#60a5fa", "#34d399"];
function chartBase() {
  const mu = css("--mu"), line = css("--line"), font = css("--font").split(",")[0].replace(/"/g, "") || "Geist";
  Chart.defaults.font.family = `${font}, system-ui, sans-serif`; Chart.defaults.color = mu;
  return {
    responsive: true, maintainAspectRatio: false, interaction: { mode: "index", intersect: false },
    animation: { duration: 900, easing: "easeOutQuart" },
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: css("--bg2"), borderColor: css("--line2"), borderWidth: 1, titleColor: css("--tx"), bodyColor: css("--tx2"),
        padding: 12, cornerRadius: 12, boxPadding: 5, usePointStyle: true, titleFont: { weight: "600" },
        callbacks: { label: (c) => (c.raw == null ? null : ` ${c.dataset.label}: ${typeof c.raw === "number" ? fmt.usd(c.raw) : c.formattedValue}`) },
        filter: (c) => c.raw != null && !c.dataset.hideTip,
      },
    },
    scales: {
      x: { grid: { display: false }, border: { display: false }, ticks: { maxRotation: 0, autoSkipPadding: 14, font: { size: 11 } } },
      y: { grid: { color: line, drawTicks: false }, border: { display: false }, ticks: { padding: 10, font: { size: 11 }, callback: (v) => fmt.k(v) } },
    },
  };
}
const fillGrad = (color, top = 0.35) => (c) => {
  const { chartArea: a, ctx } = c.chart; if (!a) return "transparent";
  const g = ctx.createLinearGradient(0, a.top, 0, a.bottom); g.addColorStop(0, rgba(color, top)); g.addColorStop(1, rgba(color, 0)); return g;
};
function mkChart(key, el, cfg) { S.charts[key]?.destroy(); S.charts[key] = new Chart(el, cfg); return S.charts[key]; }

function spark(values, color, dashedFrom = null) {
  if (!values?.length) return "";
  const W = 200, H = 46, min = Math.min(...values), max = Math.max(...values), rng = max - min || 1;
  const pts = values.map((v, i) => [(i / (values.length - 1)) * W, H - 6 - ((v - min) / rng) * (H - 14)]);
  const d = pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1)).join(" ");
  const id = "sg" + Math.random().toString(36).slice(2, 8);
  const solid = dashedFrom == null ? d : pts.slice(0, dashedFrom + 1).map((p, i) => (i ? "L" : "M") + p[0] + " " + p[1]).join(" ");
  const dash = dashedFrom == null ? "" : `<path d="${pts.slice(dashedFrom).map((p, i) => (i ? "L" : "M") + p[0] + " " + p[1]).join(" ")}" fill="none" stroke="${color}" stroke-width="1.8" stroke-dasharray="4 4"/>`;
  return `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none"><defs><linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${color}" stop-opacity=".28"/><stop offset="1" stop-color="${color}" stop-opacity="0"/></linearGradient></defs>
    <path d="${d} L${W} ${H} L0 ${H}Z" fill="url(#${id})"/><path d="${solid}" fill="none" stroke="${color}" stroke-width="1.8" stroke-linejoin="round"/>${dash}
    <circle cx="${pts.at(-1)[0] - 2}" cy="${pts.at(-1)[1]}" r="2.6" fill="${color}"/></svg>`;
}

function countUp(el, to, f, ms = 1100) {
  const t0 = performance.now();
  (function step(now) { const k = Math.min(1, (now - t0) / ms); el.textContent = f(to * (1 - Math.pow(1 - k, 4))); if (k < 1) requestAnimationFrame(step); })(t0);
}

const deltaHtml = (v, suffix = "") => v == null ? `<span class="delta"><span class="mu">needs 24 months of data</span></span>` : `<span class="delta ${v >= 0 ? "up" : "dn"}"><span class="delta-pill ${v >= 0 ? "up" : "dn"}">${v >= 0 ? "▲" : "▼"} ${fmt.pct(v).replace(/^[+−]/, "")}</span><span class="mu">${suffix}</span></span>`;

// =========================================================================
//  VIEW: OVERVIEW
// =========================================================================
VIEWS.overview = async (v) => {
  const D = await overviewData(true);
  if (!D.months.length) return emptyData(v);
  const k = D.kpis, n = D.months.length, last = D.months.at(-1);
  const hr = new Date().getHours(), part = hr < 12 ? "morning" : hr < 19 ? "afternoon" : "evening";
  const arpu = D.revenue.map((r, i) => r / Math.max(1, D.customers[i]));
  const custMom = n > 1 ? (D.customers.at(-1) / D.customers.at(-2) - 1) * 100 : 0;
  const arpuMom = n > 1 ? (arpu.at(-1) / arpu.at(-2) - 1) * 100 : 0;
  const ttm = sum(D.revenue.slice(-12));
  const P = PALETTE();
  const kpis = [
    ["Revenue · trailing 12m", ttm, fmt.k, k.ytd_growth_pct, "vs prior 12m", spark(D.revenue.slice(-12), P[0])],
    ["Last month", k.last_month, fmt.k, k.mom_pct, "MoM", spark(D.revenue.slice(-8), P[4])],
    ["Active customers", k.customers, fmt.num, custMom, "MoM", spark(D.customers.slice(-12), P[1])],
    ["Revenue per customer", k.arpu, (x) => "$" + x.toFixed(2), arpuMom, "MoM", spark(arpu.slice(-12), P[2])],
    ["Forecast · " + ml(D.forecast.months[0]), k.next_month, fmt.k, (k.next_month / k.last_month - 1) * 100, "vs last", spark([...D.revenue.slice(-5), ...D.forecast.values], P[3], 4)],
  ];
  v.innerHTML = `<div class="vw">
    <div class="welcome">
      <div><h2>Good ${part}, <em>${esc(S.sess.user)}</em></h2><p>Here’s what’s happening at ${esc(S.sess.org)} · data through ${mlong(last)}</p></div>
      <div class="row no-print">
        <div class="seg sm" id="rng">${[[6, "6M"], [12, "12M"], [99, "All"]].map(([r, l]) => `<button data-r="${r}" class="${S.range === r ? "on" : ""}">${l}</button>`).join("")}</div>
        <a class="btn ghost sm" href="#/report">${icon("report")} Report</a>
        <a class="btn primary sm" href="#/analyst">${icon("spark")} Ask AETHER</a>
      </div>
    </div>
    <div class="kpis">${kpis.map((x, i) => `<div class="card kpi"><div class="lbl"><span>${x[0]}</span></div><div class="val" id="k${i}">—</div>${deltaHtml(x[3], x[4])}<div class="spark">${x[5]}</div></div>`).join("")}</div>
    <div class="g2">
      <div class="card">
        <div class="hd"><div><h3>Revenue &amp; forecast</h3><p>${esc(D.forecast.model)} · backtested MAPE ${D.forecast.mape}% · 90% prediction band</p></div>
          <div class="legend"><span><i style="background:${P[0]}"></i>Revenue</span><span><i class="dash"></i>Forecast</span><span><i style="background:${rgba(P[1].startsWith("#") ? P[1] : "#22d3ee", .25)}"></i>90% band</span><span><i style="background:#fb7185;border-radius:50%"></i>Anomaly</span></div></div>
        <div class="chart-box"><canvas id="c-rev"></canvas></div>
      </div>
      <div class="card"><div class="hd"><div><h3>${icon("spark")} Key insights</h3><p>Computed from your data, refreshed on every change</p></div><span class="ai-badge">auto</span></div>
        <div class="insights">${D.insights.map((x) => `<div class="ins ${x.tone}"><div class="ii">${icon(x.icon)}</div><div><b>${esc(x.title)}</b><span>${esc(x.detail)}</span></div></div>`).join("") || '<p class="mu">Not enough history for insights yet.</p>'}</div>
      </div>
    </div>
    <div class="g2 eq">
      <div class="card"><div class="hd"><div><h3>Revenue by region</h3><p>Stacked monthly contribution</p></div><div class="legend" id="lg-reg"></div></div><div class="chart-box sm"><canvas id="c-reg"></canvas></div></div>
      <div class="card"><div class="hd"><div><h3>Product mix</h3><p>Share of revenue, last 12 months</p></div></div>
        <div class="row" style="gap:24px;align-items:center;flex-wrap:nowrap">
          <div class="donut-wrap" style="width:200px;height:200px;flex:none"><canvas id="c-mix"></canvas><div class="donut-center"><div><b id="mix-total"></b><small>12-month revenue</small></div></div></div>
          <div class="list" id="mix-list" style="flex:1;min-width:0"></div>
        </div>
      </div>
    </div>
    <div class="g2">
      <div class="card"><div class="hd"><div><h3>Regional heatmap</h3><p>Revenue intensity by region and month · red marks the region behind an anomaly</p></div></div><div class="heat" id="heat"></div></div>
      <div class="card"><div class="hd"><div><h3>${icon("pulse")} Anomalies</h3><p>Robust z-score on MoM growth (|z| &gt; 3.5)</p></div></div><div class="list" id="anoms"></div>
        <div class="hd" style="margin:18px 0 8px"><div><h3>Data quality</h3></div></div>
        <div class="row" style="gap:18px;flex-wrap:nowrap"><div class="ring-wrap"><div class="ring" style="--p:${D.quality.score}"></div><b>${D.quality.score}</b></div>
          <div class="list" style="flex:1"><div class="li"><span>Rows</span><b class="mono">${fmt.num(D.quality.rows)}</b></div><div class="li"><span>Months</span><b class="mono">${n}</b></div><div class="li"><span>Source</span><span class="tag ${D.data_mode === "real" ? "ok" : "vi"}">${D.data_mode === "real" ? "imported CSV" : "demo dataset"}</span></div></div></div>
      </div>
    </div>
  </div>`;
  kpis.forEach((x, i) => countUp($("#k" + i, v), x[1], x[2]));
  $$("#rng button", v).forEach((b) => (b.onclick = () => { S.range = +b.dataset.r; $$("#rng button", v).forEach((x) => x.classList.toggle("on", x === b)); drawOverviewCharts(); }));
  drawOverviewCharts();
  // product mix
  const mix = Object.entries(D.by_product).map(([p, s]) => [p, sum(s.slice(-12))]).sort((a, b) => b[1] - a[1]), mt = sum(mix.map((m) => m[1]));
  $("#mix-total").textContent = fmt.k(mt);
  $("#mix-list").innerHTML = mix.map(([p, val], i) => `<div class="li"><span><i style="display:inline-block;width:9px;height:9px;border-radius:3px;background:${P[i % 6]};margin-right:8px"></i>${esc(p)}</span><span class="mono">${(val / mt * 100).toFixed(1)}%</span></div>`).join("");
  mkChart("mix", $("#c-mix"), { type: "doughnut", data: { labels: mix.map((m) => m[0]), datasets: [{ data: mix.map((m) => m[1]), backgroundColor: mix.map((_, i) => P[i % 6]), borderWidth: 0, spacing: 3, borderRadius: 6, hoverOffset: 6 }] },
    options: { ...chartBase(), cutout: "74%", scales: {}, interaction: { mode: "nearest", intersect: true } } });
  // heatmap
  const H = D.heatmap, all = H.rows.flatMap((r) => r.values), hmax = Math.max(...all), hmin = Math.min(...all);
  const flagged = new Set(D.anomalies.filter((a) => a.driver).map((a) => a.month + "|" + a.driver.region));
  $("#heat").innerHTML = `<div class="hr" style="--n:${H.months.length}"><span></span>${H.months.map((m) => `<span class="hm">${MN[+m.slice(5) - 1]}</span>`).join("")}</div>` +
    H.rows.map((r) => `<div class="hr" style="--n:${H.months.length}"><span class="hl">${esc(r.label)}</span>${r.values.map((x, i) => `<span class="hc ${flagged.has(H.months[i] + "|" + r.label) ? "anom" : ""}" style="--a:${(0.1 + 0.85 * (x - hmin) / (hmax - hmin || 1)).toFixed(2)}" title="${esc(r.label)} · ${mlong(H.months[i])}: ${fmt.usd(x)}"></span>`).join("")}</div>`).join("");
  // anomalies
  $("#anoms").innerHTML = D.anomalies.length ? D.anomalies.map((a) => `<div class="li"><div><b>${mlong(a.month)}</b> <span class="tag ${a.severity === "medium" ? "warn" : "bad"}">${a.severity}</span>
      <small>${fmt.pct(a.change_pct)} MoM · z = ${a.score}${a.driver ? ` · ${esc(a.driver.region)} ≈ ${a.driver.share}% of the move` : ""}</small></div>
      <button class="btn ghost sm" data-ask="Why did revenue change in ${a.month}?">${icon("spark")} Explain</button></div>`).join("")
    : `<div class="li"><span class="mu">No anomalies detected — growth is within normal bounds.</span><span class="tag ok">healthy</span></div>`;
  $$("[data-ask]", v).forEach((b) => (b.onclick = () => askFromAnywhere(b.dataset.ask)));
};

function drawOverviewCharts() {
  const D = S.D, P = PALETTE(), R = S.range, s = Math.max(0, D.months.length - R);
  const m = D.months.slice(s), vals = D.revenue.slice(s), n = m.length, F = D.forecast;
  const labels = [...m, ...F.months].map(ml), pad = (a) => [...Array(n - 1).fill(null), vals[n - 1], ...a];
  const anomIdx = new Set(D.anomalies.map((a) => m.indexOf(a.month)).filter((i) => i >= 0));
  const base = chartBase();
  mkChart("rev", $("#c-rev"), {
    type: "line",
    data: { labels, datasets: [
      { label: "Revenue", data: [...vals, ...F.months.map(() => null)], borderColor: P[0], backgroundColor: fillGrad(P[0].startsWith("#") ? P[0] : "#a78bfa"), fill: true, tension: 0.38, borderWidth: 2.4, pointRadius: 0, pointHoverRadius: 5, pointHoverBackgroundColor: P[0] },
      { label: "Forecast", data: pad(F.values), borderColor: "#22d3ee", borderDash: [6, 5], borderWidth: 2.2, tension: 0.35, pointRadius: (c) => (c.dataIndex >= n ? 3.5 : 0), pointBackgroundColor: "#22d3ee" },
      { label: "Upper (90%)", data: pad(F.upper), borderColor: "transparent", backgroundColor: "rgba(34,211,238,.13)", fill: "+1", pointRadius: 0, tension: 0.35 },
      { label: "Lower (90%)", data: pad(F.lower), borderColor: "transparent", pointRadius: 0, tension: 0.35 },
      { label: "Anomaly", data: vals.map((x, i) => (anomIdx.has(i) ? x : null)).concat(F.months.map(() => null)), showLine: false, pointRadius: 6, pointHoverRadius: 8, pointBackgroundColor: "#fb7185", pointBorderColor: rgba("#fb7185", 0.35), pointBorderWidth: 8, hideTip: false },
    ] },
    options: base,
  });
  const regions = Object.keys(D.by_region);
  $("#lg-reg").innerHTML = regions.map((r, i) => `<span><i style="background:${P[i % 6]}"></i>${esc(r)}</span>`).join("");
  const b2 = chartBase(); b2.scales.x.stacked = true; b2.scales.y.stacked = true;
  mkChart("reg", $("#c-reg"), { type: "bar", data: { labels: m.map(ml), datasets: regions.map((r, i) => ({ label: r, data: D.by_region[r].slice(s), backgroundColor: P[i % 6], borderRadius: 4, borderSkipped: false, barPercentage: 0.72, categoryPercentage: 0.8 })) }, options: b2 });
}

function emptyData(v) {
  v.innerHTML = `<div class="vw"><div class="card empty" style="padding:80px 20px">
    <div class="eic">${icon("db")}</div><h3>Your workspace is ready</h3>
    <p>${esc(S.sess.org)} has no data yet. Import a CSV or Excel file with your monthly or daily sales (Spanish or English headers work) — or load the demo dataset to explore every feature right away.</p>
    <div class="row" style="justify-content:center;margin-top:8px">
      ${can("write") ? `<a class="btn primary" href="#/data">${icon("upload")} Import data</a>` : ""}
      ${can("admin") ? `<button class="btn ghost" id="load-demo">${icon("refresh")} Load demo data</button>` : ""}
      ${!can("write") ? `<p class="mu">Ask an admin or analyst to import data.</p>` : ""}
    </div></div></div>`;
  $("#load-demo", v)?.addEventListener("click", loadDemo);
}

async function loadDemo() {
  try { await api("reset", { method: "POST" }); S.D = null; S.lab = null; toast("Demo dataset loaded — 24 months, 4 regions, 3 products"); route(); refreshBell(); }
  catch (e) { toast(e.message, "err"); }
}

// =========================================================================
//  VIEW: AI ANALYST
// =========================================================================
VIEWS.analyst = async (v) => {
  if (!S.info) S.info = await api("assistant/info").catch(() => ({ llm: false, model: "aether-engine", suggestions: [] }));
  const I = S.info;
  v.innerHTML = `<div class="chat-grid vw">
    <div class="card chat">
      <div class="chat-head"><div class="who"><div class="orb" id="orb"></div><div><b>AETHER Analyst</b><small>${I.llm ? `Narrated by ${esc(I.model)} · grounded on computed facts` : "Deterministic analytics engine · every number is computed, never guessed"}</small></div></div>
        <button class="btn ghost sm" id="clear-chat">${icon("refresh")} New chat</button></div>
      <div class="log" id="log" aria-live="polite"></div>
      <div class="composer"><form id="ask-form"><input id="q" placeholder="Ask anything about your revenue, regions, products or forecast…" autocomplete="off" maxlength="500" /><button class="btn primary" type="submit">${icon("send")}<span>Ask</span></button></form></div>
    </div>
    <div>
      <div class="card side-card"><h4>How answers are built</h4><ol class="steps">
        <li>Your question is mapped to an analysis intent (driver analysis, ranking, forecast, anomalies…).</li>
        <li>The engine runs the aggregation on your organization’s data only.</li>
        <li>Every query and formula is attached as a reasoning trace you can audit.</li>
        <li>${I.llm ? "Claude rewrites the computed facts into an executive answer — it is not allowed to invent figures." : "Set <span class='mono'>ANTHROPIC_API_KEY</span> to add Claude narration on top of the engine."}</li></ol>
        <div class="msg-meta"><span class="ai-badge">${icon("cpu")} ${esc(I.model)}</span></div></div>
      <div class="card side-card"><h4>Try asking</h4><div class="sugg">${I.suggestions.map((s) => `<button class="chip" data-q="${esc(s)}">${esc(s)}</button>`).join("")}</div></div>
    </div></div>`;
  const log = $("#log", v);
  if (!S.chat.length) S.chat.push({ role: "ai", welcome: true, answer: `Hi ${S.sess.user} — I’m your analyst for **${S.sess.org}**. Ask me why a number moved, which segment is winning, or what’s coming next. I’ll show my work.` });
  S.chat.forEach((m) => log.append(renderMsg(m, false)));
  log.scrollTop = log.scrollHeight;
  $("#ask-form", v).onsubmit = (e) => { e.preventDefault(); const q = $("#q").value.trim(); if (q) { $("#q").value = ""; ask(q); } };
  $$("[data-q]", v).forEach((b) => (b.onclick = () => ask(b.dataset.q)));
  $("#clear-chat", v).onclick = () => { S.chat = []; route(); };
  if (S.pendingAsk) { const q = S.pendingAsk; S.pendingAsk = null; ask(q); } else $("#q").focus();
};

function askFromAnywhere(q) { S.pendingAsk = q; if (location.hash === "#/analyst") route(); else location.hash = "#/analyst"; }

function highlightCalc(lines) {
  // one-pass tokenizer over text where only & < > are escaped, so quotes stay literal
  const tok = /('[^']*')|\b(SELECT|FROM|WHERE|GROUP BY|ORDER BY|IN|AND|BETWEEN|SUM|COUNT|DISTINCT|DESC|AS)\b|(\b\d+(?:\.\d+)?\b)/g;
  const escT = (s) => s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" })[c]);
  const paint = (s) => escT(s).replace(tok, (m, str, kw, num) => (str ? `<span class="str">${str}</span>` : kw ? `<span class="kw">${kw}</span>` : `<span class="num">${num}</span>`));
  return lines.map((l) => {
    const i = l.indexOf("--");
    return i === -1 ? paint(l) : paint(l.slice(0, i)) + `<span class="cmt">${escT(l.slice(i))}</span>`;
  }).join("\n");
}

function renderMsg(m, animate) {
  const el = document.createElement("div");
  if (m.role === "me") { el.className = "msg me"; el.innerHTML = `<div class="bub">${esc(m.text)}</div>`; return el; }
  el.className = "msg ai";
  el.innerHTML = `<div class="orb"></div><div class="bub"><div class="ans"></div><div class="extra"></div></div>`;
  const ans = $(".ans", el), extra = $(".extra", el);
  const finish = () => {
    ans.innerHTML = md(m.answer);
    if (m.welcome) { extra.innerHTML = `<div class="followups">${(S.info?.suggestions || []).slice(0, 3).map((s) => `<button class="chip" data-f="${esc(s)}">${esc(s)}</button>`).join("")}</div>`; }
    else {
      extra.innerHTML = `${m.calculations?.length ? `<details class="trace"${animate ? "" : ""}><summary>Reasoning trace · ${m.calculations.length} steps</summary><pre>${highlightCalc(m.calculations)}</pre></details>` : ""}
        ${m.chart ? `<div class="msg-chart"><canvas></canvas></div>` : ""}
        <div class="msg-meta"><span class="ai-badge">${icon("cpu")} ${esc(m.engine || "aether-engine")}</span>${(m.sources || []).map((s) => `<span>${esc(s)}</span>`).join(" · ")}</div>
        ${m.followups?.length ? `<div class="followups">${m.followups.map((f) => `<button class="chip" data-f="${esc(f)}">${esc(f)} →</button>`).join("")}</div>` : ""}`;
      if (m.chart) requestAnimationFrame(() => msgChart($("canvas", extra), m.chart));
    }
    $$("[data-f]", extra).forEach((b) => (b.onclick = () => ask(b.dataset.f)));
  };
  if (animate) {
    const words = m.answer.replace(/\*\*/g, "").split(" "), step = Math.max(1, Math.ceil(words.length / 55)); let i = 0;
    (function tick() { i += step; ans.textContent = words.slice(0, i).join(" "); const log = $("#log"); if (log) log.scrollTop = log.scrollHeight; if (i < words.length) setTimeout(tick, 16); else { finish(); const l = $("#log"); if (l) l.scrollTop = l.scrollHeight; } })();
  } else finish();
  return el;
}

function msgChart(cv, c) {
  const P = PALETTE(), base = chartBase(); base.scales.x.ticks.font = { size: 10 }; base.scales.y.ticks.font = { size: 10 };
  const labels = c.labels.map(ml);
  const ds = c.type === "line"
    ? { label: "Revenue", data: c.data, borderColor: "#a78bfa", backgroundColor: fillGrad("#a78bfa", .25), fill: true, tension: .35, pointRadius: 2.5, borderWidth: 2,
        segment: { borderColor: (s) => (c.split && s.p0DataIndex >= c.split - 1 ? "#22d3ee" : undefined), borderDash: (s) => (c.split && s.p0DataIndex >= c.split - 1 ? [5, 4] : undefined) } }
    : { label: "Revenue", data: c.data, borderRadius: 6, backgroundColor: c.data.map((_, i) => (c.highlight === i ? "#fb7185" : c.highlight != null ? rgba("#a78bfa", .45) : P[i % 6])) };
  mkChart("msg" + Math.random(), cv, { type: c.type, data: { labels, datasets: [ds] }, options: base });
}

async function ask(q) {
  const log = $("#log"); if (!log) return askFromAnywhere(q);
  // prior turns (plain text) so follow-ups like "and in October?" keep their context
  const history = S.chat.filter((m) => !m.welcome && (m.text || m.answer)).slice(-10).map((m) => ({ role: m.role === "me" ? "user" : "assistant", content: (m.text || m.answer).slice(0, 2000) }));
  const me = { role: "me", text: q }; S.chat.push(me); log.append(renderMsg(me));
  const wait = document.createElement("div"); wait.className = "msg ai"; wait.innerHTML = `<div class="orb think"></div><div class="bub"><span class="typing"><i></i><i></i><i></i></span></div>`;
  log.append(wait); log.scrollTop = log.scrollHeight; $("#orb")?.classList.add("think");
  try {
    const [r] = await Promise.all([api("ask", { method: "POST", body: { question: q, history } }), sleep(550)]);
    const m = { role: "ai", ...r }; S.chat.push(m); wait.replaceWith(renderMsg(m, true));
  } catch (e) { wait.querySelector(".bub").innerHTML = `<span class="dn">${esc(e.message)}</span>`; }
  $("#orb")?.classList.remove("think");
}

// =========================================================================
//  VIEW: FORECAST LAB
// =========================================================================
VIEWS.forecast = async (v) => {
  const D = await overviewData();
  if (!D.months.length) return emptyData(v);
  if (D.months.length < 12) { v.innerHTML = `<div class="card empty"><div class="eic">${icon("lab")}</div><h3>Need 12+ months</h3><p>The forecast lab backtests each model on rolling windows, which requires at least a year of history.</p></div>`; return; }
  if (!S.lab || S.lab.horizon !== S.h) S.lab = await api("forecast/lab?h=" + S.h);
  const L = S.lab; S.labModel = S.labModel && L.models[S.labModel] ? S.labModel : L.best;
  const maxM = Math.max(...L.ranking.map((k) => L.models[k].mape));
  v.innerHTML = `<div class="vw">
    <div class="card"><div class="hd"><div><h3>${icon("lab")} Model leaderboard</h3><p>${esc(L.method)} Lower is better. Click a model to inspect it.</p></div><span class="tag ok">${icon("check")} winner: ${esc(L.models[L.best].label)}</span></div>
      <div class="tbl-wrap"><table class="tbl"><thead><tr><th>#</th><th>Model</th><th>MAPE</th><th></th><th class="num">RMSE</th><th class="num">Bias</th></tr></thead><tbody>
      ${L.ranking.map((k, i) => { const m = L.models[k]; return `<tr class="tr-sel ${k === S.labModel ? "on" : ""}" data-m="${k}"><td><span class="rank ${i === 0 ? "first" : ""}">${i + 1}</span></td><td><b>${esc(m.label)}</b></td>
        <td class="mono">${m.mape}%</td><td style="width:34%"><div class="meter"><i data-w="${(m.mape / maxM) * 100}%"></i></div></td><td class="num">${fmt.usd(m.rmse)}</td><td class="num ${m.bias < 0 ? "dn" : "up"}">${fmt.usd(m.bias)}</td></tr>`; }).join("")}
      </tbody></table></div></div>
    <div class="g2">
      <div class="card"><div class="hd"><div><h3 id="fl-title"></h3><p>History, forward forecast and 90% prediction band (widens with √horizon)</p></div>
        <div class="seg sm" id="hz">${[3, 6, 12].map((h) => `<button data-h="${h}" class="${S.h === h ? "on" : ""}">${h} mo</button>`).join("")}</div></div>
        <div class="chart-box"><canvas id="c-fl"></canvas></div></div>
      <div class="card"><div class="hd"><div><h3>Selected model</h3><p>Out-of-sample performance</p></div></div>
        <div id="fl-stats"></div>
        <div class="notice" style="margin-top:16px">${icon("lab")}<span>Metrics come from <b>${L.folds} rolling folds</b>: each model is refit without the months it predicts, so the score reflects real forecasting skill — not in-sample fit.</span></div></div>
    </div>
    <div class="card"><div class="hd"><div><h3>Backtest: last ${L.holdout_size} months held out</h3><p>Every model trained without these months, then asked to predict them</p></div><div class="legend" id="lg-bt"></div></div><div class="chart-box"><canvas id="c-bt"></canvas></div></div>
  </div>`;
  requestAnimationFrame(() => $$(".meter i", v).forEach((i) => (i.style.width = i.dataset.w)));
  $$("#hz button", v).forEach((b) => (b.onclick = () => { S.h = +b.dataset.h; route(); }));
  $$("tr[data-m]", v).forEach((tr) => (tr.onclick = () => { S.labModel = tr.dataset.m; $$("tr[data-m]", v).forEach((x) => x.classList.toggle("on", x === tr)); drawLab(); }));
  drawLab();
};

function drawLab() {
  const L = S.lab, k = S.labModel, M = L.models[k], P = PALETTE();
  $("#fl-title").textContent = `${M.label} · next ${L.horizon} months`;
  $("#fl-stats").innerHTML = `<div class="big-num">${M.mape}<span class="mu" style="font-size:22px">% MAPE</span></div>
    <div class="list" style="margin-top:12px"><div class="li"><span>RMSE</span><b class="mono">${fmt.usd(M.rmse)}</b></div><div class="li"><span>Bias (avg error)</span><b class="mono ${M.bias < 0 ? "dn" : "up"}">${fmt.usd(M.bias)}</b></div>
    <div class="li"><span>Total forecast · ${L.horizon} mo</span><b class="mono">${fmt.k(sum(M.forecast))}</b></div><div class="li"><span>Rank</span><b class="mono">${L.ranking.indexOf(k) + 1} / ${L.ranking.length}</b></div></div>`;
  const hist = L.revenue.slice(-18), hm = L.months.slice(-18), n = hist.length, pad = (a) => [...Array(n - 1).fill(null), hist[n - 1], ...a];
  mkChart("fl", $("#c-fl"), { type: "line", data: { labels: [...hm, ...L.future].map(ml), datasets: [
    { label: "Actual", data: [...hist, ...L.future.map(() => null)], borderColor: "#a78bfa", backgroundColor: fillGrad("#a78bfa", .3), fill: true, tension: .35, pointRadius: 0, borderWidth: 2.4 },
    { label: "Forecast", data: pad(M.forecast), borderColor: "#22d3ee", borderDash: [6, 5], borderWidth: 2.2, tension: .3, pointRadius: (c) => (c.dataIndex >= n ? 3 : 0), pointBackgroundColor: "#22d3ee" },
    { label: "Upper (90%)", data: pad(M.upper), borderColor: "transparent", backgroundColor: "rgba(34,211,238,.13)", fill: "+1", pointRadius: 0, tension: .3 },
    { label: "Lower (90%)", data: pad(M.lower), borderColor: "transparent", pointRadius: 0, tension: .3 },
  ] }, options: chartBase() });
  const hold = L.holdout_size, win = L.months.slice(-(hold + 8)), act = L.revenue.slice(-(hold + 8)), off = win.length - hold;
  const order = Object.keys(L.models), cols = { ols_seasonal: "#a78bfa", holt: "#f472b6", seasonal_naive: "#fbbf24", naive: "#60a5fa" };
  $("#lg-bt").innerHTML = `<span><i style="background:${css("--tx")}"></i>Actual</span>` + order.map((m) => `<span style="opacity:${m === k ? 1 : .55}"><i style="background:${cols[m]}"></i>${esc(L.models[m].label)}</span>`).join("");
  mkChart("bt", $("#c-bt"), { type: "line", data: { labels: win.map(ml), datasets: [
    { label: "Actual", data: act, borderColor: css("--tx"), borderWidth: 2.4, tension: .3, pointRadius: 2 },
    ...order.map((m) => ({ label: L.models[m].label, data: [...Array(off - 1).fill(null), act[off - 1], ...L.models[m].holdout], borderColor: m === k ? cols[m] : rgba(cols[m], .35), borderWidth: m === k ? 2.6 : 1.4, borderDash: m === k ? [] : [4, 4], tension: .3, pointRadius: 0 })),
  ] }, options: chartBase() });
}

// =========================================================================
//  VIEW: SCENARIOS
// =========================================================================
const SC = { price: 0, marketing: 0, churn: 0, elasticity: -1.2, horizon: 6 };
const PRESETS = { "Premium pricing": { price: 10, marketing: 0, churn: 5 }, "Growth push": { price: -5, marketing: 60, churn: 0 }, "Retention focus": { price: 0, marketing: 10, churn: -20 }, "Downturn": { price: -10, marketing: -40, churn: 15 } };
VIEWS.scenarios = async (v) => {
  const D = await overviewData();
  if (!D.months.length) return emptyData(v);
  const sl = (id, label, min, max, step, unit, hint) => `<div class="slider"><div class="sl-top"><span>${label}</span><b id="o-${id}"></b></div>
    <input type="range" id="s-${id}" min="${min}" max="${max}" step="${step}" value="${SC[id]}" aria-label="${label}" /><small>${hint}</small></div>`;
  v.innerHTML = `<div class="vw"><div class="g2" style="grid-template-columns:minmax(0,1fr) minmax(0,1.6fr)">
    <div class="card"><div class="hd"><div><h3>${icon("sliders")} Levers</h3><p>The forecast recomputes as you move them</p></div><button class="btn ghost sm" id="sc-reset">Reset</button></div>
      <div class="row" style="margin-bottom:6px">${Object.keys(PRESETS).map((p) => `<button class="chip" data-p="${p}">${p}</button>`).join("")}</div>
      ${sl("price", "Price change", -20, 20, 1, "%", "Higher price lifts margin per unit but reduces volume")}
      ${sl("marketing", "Marketing spend", -50, 100, 5, "%", "Each +1% spend adds ~0.25% volume")}
      ${sl("churn", "Churn change", -30, 30, 1, "%", "Each +1% churn removes ~0.6% volume")}
      ${sl("elasticity", "Price elasticity", -2.5, -0.2, 0.1, "", "How sensitive demand is to price (−1.2 is typical retail)")}
      <div class="slider"><div class="sl-top"><span>Horizon</span></div><div class="seg sm" id="sc-h">${[3, 6, 12].map((h) => `<button data-h="${h}" class="${SC.horizon === h ? "on" : ""}">${h} months</button>`).join("")}</div></div>
    </div>
    <div style="display:grid;gap:18px">
      <div class="card"><div class="hd"><div><h3>Scenario impact</h3><p id="sc-asm"></p></div></div>
        <div class="row" style="gap:28px;align-items:flex-end"><div><small class="mu">Revenue vs baseline</small><div class="big-num" id="sc-delta">—</div></div><div><small class="mu">Change</small><div class="big-num" style="font-size:30px" id="sc-pct">—</div></div></div>
        <div class="chart-box sm" style="margin-top:14px"><canvas id="c-sc"></canvas></div></div>
      <div class="card"><div class="hd"><div><h3>Revenue bridge</h3><p>How each lever moves total revenue from baseline to scenario</p></div></div><div class="chart-box sm"><canvas id="c-br"></canvas></div></div>
    </div></div></div>`;
  const run = debounce(simulate, 110);
  ["price", "marketing", "churn", "elasticity"].forEach((id) => { const el = $("#s-" + id); el.oninput = () => { SC[id] = +el.value; paintSliders(); run(); }; });
  $$("#sc-h button", v).forEach((b) => (b.onclick = () => { SC.horizon = +b.dataset.h; $$("#sc-h button").forEach((x) => x.classList.toggle("on", x === b)); simulate(); }));
  $$("[data-p]", v).forEach((b) => (b.onclick = () => { Object.assign(SC, PRESETS[b.dataset.p]); ["price", "marketing", "churn"].forEach((id) => ($("#s-" + id).value = SC[id])); paintSliders(); simulate(); toast(`Preset applied: ${b.dataset.p}`, "info"); }));
  $("#sc-reset").onclick = () => { Object.assign(SC, { price: 0, marketing: 0, churn: 0, elasticity: -1.2 }); ["price", "marketing", "churn", "elasticity"].forEach((id) => ($("#s-" + id).value = SC[id])); paintSliders(); simulate(); };
  paintSliders(); simulate();
};
function paintSliders() {
  ["price", "marketing", "churn", "elasticity"].forEach((id) => {
    const el = $("#s-" + id); if (!el) return;
    el.style.setProperty("--fill", ((el.value - el.min) / (el.max - el.min)) * 100 + "%");
    $("#o-" + id).textContent = id === "elasticity" ? (+el.value).toFixed(1) : (el.value > 0 ? "+" : "") + el.value + "%";
  });
}
let lastDelta = 0;
async function simulate() {
  const W = await api("whatif", { method: "POST", body: SC });
  if (!$("#c-sc")) return;
  $("#sc-asm").textContent = W.assumptions;
  const del = $("#sc-delta"), from = lastDelta; lastDelta = W.delta;
  const t0 = performance.now(); (function s(now) { const k = Math.min(1, (now - t0) / 500), x = from + (W.delta - from) * (1 - Math.pow(1 - k, 3)); del.textContent = (x >= 0 ? "+" : "") + fmt.k(x); del.className = "big-num " + (x >= 0 ? "up" : "dn"); if (k < 1) requestAnimationFrame(s); })(t0);
  $("#sc-pct").textContent = fmt.pct(W.delta_pct, 2); $("#sc-pct").className = "big-num " + (W.delta_pct >= 0 ? "up" : "dn");
  const base = chartBase(); base.animation = { duration: 400 };
  if (S.charts.sc) { const c = S.charts.sc; c.data.labels = W.months.map(ml); c.data.datasets[0].data = W.base; c.data.datasets[1].data = W.scenario; c.update(); }
  else mkChart("sc", $("#c-sc"), { type: "bar", data: { labels: W.months.map(ml), datasets: [
    { label: "Baseline", data: W.base, backgroundColor: rgba("#a78bfa", .3), borderColor: "#a78bfa", borderWidth: 1, borderRadius: 6, barPercentage: .7 },
    { label: "Scenario", data: W.scenario, backgroundColor: "#22d3ee", borderRadius: 6, barPercentage: .7 }] }, options: base });
  const tb = sum(W.base); let run = tb; const steps = [["Baseline", 0, tb]];
  W.bridge.forEach((b) => { steps.push([b.label, run, run + b.value]); run += b.value; }); steps.push(["Scenario", 0, run]);
  const b2 = chartBase(); b2.animation = { duration: 400 }; b2.scales.y.beginAtZero = false; b2.scales.y.min = Math.min(...steps.flatMap((s) => s.slice(1).filter((x, i) => i || s[0] !== "Baseline" && s[0] !== "Scenario"))) * 0.97;
  b2.plugins.tooltip.callbacks.label = (c) => { const s = steps[c.dataIndex]; return c.dataIndex === 0 || c.dataIndex === steps.length - 1 ? ` ${fmt.usd(s[2])}` : ` ${s[2] - s[1] >= 0 ? "+" : ""}${fmt.usd(s[2] - s[1])}`; };
  const colors = steps.map((s, i) => (i === 0 || i === steps.length - 1 ? "#a78bfa" : s[2] >= s[1] ? "#34d399" : "#fb7185"));
  const data = steps.map((s, i) => (i === 0 || i === steps.length - 1 ? [b2.scales.y.min, s[2]] : [s[1], s[2]]));
  if (S.charts.br) { const c = S.charts.br; c.options.scales.y.min = b2.scales.y.min; c.data.datasets[0].data = data; c.data.datasets[0].backgroundColor = colors; c.options.plugins.tooltip.callbacks.label = b2.plugins.tooltip.callbacks.label; c.update(); }
  else mkChart("br", $("#c-br"), { type: "bar", data: { labels: steps.map((s) => s[0]), datasets: [{ label: "Revenue", data, backgroundColor: colors, borderRadius: 6, borderSkipped: false, barPercentage: .6 }] }, options: b2 });
}

// =========================================================================
//  VIEW: CHURN
// =========================================================================
VIEWS.churn = async (v) => {
  const c = await api("churn"), cm = c.confusion;
  if (!c.available) {
    v.innerHTML = `<div class="card empty" style="padding:70px 20px"><div class="eic">${icon("users")}</div><h3>Train the churn model on your customers</h3><p>${esc(c.reason)}</p>
      <div class="row" style="justify-content:center;margin-top:8px">${can("write") ? `<button class="btn primary" id="go-cust">${icon("upload")} Import customer data</button>` : ""}
      <button class="btn ghost" id="cust-tpl">${icon("download")} Download template</button></div></div>`;
    $("#go-cust", v)?.addEventListener("click", () => { DATA_KIND = "customers"; location.hash = "#/data"; });
    $("#cust-tpl", v).onclick = async () => download("aether_customers_template.csv", await (await fetch("/api/templates/customers")).text());
    return;
  }
  const metrics = [["ROC AUC", c.auc.toFixed(3), "Ranking quality, 0.5 = random"], ["Accuracy", c.accuracy + "%", "Correct predictions"], ["Precision", c.precision + "%", "Flagged that truly churn"], ["Recall", c.recall + "%", "Churners we catch"], ["F1 score", c.f1 + "%", "Precision/recall balance"]];
  v.innerHTML = `<div class="vw">
    <div class="notice">${icon("cpu")}<span>Trained on <b>${esc(c.source)}</b>: logistic regression fitted by gradient descent on ${c.train_size} customers and evaluated on a <b>${c.test_size}-customer holdout</b> never seen during training. Base churn rate ${c.base_rate}%.${c.source === "your customers" ? ` Risk scores cover your ${fmt.num(c.scored)} active customers.` : ""}</span></div>
    <div class="metrics">${metrics.map((m) => `<div class="card metric"><small><span>${m[0]}</span></small><b>${m[1]}</b><small>${m[2]}</small></div>`).join("")}</div>
    <div class="g3">
      <div class="card"><div class="hd"><div><h3>ROC curve</h3><p>True vs false positive rate across thresholds</p></div></div><div class="chart-box xs" style="height:220px"><canvas id="c-roc"></canvas></div></div>
      <div class="card"><div class="hd"><div><h3>Confusion matrix</h3><p>Holdout set · threshold 0.5</p></div></div>
        <div class="cm"><span></span><span class="ax">Pred. churn</span><span class="ax">Pred. stay</span>
          <span class="ax" style="writing-mode:vertical-rl;transform:rotate(180deg)">Churned</span><div class="cell good"><b>${cm.tp}</b><small>true pos.</small></div><div class="cell bad"><b>${cm.fn}</b><small>false neg.</small></div>
          <span class="ax" style="writing-mode:vertical-rl;transform:rotate(180deg)">Stayed</span><div class="cell bad"><b>${cm.fp}</b><small>false pos.</small></div><div class="cell good"><b>${cm.tn}</b><small>true neg.</small></div></div></div>
      <div class="card"><div class="hd"><div><h3>What drives churn</h3><p>Standardized model coefficients</p></div></div><div class="chart-box xs" style="height:220px"><canvas id="c-w"></canvas></div></div>
    </div>
    <div class="g2 eq">
      <div class="card"><div class="hd"><div><h3>Risk segments</h3><p>All ${c.train_size + c.test_size} customers by predicted probability</p></div></div><div class="chart-box xs"><canvas id="c-seg"></canvas></div></div>
      <div class="card"><div class="hd"><div><h3>Training loss</h3><p>Log-loss every 30 epochs — gradient descent converging smoothly</p></div></div><div class="spark" style="height:150px;margin:0">${spark(c.loss_curve, "#a78bfa")}</div></div>
    </div>
    <div class="card"><div class="hd"><div><h3>${icon("alert")} Customers at risk</h3><p>Highest predicted churn probability, with the feature pushing them out and a recommended action</p></div><button class="btn ghost sm" id="risk-csv">${icon("download")} CSV</button></div>
        <div class="tbl-wrap"><table class="tbl"><thead><tr><th>Customer</th><th>Risk</th><th class="num">Tenure</th><th class="num">Orders/mo</th><th class="num">Tickets</th><th class="num">Idle</th><th>Next best action</th></tr></thead><tbody>
        ${c.at_risk.map((r) => `<tr><td><b class="mono">${r.id}</b><br><span class="tag warn" style="margin-top:4px">${esc(r.reason)}</span></td><td style="min-width:120px"><div class="meter risk"><i data-w="${r.prob}%"></i></div><small class="mono">${r.prob}%</small></td>
          <td class="num">${r.tenure}m</td><td class="num">${r.orders}</td><td class="num">${r.tickets}</td><td class="num">${r.idle_days}d</td><td style="min-width:200px">${esc(r.action)}</td></tr>`).join("")}</tbody></table></div></div>
    </div>`;
  requestAnimationFrame(() => $$(".meter i", v).forEach((i) => (i.style.width = i.dataset.w)));
  const base = chartBase(); base.scales.y.ticks.callback = (x) => x; base.scales.x = { ...base.scales.x, type: "linear", min: 0, max: 1, title: { display: true, text: "False positive rate", font: { size: 10.5 } } };
  base.scales.y = { ...base.scales.y, min: 0, max: 1, title: { display: true, text: "True positive rate", font: { size: 10.5 } } };
  base.plugins.tooltip.callbacks.label = (x) => ` FPR ${x.raw.x} · TPR ${x.raw.y}`; base.interaction = { mode: "nearest", intersect: false };
  mkChart("roc", $("#c-roc"), { type: "line", data: { datasets: [
    { label: "ROC", data: c.roc.map(([x, y]) => ({ x, y })), borderColor: "#a78bfa", backgroundColor: fillGrad("#a78bfa", .3), fill: true, tension: .2, pointRadius: 0, borderWidth: 2.4 },
    { label: "Random", data: [{ x: 0, y: 0 }, { x: 1, y: 1 }], borderColor: css("--line2"), borderDash: [4, 4], pointRadius: 0, borderWidth: 1.2, hideTip: true }] }, options: base });
  const bw = chartBase(); bw.indexAxis = "y"; bw.scales.x.ticks = { callback: (x) => x }; bw.scales.y.ticks = { font: { size: 11 } }; bw.scales.x.grid = { color: css("--line") }; bw.scales.y.grid = { display: false };
  bw.plugins.tooltip.callbacks.label = (x) => ` weight ${x.raw > 0 ? "+" : ""}${x.raw} → ${x.raw > 0 ? "raises" : "lowers"} churn risk`;
  mkChart("w", $("#c-w"), { type: "bar", data: { labels: c.features, datasets: [{ label: "Weight", data: c.weights, backgroundColor: c.weights.map((w) => (w > 0 ? "#fb7185" : "#34d399")), borderRadius: 6, barPercentage: .6 }] }, options: bw });
  const bs = chartBase(); bs.scales.y.ticks.callback = (x) => x; bs.plugins.tooltip.callbacks.label = (x) => ` ${x.raw} customers`;
  mkChart("seg", $("#c-seg"), { type: "bar", data: { labels: c.segments.map((s) => s.label), datasets: [{ label: "Customers", data: c.segments.map((s) => s.count), backgroundColor: ["#34d399", "#fbbf24", "#fb923c", "#fb7185"], borderRadius: 8, barPercentage: .6 }] }, options: bs });
  $("#risk-csv").onclick = () => download("aether_churn_risk.csv", "customer,probability,tenure,orders,tickets,idle_days,driver,action\n" + c.at_risk.map((r) => [r.id, r.prob, r.tenure, r.orders, r.tickets, r.idle_days, r.reason, `"${r.action}"`].join(",")).join("\n"));
};

// =========================================================================
//  VIEW: DATA
// =========================================================================
const KINDS = {
  sales: { title: "Sales data", api: "upload", needs: "a month/date column and a revenue/sales column", optional: "region, product, customers",
    eg: "Fecha, Ciudad, Producto, Ventas · or · month, region, product, revenue" },
  customers: { title: "Customer data", api: "upload/customers", needs: "tenure (months), orders per month, support tickets, days since last order", optional: "customer id, churned (yes/no)",
    eg: "customer_id, tenure_months, orders_per_month, support_tickets, days_since_last_order, churned" },
};
let DATA_KIND = "sales";

VIEWS.data = async (v) => {
  const ds = await api("dataset"), w = can("write"), K = KINDS[DATA_KIND], sales = ds.sales;
  v.innerHTML = `<div class="vw">
    <div class="seg sm" id="kind" style="justify-self:start">${Object.entries(KINDS).map(([k, x]) => `<button data-k="${k}" class="${k === DATA_KIND ? "on" : ""}">${x.title}</button>`).join("")}</div>
    <div class="g2">
    <div class="card"><div class="hd"><div><h3>${icon("upload")} Import ${K.title.toLowerCase()}</h3><p>CSV or Excel (.xlsx), English or Spanish headers. Needs ${K.needs}; optional: ${K.optional}.</p></div></div>
      ${ds.demo_org ? `<div class="notice" style="margin-bottom:14px">${icon("shield")}<span>This is the shared public demo, so imports are previewed but not saved. <a href="#" id="go-reg" style="color:var(--violet2);font-weight:600">Create your own workspace</a> to use your data.</span></div>` : ""}
      ${w ? `<label class="drop" id="dz"><div class="eic">${icon("upload")}</div><b>Drop your file here</b><span class="mu">or click to browse · .csv, .xlsx · up to 8 MB</span><span class="mu mono" style="font-size:11.5px">${esc(K.eg)}</span><input type="file" id="file" accept=".csv,.txt,.xlsx,.xlsm,text/csv" hidden /></label>`
        : `<div class="notice">${icon("shield")}<span>Your role is <b>viewer</b>: you can explore and export data, but only admins and analysts can import. RBAC is enforced by the API.</span></div>`}
      <div id="up-res" style="margin-top:16px"></div>
      <div class="hd" style="margin:22px 0 10px"><div><h3>What happens to your file</h3></div></div>
      <ol class="steps"><li>Columns are recognized by name (e.g. <span class="mono">Fecha → month</span>, <span class="mono">Ventas → revenue</span>), and the delimiter is detected.</li>
        <li>Dates (2025-03, 14/03/2025, mar-25…) and numbers ($1,234.50, 1.234,50…) are normalized.</li>
        <li>Duplicates and invalid rows are removed; daily rows are summed into months.</li><li>You review a preview, then confirm. Nothing is saved before that.</li></ol>
    </div>
    <div style="display:grid;gap:18px;align-content:start">
      <div class="card"><div class="hd"><div><h3>${icon("db")} Your data</h3></div><span class="tag ${ds.data_mode === "real" ? "ok" : ds.data_mode === "demo" ? "vi" : ""}">${ds.data_mode === "real" ? "imported" : ds.data_mode === "demo" ? "demo" : "empty"}</span></div>
        <div class="list"><div class="li"><span>Sales rows</span><b class="mono">${sales ? fmt.num(sales.rows) : "—"}</b></div>
          <div class="li"><span>Months</span><b class="mono">${sales ? `${sales.months} <span class="mu">(${ml(sales.range[0])} → ${ml(sales.range[1])})</span>` : "—"}</b></div>
          <div class="li"><span>Regions</span><b>${sales ? sales.regions.slice(0, 6).map(esc).join(", ") + (sales.regions.length > 6 ? "…" : "") : "—"}</b></div>
          <div class="li"><span>Products</span><b>${sales ? sales.products.slice(0, 6).map(esc).join(", ") + (sales.products.length > 6 ? "…" : "") : "—"}</b></div>
          <div class="li"><span>Customers (churn model)</span><b class="mono">${ds.customers ? fmt.num(ds.customers) : ds.data_mode === "demo" ? "demo set" : "—"}</b></div></div></div>
      <div class="card"><div class="hd"><div><h3>Actions</h3></div></div><div style="display:grid;gap:8px">
        <button class="btn ghost block" id="tpl">${icon("download")} Download ${K.title.toLowerCase()} template</button>
        <button class="btn ghost block" id="exp" ${sales ? "" : "disabled"}>${icon("download")} Export sales (CSV)</button>
        ${can("admin") && !ds.demo_org ? `<button class="btn ghost block" id="demo-btn">${icon("refresh")} Replace with demo dataset</button>` : ""}
      </div></div>
    </div></div></div>`;
  $$("#kind button", v).forEach((b) => (b.onclick = () => { DATA_KIND = b.dataset.k; route(); }));
  $("#go-reg", v)?.addEventListener("click", (e) => { e.preventDefault(); logout(); openAuth("reg"); });
  $("#exp", v).onclick = async () => { const r = await api("export"); download("aether_sales.csv", r.content); toast("Sales exported"); };
  $("#tpl", v).onclick = async () => { const r = await fetch("/api/templates/" + DATA_KIND); download(`aether_${DATA_KIND}_template.csv`, await r.text()); };
  $("#demo-btn", v)?.addEventListener("click", () => confirm("Replace this organization's sales with the demo dataset?") && loadDemo());
  if (!w) return;
  const dz = $("#dz", v);
  $("#file", v).onchange = (e) => e.target.files[0] && preview(e.target.files[0], ds.demo_org);
  dz.ondragover = (e) => { e.preventDefault(); dz.classList.add("h"); }; dz.ondragleave = () => dz.classList.remove("h");
  dz.ondrop = (e) => { e.preventDefault(); dz.classList.remove("h"); e.dataTransfer.files[0] && preview(e.dataTransfer.files[0], ds.demo_org); };
};

async function filePayload(file) {
  if (/\.xlsx?m?$/i.test(file.name)) {
    const bytes = new Uint8Array(await file.arrayBuffer()); let bin = "";
    for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
    return { content_b64: btoa(bin), filename: file.name };
  }
  return { content: await file.text(), filename: file.name };
}

const errBox = (msg) => `<div class="notice" style="border-color:rgba(251,113,133,.35);background:rgba(251,113,133,.06)">${icon("alert")}<span>${esc(msg)}</span></div>`;

async function preview(file, demoOrg) {
  const out = $("#up-res"), kind = DATA_KIND, K = KINDS[kind];
  if (file.size > 8e6) return toast("File is larger than 8 MB", "err");
  out.innerHTML = `<div class="skel" style="height:120px"></div>`;
  let body;
  try { body = await filePayload(file); const r = await api(K.api, { method: "POST", body: { ...body, dry_run: true } }); out.innerHTML = previewHtml(file, r, kind, demoOrg); }
  catch (e) { out.innerHTML = errBox(e.message); return; }
  paintIcons(out);
  $("#up-cancel", out).onclick = () => { out.innerHTML = ""; $("#file").value = ""; };
  $("#up-go", out)?.addEventListener("click", async () => {
    const btn = $("#up-go", out); btn.disabled = true; btn.textContent = "Importing…";
    try {
      await api(K.api, { method: "POST", body });
      S.D = null; S.lab = null; toast(kind === "sales" ? "Sales imported — every dashboard has been recomputed" : "Customers imported — the churn model was retrained on them");
      refreshBell(); location.hash = kind === "sales" ? "#/overview" : "#/churn";
    } catch (e) { out.insertAdjacentHTML("beforeend", errBox(e.message)); btn.disabled = false; btn.textContent = "Import"; }
  });
}

function previewHtml(file, r, kind, demoOrg) {
  const cols = Object.entries(r.columns).map(([f, c]) => `<span class="tag vi">${esc(c)} → ${f}</span>`).join(" ");
  const stats = kind === "sales"
    ? [["Rows read", fmt.num(r.rows)], ["Kept", fmt.num(r.kept)], ["Duplicates · invalid", `${r.duplicates} · ${r.invalid}`], ["Months", `${r.months} (${ml(r.range[0])} → ${ml(r.range[1])})`],
       ["Regions", r.regions.length], ["Products", r.products.length]]
    : [["Customers", fmt.num(r.kept)], ["Invalid rows", r.invalid], ["With known outcome", fmt.num(r.labeled)], ["Churn rate", r.churn_rate != null ? r.churn_rate + "%" : "—"]];
  const head = kind === "sales" ? ["month", "region", "product", "revenue", "customers"] : ["ext_id", "tenure", "orders", "tickets", "idle", "churned"];
  const notes = [r.estimated_customers ? "No customers column: customer counts are estimated from revenue." : "",
    r.invalid_samples?.length ? `Skipped rows look like: ${r.invalid_samples.map((s) => s.join(" | ")).slice(0, 2).join(" ; ")}` : "",
    kind === "customers" && !r.labeled ? "No churned column: the model can't be trained without known outcomes." : ""].filter(Boolean);
  return `<div class="card" style="padding:18px"><div class="hd" style="margin-bottom:10px"><div><h3>${icon("check")} Preview · ${esc(file.name)}</h3><p>${esc(r.format)}${r.delimiter ? ` · delimiter “${esc(r.delimiter)}”` : ""}${r.date_order ? ` · dates ${r.date_order === "dmy" ? "day/month" : "month/day"}` : ""} · quality ${r.score}/100</p></div></div>
    <div class="row" style="margin-bottom:12px">${cols}</div>
    <div class="list">${stats.map(([a, b]) => `<div class="li"><span>${a}</span><b class="mono">${esc(String(b))}</b></div>`).join("")}</div>
    ${notes.map((n) => `<p class="mu" style="font-size:12.5px;margin:10px 0 0">${esc(n)}</p>`).join("")}
    <div class="tbl-wrap" style="margin-top:12px"><table class="tbl"><thead><tr>${head.map((h) => `<th>${h}</th>`).join("")}</tr></thead><tbody>
      ${r.preview.map((row) => `<tr>${head.map((h) => `<td class="${typeof row[h] === "number" ? "num" : ""}">${esc(row[h] ?? "—")}</td>`).join("")}</tr>`).join("")}</tbody></table></div>
    <div class="row" style="justify-content:flex-end;margin-top:14px"><button class="btn ghost sm" id="up-cancel">Cancel</button>
      ${demoOrg ? `<span class="mu" style="font-size:12.5px">Saving is disabled in the public demo</span>` : `<button class="btn primary sm" id="up-go">Import ${r.kept ?? r.rows} rows</button>`}</div></div>`;
}

function download(name, text) {
  const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob(["﻿" + text], { type: "text/csv;charset=utf-8" })); a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

// =========================================================================
//  VIEW: ALERTS
// =========================================================================
const METRIC = { mom_pct: ["Revenue MoM", "%"], last_month: ["Monthly revenue", "$"], customers: ["Active customers", ""], ytd_growth_pct: ["12-month growth", "%"] };
const fmtMetric = (m, x) => (x == null ? "no data" : METRIC[m][1] === "%" ? fmt.pct(x) : METRIC[m][1] === "$" ? fmt.usd(x) : fmt.num(x));
const TEMPLATES = [["Revenue drop", "mom_pct", "<", -10], ["Growth slowdown", "ytd_growth_pct", "<", 10], ["Customer floor", "customers", "<", 3000], ["Record month", "last_month", ">", 300000]];
VIEWS.alerts = async (v) => {
  const list = await api("alerts"); S.alerts = list;
  const w = can("write"), firing = list.filter((a) => a.firing).length;
  v.innerHTML = `<div class="vw">
    <div class="metrics" style="grid-template-columns:repeat(3,minmax(0,1fr))"><div class="card metric"><small>Active rules</small><b>${list.length}</b></div><div class="card metric"><small>Firing now</small><b class="${firing ? "dn" : "up"}">${firing}</b></div><div class="card metric"><small>Evaluated</small><b style="font-size:18px;margin-top:10px">on every refresh</b></div></div>
    <div class="card"><div class="hd"><div><h3>${icon("bell")} Alert rules</h3><p>Compared against the latest KPIs of ${esc(S.sess.org)}</p></div></div>
      <div class="list">${list.length ? list.map((a) => `<div class="li"><div style="display:flex;gap:12px;align-items:center"><span class="dot ${a.firing ? "" : "live"}" style="${a.firing ? "background:var(--red);box-shadow:0 0 12px var(--red)" : ""}"></span>
          <div><b>${esc(a.name)}</b><small>${METRIC[a.metric]?.[0] || esc(a.metric)} ${esc(a.op)} ${fmtMetric(a.metric, a.threshold)} · current <span class="mono">${fmtMetric(a.metric, a.value)}</span></small></div></div>
          <div class="row"><span class="tag ${a.value == null ? "" : a.firing ? "bad" : "ok"}">${a.value == null ? "no data" : a.firing ? "firing" : "ok"}</span>${w ? `<button class="icon-btn" data-del="${a.id}" aria-label="Delete alert" title="Delete">${icon("trash")}</button>` : ""}</div></div>`).join("")
        : `<div class="empty" style="padding:30px"><p>No alert rules yet.</p></div>`}</div></div>
    ${w ? `<div class="card"><div class="hd"><div><h3>${icon("plus")} New rule</h3><p>Start from a template or define your own threshold</p></div></div>
      <div class="row" style="margin-bottom:12px">${TEMPLATES.map((t, i) => `<button class="chip" data-t="${i}">${t[0]}</button>`).join("")}</div>
      <form class="form-row" id="al-form"><input id="al-name" placeholder="Rule name" required maxlength="120" />
        <select id="al-metric">${Object.entries(METRIC).map(([k, m]) => `<option value="${k}">${m[0]}</option>`).join("")}</select>
        <select id="al-op"><option>&lt;</option><option>&gt;</option></select><input id="al-th" type="number" step="any" placeholder="Threshold" required />
        <button class="btn primary" type="submit">Create</button></form></div>`
      : `<div class="notice">${icon("shield")}<span>Viewers can see alerts but not change them.</span></div>`}
  </div>`;
  $$("[data-del]", v).forEach((b) => (b.onclick = async () => { await api("alerts/" + b.dataset.del, { method: "DELETE" }).then(() => toast("Alert deleted")).catch((e) => toast(e.message, "err")); route(); refreshBell(); }));
  $$("[data-t]", v).forEach((b) => (b.onclick = () => { const t = TEMPLATES[+b.dataset.t]; $("#al-name").value = t[0]; $("#al-metric").value = t[1]; $("#al-op").value = t[2]; $("#al-th").value = t[3]; }));
  $("#al-form", v)?.addEventListener("submit", async (e) => {
    e.preventDefault();
    try { await api("alerts", { method: "POST", body: { name: $("#al-name").value, metric: $("#al-metric").value, op: $("#al-op").value, threshold: +$("#al-th").value } }); toast("Alert rule created"); route(); refreshBell(); }
    catch (err) { toast(err.message, "err"); }
  });
};

// =========================================================================
//  VIEW: TEAM & AUDIT
// =========================================================================
VIEWS.team = async (v) => {
  if (!can("admin")) {
    v.innerHTML = `<div class="card empty"><div class="eic">${icon("shield")}</div><h3>Admins only</h3><p>Team management and the audit log are restricted to administrators. This is enforced server-side — try calling <span class="mono">GET /api/team</span> with your token and you’ll get a 403.</p></div>`; return;
  }
  const [t, inv] = await Promise.all([api("team"), api("invites")]);
  v.innerHTML = `<div class="vw"><div class="g2">
    <div style="display:grid;gap:18px;align-content:start">
      <div class="card"><div class="hd"><div><h3>${icon("users")} Members</h3><p>${t.members.length} people in ${esc(S.sess.org)}</p></div></div>
        <div class="tbl-wrap"><table class="tbl"><thead><tr><th>Member</th><th>Role</th><th></th></tr></thead><tbody>
        ${t.members.map((m) => `<tr><td><div style="display:flex;gap:10px;align-items:center"><div class="avatar sm">${esc(initials(m.username))}</div><div><b>${esc(m.username)}</b>${m.username === S.sess.user ? ' <span class="tag vi">you</span>' : ""}<br><small class="mu">${esc(m.email)}</small></div></div></td>
          <td><select data-role="${esc(m.username)}" style="width:130px">${["admin", "analyst", "viewer"].map((r) => `<option ${r === m.role ? "selected" : ""}>${r}</option>`).join("")}</select></td>
          <td class="num">${m.username === S.sess.user ? "" : `<button class="icon-btn" data-rm="${esc(m.username)}" title="Remove member" aria-label="Remove member">${icon("trash")}</button>`}</td></tr>`).join("")}</tbody></table></div></div>
      <div class="card"><div class="hd"><div><h3>${icon("mail")} Invite a teammate</h3><p>Creates a single-use link that expires in 7 days</p></div></div>
        <form class="row" id="inv-form" style="flex-wrap:nowrap"><input id="inv-email" type="email" placeholder="name@company.com" required style="flex:2" /><select id="inv-role" style="flex:1"><option>analyst</option><option>viewer</option><option>admin</option></select><button class="btn primary" type="submit">Invite</button></form>
        <div class="list" style="margin-top:10px">${inv.map((i) => `<div class="li"><div><b>${esc(i.email)}</b> <span class="tag vi">${esc(i.role)}</span><small>expires ${esc(i.expires)}</small></div>
          <div class="row"><button class="btn ghost sm" data-copy="${esc(i.token)}">${icon("copy")} Copy link</button><button class="icon-btn" data-revoke="${i.id}" title="Revoke" aria-label="Revoke invite">${icon("trash")}</button></div></div>`).join("") || '<p class="mu" style="margin:8px 0 0">No pending invitations.</p>'}</div></div>
    </div>
    <div class="card"><div class="hd"><div><h3>${icon("shield")} Audit log</h3><p>Last 30 security-relevant events</p></div></div>
      <div class="timeline">${t.audit.map((a) => `<div class="tl"><i></i><div><b>${esc(a.user)}</b> <span class="tx2">${esc(a.action)}</span></div><small>${esc(a.t.slice(5, 16))}</small></div>`).join("")}</div></div>
  </div></div>`;
  $$("[data-role]", v).forEach((s) => (s.onchange = () => api("members/" + encodeURIComponent(s.dataset.role), { method: "PATCH", body: { role: s.value } }).then(() => { toast("Role updated"); route(); }).catch((e) => { toast(e.message, "err"); route(); })));
  $$("[data-rm]", v).forEach((b) => (b.onclick = () => confirm(`Remove ${b.dataset.rm} from the organization?`) && api("members/" + encodeURIComponent(b.dataset.rm), { method: "DELETE" }).then(() => { toast("Member removed"); route(); }).catch((e) => toast(e.message, "err"))));
  $$("[data-copy]", v).forEach((b) => (b.onclick = () => navigator.clipboard.writeText(location.origin + "/?invite=" + b.dataset.copy).then(() => toast("Invite link copied"))));
  $$("[data-revoke]", v).forEach((b) => (b.onclick = () => api("invites/" + b.dataset.revoke, { method: "DELETE" }).then(() => { toast("Invitation revoked"); route(); })));
  $("#inv-form", v).onsubmit = async (e) => {
    e.preventDefault();
    try { const r = await api("invites", { method: "POST", body: { email: $("#inv-email").value, role: $("#inv-role").value } }); await navigator.clipboard?.writeText(location.origin + r.link).catch(() => {}); toast("Invitation created — link copied to clipboard"); route(); }
    catch (err) { toast(err.message, "err"); }
  };
};

// =========================================================================
//  VIEW: EXECUTIVE REPORT
// =========================================================================
VIEWS.report = async (v) => {
  const r = await api("report"), k = r.kpis;
  if (!r.months.length) return emptyData(v);
  v.innerHTML = `<div class="vw">
    <div class="row no-print" style="justify-content:space-between"><p class="mu" style="margin:0">A one-page brief generated from live data. Use <b>Print → Save as PDF</b> to share it.</p>
      <div class="row"><button class="btn ghost sm" id="rp-copy">${icon("copy")} Copy summary</button><button class="btn primary sm" onclick="print()">${icon("print")} Print / PDF</button></div></div>
    <article class="card report">
      <header class="rp-head"><div><span class="brand"><span class="mark"></span>AETHER</span><h2>${esc(r.title.replace("Executive Report — ", ""))}</h2><span class="mu">Executive performance report</span></div>
        <div class="rp-meta">Generated ${esc(r.generated)}<br>Prepared for ${esc(r.author)}<br>Period ${ml(r.months[0])} – ${ml(r.months.at(-1))}</div></header>
      <section class="rp-sec"><h4>Summary</h4><p>${md(r.summary)}</p></section>
      <section class="rp-sec"><h4>Key metrics</h4><div class="rp-kpis">
        <div><small>Revenue, last 12 months</small><b>${fmt.k(sum(r.revenue))}</b>${k.ytd_growth_pct == null ? `<span class="mu mono">${r.months.length} months</span>` : `<span class="${k.ytd_growth_pct >= 0 ? "up" : "dn"} mono">${fmt.pct(k.ytd_growth_pct)} YoY</span>`}</div>
        <div><small>Last month</small><b>${fmt.k(k.last_month)}</b><span class="${k.mom_pct >= 0 ? "up" : "dn"} mono">${fmt.pct(k.mom_pct)} MoM</span></div>
        <div><small>Active customers</small><b>${fmt.num(k.customers)}</b><span class="mu mono">ARPU $${k.arpu}</span></div>
        <div><small>Next quarter forecast</small><b>${fmt.k(sum(r.forecast.values))}</b><span class="mu mono">MAPE ${r.forecast.mape}%</span></div></div></section>
      <section class="rp-sec"><h4>Revenue trend &amp; outlook</h4><div class="chart-box sm"><canvas id="c-rp"></canvas></div></section>
      <section class="rp-sec"><h4>Findings</h4><div class="insights">${r.insights.map((x) => `<div class="ins ${x.tone}"><div class="ii">${icon(x.icon)}</div><div><b>${esc(x.title)}</b><span>${esc(x.detail)}</span></div></div>`).join("")}</div></section>
      ${r.anomalies.length ? `<section class="rp-sec"><h4>Root cause · ${mlong(r.anomalies.at(-1).month)}</h4><p>${md(r.insight)}</p></section>` : ""}
      <section class="rp-sec"><h4>Forecast detail</h4><table class="tbl"><thead><tr><th>Month</th><th class="num">Low (5%)</th><th class="num">Expected</th><th class="num">High (95%)</th></tr></thead><tbody>
        ${r.forecast.months.map((m, i) => `<tr><td>${mlong(m)}</td><td class="num">${fmt.usd(r.forecast.lower[i])}</td><td class="num"><b>${fmt.usd(r.forecast.values[i])}</b></td><td class="num">${fmt.usd(r.forecast.upper[i])}</td></tr>`).join("")}</tbody></table>
        <p class="mu" style="font-size:12px;margin-top:12px">Model: ${esc(r.forecast.model)}. Figures computed by the AETHER analytics engine from the organization’s sales table.</p></section>
    </article></div>`;
  const n = r.months.length, F = r.forecast, pad = (a) => [...Array(n - 1).fill(null), r.revenue[n - 1], ...a];
  const base = chartBase(); base.animation = false;
  mkChart("rp", $("#c-rp"), { type: "line", data: { labels: [...r.months, ...F.months].map(ml), datasets: [
    { label: "Revenue", data: [...r.revenue, ...F.months.map(() => null)], borderColor: "#7c3aed", backgroundColor: fillGrad("#7c3aed", .18), fill: true, tension: .35, pointRadius: 2, borderWidth: 2.2 },
    { label: "Forecast", data: pad(F.values), borderColor: "#0891b2", borderDash: [6, 5], tension: .3, pointRadius: 2, borderWidth: 2 },
    { label: "Upper", data: pad(F.upper), borderColor: "transparent", backgroundColor: "rgba(8,145,178,.12)", fill: "+1", pointRadius: 0 },
    { label: "Lower", data: pad(F.lower), borderColor: "transparent", pointRadius: 0 }] }, options: base });
  $("#rp-copy").onclick = () => navigator.clipboard.writeText(`${r.title}\n\n${r.summary.replace(/\*\*/g, "")}\n\n` + r.insights.map((x) => `• ${x.title} — ${x.detail}`).join("\n")).then(() => toast("Summary copied"));
};

// =========================================================================
//  NOTIFICATIONS
// =========================================================================
async function refreshBell() {
  try {
    const [alerts, D] = await Promise.all([api("alerts"), overviewData()]);
    const firing = alerts.filter((a) => a.firing), anoms = D.anomalies.slice(-3).reverse();
    const n = firing.length + anoms.length; $("#bell-n").hidden = !n; $("#bell-n").textContent = n;
    $("#bell-pop").innerHTML = `<h4>Alerts</h4>${firing.map((a) => `<div class="pop-item" data-go="alerts"><span class="dot" style="background:var(--red);margin-top:6px"></span><div>${esc(a.name)}<small>${METRIC[a.metric]?.[0] || ""} is ${fmtMetric(a.metric, a.value)}</small></div></div>`).join("") || '<div class="pop-item"><span class="dot live" style="margin-top:6px"></span><div>All alert rules OK<small>Nothing firing right now</small></div></div>'}
      <h4>Anomalies</h4>${anoms.map((a) => `<div class="pop-item" data-explain="${a.month}"><span class="dot" style="background:var(--amber);margin-top:6px"></span><div>${mlong(a.month)} · ${fmt.pct(a.change_pct)} MoM<small>Click to have the analyst explain it</small></div></div>`).join("") || '<div class="pop-item"><div class="mu">No anomalies detected</div></div>'}`;
    $("#status-pill span:last-child").textContent = D.data_mode === "real" ? "Live · your data" : D.data_mode === "demo" ? "Live · demo data" : "No data yet";
  } catch {}
}

// =========================================================================
//  COMMAND PALETTE
// =========================================================================
let CMD = [], CMD_I = 0;
function commands(q) {
  const items = [
    ...NAV.filter((n) => n.id).map((n) => ({ grp: "Go to", label: n.label, icon: n.icon, run: () => (location.hash = "#/" + n.id) })),
    { grp: "Actions", label: "Toggle light / dark theme", icon: "sun", run: toggleTheme },
    { grp: "Actions", label: "Export dataset as CSV", icon: "download", run: async () => { const r = await api("export"); download("aether_export.csv", r.content); } },
    { grp: "Actions", label: "Print executive report", icon: "print", run: () => { location.hash = "#/report"; setTimeout(print, 900); } },
    ...(can("admin") ? [{ grp: "Actions", label: "Load demo dataset", icon: "refresh", run: loadDemo }] : []),
    { grp: "Actions", label: "Account & password", icon: "shield", run: openAccount },
    { grp: "Actions", label: "Open API documentation", icon: "cpu", run: () => open("/docs", "_blank") },
    { grp: "Actions", label: "Sign out", icon: "logout", run: logout },
  ];
  const ql = q.toLowerCase().trim(), hits = items.filter((i) => !ql || i.label.toLowerCase().includes(ql));
  return ql.length > 2 ? [{ grp: "Ask AETHER", label: `“${q}”`, icon: "spark", run: () => askFromAnywhere(q) }, ...hits] : hits;
}
function openCmd() { $("#cmdk").hidden = false; $("#cmdk-q").value = ""; drawCmd(); setTimeout(() => $("#cmdk-q").focus(), 20); }
function drawCmd() {
  CMD = commands($("#cmdk-q").value); CMD_I = Math.min(CMD_I, Math.max(0, CMD.length - 1)); let g = "";
  $("#cmdk-list").innerHTML = CMD.map((c, i) => (c.grp !== g ? `<div class="grp">${(g = c.grp)}</div>` : "") + `<div class="cmdk-item ${i === CMD_I ? "on" : ""}" data-i="${i}" role="option">${icon(c.icon)}<span>${esc(c.label)}</span>${i === CMD_I ? "<kbd>↵</kbd>" : ""}</div>`).join("") || '<div class="cmdk-item mu">No results</div>';
  $$(".cmdk-item[data-i]").forEach((el) => { el.onclick = () => runCmd(+el.dataset.i); el.onmousemove = () => { if (CMD_I !== +el.dataset.i) { CMD_I = +el.dataset.i; drawCmd(); } }; });
}
function runCmd(i) { const c = CMD[i]; if (!c) return; $("#cmdk").hidden = true; c.run(); }

// =========================================================================
//  THEME + GLOBAL WIRING
// =========================================================================
function toggleTheme() {
  const t = document.documentElement.dataset.theme === "light" ? "dark" : "light";
  document.documentElement.dataset.theme = t; try { localStorage.setItem("aether.theme", t); } catch {}
  $("#theme-btn").innerHTML = icon(t === "light" ? "moon" : "sun");
  $('meta[name="theme-color"]').content = t === "light" ? "#f6f6fa" : "#05060a";
  if (S.token) route();
}

function boot() {
  try { const t = localStorage.getItem("aether.theme"); if (t) document.documentElement.dataset.theme = t; } catch {}
  paintIcons(); initLanding();
  $$("[data-demo]").forEach((b) => (b.onclick = () => loginAs("demo")));
  $$("[data-auth]").forEach((b) => (b.onclick = () => openAuth(b.dataset.auth)));
  $$("#auth-tabs button").forEach((b) => (b.onclick = () => openAuth(b.dataset.m)));
  $$("[data-as]").forEach((b) => (b.onclick = () => loginAs(b.dataset.as)));
  $("#auth-form").onsubmit = submitAuth;
  $$("[data-close]").forEach((b) => (b.onclick = () => closeModal("#auth")));
  $$(".modal").forEach((m) => m.addEventListener("mousedown", (e) => { if (e.target === m) m.hidden = true; }));
  $("#theme-btn").onclick = toggleTheme; $("#logout-btn").onclick = () => { logout(); toast("Signed out", "info"); };
  $(".me").onclick = openAccount; $(".me").style.cursor = "pointer"; $(".me").title = "Account settings";
  $("[data-close-acct]").onclick = () => closeModal("#acct");
  $("#acct-form").onsubmit = async (e) => {
    e.preventDefault(); $("#acct-err").textContent = "";
    try { await api("account/password", { method: "POST", body: { current: $("#pw-cur").value, new: $("#pw-new").value } }); closeModal("#acct"); toast("Password updated"); }
    catch (err) { $("#acct-err").textContent = err.message; }
  };
  $("#menu-btn").onclick = () => $("#app").classList.add("side-open");
  $$("[data-close-side]").forEach((b) => (b.onclick = () => $("#app").classList.remove("side-open")));
  $("#cmd-btn").onclick = openCmd;
  $("#cmdk-q").oninput = () => { CMD_I = 0; drawCmd(); };
  $("#bell-btn").onclick = (e) => { e.stopPropagation(); $("#bell-pop").hidden = !$("#bell-pop").hidden; };
  $("#bell-pop").onclick = (e) => { const it = e.target.closest(".pop-item"); if (!it) return; $("#bell-pop").hidden = true; if (it.dataset.go) location.hash = "#/" + it.dataset.go; if (it.dataset.explain) askFromAnywhere(`Why did revenue change in ${it.dataset.explain}?`); };
  document.addEventListener("click", (e) => { if (!e.target.closest(".pop-wrap")) $("#bell-pop").hidden = true; });
  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k" && S.token) { e.preventDefault(); $("#cmdk").hidden ? openCmd() : ($("#cmdk").hidden = true); }
    if (e.key === "Escape") { $$(".modal").forEach((m) => (m.hidden = true)); $("#bell-pop").hidden = true; }
    if (!$("#cmdk").hidden) {
      if (e.key === "ArrowDown") { e.preventDefault(); CMD_I = (CMD_I + 1) % Math.max(1, CMD.length); drawCmd(); }
      if (e.key === "ArrowUp") { e.preventDefault(); CMD_I = (CMD_I - 1 + CMD.length) % Math.max(1, CMD.length); drawCmd(); }
      if (e.key === "Enter") { e.preventDefault(); runCmd(CMD_I); }
    }
    if (e.key === "/" && S.token && !/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)) { e.preventDefault(); if (location.hash === "#/analyst") $("#q")?.focus(); else openCmd(); }
  });
  addEventListener("hashchange", route);
  if (/Mac|iPhone|iPad/.test(navigator.platform)) $(".search kbd").textContent = "⌘K";

  if (INVITE) {
    fetch("/api/invites/" + encodeURIComponent(INVITE)).then((r) => r.json()).then((i) => {
      if (!i.org) return toast("This invitation is invalid or has expired", "err");
      openAuth("inv"); $("#auth-title").textContent = `Join ${i.org}`; $("#auth-sub").textContent = `You’ve been invited as ${i.role} (${i.email}). Choose a username and password.`;
    });
    return;
  }
  try {
    const s = JSON.parse(sessionStorage.getItem("aether.session") || "null"), p = s && decode(s.token);
    if (p && p.exp * 1000 > Date.now() + 30000) { S.token = s.token; S.sess = s; $("#landing").hidden = true; $("#app").hidden = false; buildShell(); route(); refreshBell(); }
  } catch {}
}

boot();
