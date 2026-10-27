"use strict";

// ------------------------------------------------------------------ util
const TOKEN = (() => {
  const m = location.hash.match(/t=([\w-]+)/);
  if (m) {
    sessionStorage.setItem("token", m[1]);
    history.replaceState(null, "", location.pathname);
  }
  return sessionStorage.getItem("token") || "";
})();

const $ = (sel, root = document) => root.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
// Usado dentro de atributos style="..." — por isso aspas simples e sem aspas na URL.
const cssUrl = (u) => `url('${String(u).replace(/["'\\\n<>]/g, (c) => encodeURIComponent(c))}')`;

async function api(path, { method = "GET", body, raw, headers = {} } = {}) {
  const opts = { method, headers: { "X-Token": TOKEN, ...headers } };
  if (raw !== undefined) opts.body = raw;
  else if (body !== undefined) {
    opts.body = JSON.stringify(body);
    opts.headers["Content-Type"] = "application/json";
  }
  const res = await fetch(path, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Erro ${res.status}`);
  return data;
}

function fmtNum(n) {
  if (n >= 1e6) return (n / 1e6).toFixed(n >= 1e7 ? 0 : 1).replace(".0", "") + "M";
  if (n >= 1e3) return (n / 1e3).toFixed(n >= 1e4 ? 0 : 1).replace(".0", "") + "K";
  return String(n);
}
function fmtPlaytime(sec) {
  if (!sec || sec < 60) return "0 min";
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60);
  return h ? `${h} h ${m} min` : `${m} min`;
}
function timeAgo(ts) {
  if (!ts) return "Nunca";
  const d = (Date.now() / 1000 - ts);
  if (d < 60) return "Agora";
  if (d < 3600) return `Há ${Math.floor(d / 60)} min`;
  if (d < 86400) return `Há ${Math.floor(d / 3600)} h`;
  if (d < 86400 * 30) return `Há ${Math.floor(d / 86400)} dia(s)`;
  return new Date(ts * 1000).toLocaleDateString("pt-BR");
}
function fmtSize(b) {
  if (b >= 1048576) return (b / 1048576).toFixed(1) + " MB";
  return Math.max(1, Math.round(b / 1024)) + " KB";
}
function hashHue(s) {
  let h = 0;
  for (const c of String(s)) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return h % 360;
}
function initials(name) {
  return String(name).split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join("").toUpperCase() || "?";
}
/** Estilo de fundo para a arte de uma instância/projeto (imagem ou gradiente). */
function artStyle(name, url) {
  if (url) return `background-image:${cssUrl(url)}`;
  const h = hashHue(name);
  return `background-image:linear-gradient(135deg,hsl(${h} 65% 45%),hsl(${(h + 50) % 360} 70% 28%))`;
}
function art(name, url, cls = "thumb") {
  return `<div class="${cls}" style="${artStyle(name, url)}">${url ? "" : esc(initials(name))}</div>`;
}

// ------------------------------------------------------------------ ícones
const I = {
  play: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M8 5.5v13a1 1 0 0 0 1.5.86l10.5-6.5a1 1 0 0 0 0-1.72L9.5 4.64A1 1 0 0 0 8 5.5z"/></svg>',
  stop: '<svg viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>',
  plus: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>',
  search: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>',
  gear: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>',
  folder: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>',
  more: '<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="5" cy="12" r="2"/><circle cx="12" cy="12" r="2"/><circle cx="19" cy="12" r="2"/></svg>',
  download: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 4v11m0 0-4-4m4 4 4-4M5 20h14"/></svg>',
  upload: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 16V5m0 0-4 4m4-4 4 4M5 20h14"/></svg>',
  heart: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1-1.1a5.5 5.5 0 0 0-7.8 7.8l1 1.1L12 21l7.8-7.5 1-1.1a5.5 5.5 0 0 0 0-7.8z"/></svg>',
  clock: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',
  trash: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/></svg>',
  refresh: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 11a8 8 0 0 0-14.9-3M4 4v4h4M4 13a8 8 0 0 0 14.9 3M20 20v-4h-4"/></svg>',
  x: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18"/></svg>',
  external: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/></svg>',
  copy: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a1 1 0 0 1 1-1h10"/></svg>',
  cube: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><path d="M12 2 3 7v10l9 5 9-5V7z"/><path d="m3 7 9 5 9-5M12 12v10"/></svg>',
  user: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></svg>',
  calendar: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/></svg>',
};


// ------------------------------------------------------------------ modais
function modal(html, { wide = false, onClose } = {}) {
  const root = document.createElement("div");
  root.className = "overlay";
  root.innerHTML = `<div class="modal ${wide ? "wide" : ""}">${html}</div>`;
  const close = () => { root.remove(); onClose && onClose(); };
  root.addEventListener("mousedown", (e) => { if (e.target === root) close(); });
  root.querySelectorAll("[data-close]").forEach((b) => b.addEventListener("click", close));
  $("#modal-root").appendChild(root);
  root.close = close;
  return root;
}
const head = (title) => `<div class="modal-head"><h3>${title}</h3><button class="icon-btn" data-close>${I.x}</button></div>`;

function toast(msg, type = "", ms = 4500) {
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.innerHTML = msg;
  $("#toasts").appendChild(el);
  setTimeout(() => el.remove(), ms);
}
const fail = (e) => toast(esc(e.message || e), "error", 7000);

function confirmDialog(title, text, okLabel = "Confirmar", danger = false) {
  return new Promise((resolve) => {
    const m = modal(`${head(esc(title))}<div class="modal-body muted">${text}</div>
      <div class="modal-foot"><button class="btn" data-close>Cancelar</button><button class="btn ${danger ? "red" : "primary"}" id="ok">${esc(okLabel)}</button></div>`,
      { onClose: () => resolve(false) });
    $("#ok", m).addEventListener("click", () => { resolve(true); m.remove(); });
  });
}

function promptDialog(title, label, value = "") {
  return new Promise((resolve) => {
    const m = modal(`${head(esc(title))}<form class="modal-body"><div class="field"><label>${esc(label)}</label><input class="input" id="pv" value="${esc(value)}"></div></form>
      <div class="modal-foot"><button class="btn" data-close>Cancelar</button><button class="btn primary" id="ok">OK</button></div>`,
      { onClose: () => resolve(null) });
    const input = $("#pv", m);
    input.focus();
    input.select();
    const ok = () => { resolve(input.value.trim() || null); m.remove(); };
    $("#ok", m).addEventListener("click", ok);
    $("form", m).addEventListener("submit", (e) => { e.preventDefault(); ok(); });
  });
}


// ---- contas
let loginModal = null;
function accountsModal() {
  const d = S.data;
  const rows = d.accounts.map((a) => `<div class="acc-row ${a.uuid === d.default_account ? "active" : ""}">
      ${avatar(a)}<div class="grow"><div style="font-weight:700">${esc(a.name)}</div><div class="faint">${a.type === "msa" ? "Conta Microsoft" : "Offline"}</div></div>
      ${a.uuid === d.default_account ? '<span class="pill green">Em uso</span>' : `<button class="btn" data-acc="use" data-uuid="${esc(a.uuid)}">Usar</button>`}
      <button class="icon-btn" data-acc="remove" data-uuid="${esc(a.uuid)}" title="Remover">${I.trash}</button>
    </div>`).join("");
  const m = modal(`${head("Contas")}
    <div class="modal-body">
      ${rows || '<div class="faint" style="margin-bottom:12px">Nenhuma conta adicionada.</div>'}
      <button class="btn primary block" id="acc-ms" style="margin-top:6px">Entrar com conta Microsoft</button>
      <h2 class="section" style="margin-top:20px">Conta offline</h2>
      <form class="row2" id="acc-off" style="grid-template-columns:1fr auto"><input class="input" id="acc-name" placeholder="Nome de jogador" maxlength="16"><button class="btn">Adicionar</button></form>
      <div class="faint" style="margin-top:6px">Contas offline funcionam em singleplayer, LAN e servidores em modo offline.</div>
    </div>`);
  m.querySelectorAll("[data-acc]").forEach((b) => b.addEventListener("click", async () => {
    try {
      await api(`/api/accounts/${b.dataset.acc === "use" ? "default" : "remove"}`, { method: "POST", body: { uuid: b.dataset.uuid } });
      await refresh();
      m.close();
      accountsModal();
    } catch (e) { fail(e); }
  }));
  $("#acc-off", m).addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      await api("/api/accounts/offline", { method: "POST", body: { name: $("#acc-name", m).value } });
      await refresh();
      m.close();
      toast("Conta adicionada", "success");
    } catch (err) { fail(err); }
  });
  $("#acc-ms", m).addEventListener("click", async () => {
    try {
      await api("/api/accounts/microsoft", { method: "POST" });
      m.close();
      loginModal = modal(`${head("Entrar com Microsoft")}<div class="modal-body" id="login-body"><div class="center"><span class="spin"></span></div></div>`,
        { onClose: () => { api("/api/accounts/microsoft/cancel", { method: "POST" }); loginModal = null; } });
    } catch (e) { fail(e); }
  });
}

function onLoginEvent(data) {
  if (!loginModal) return;
  if (data.done) {
    const m = loginModal;
    loginModal = null;
    m.remove();
    toast(`Logado como <b>${esc(data.name)}</b>`, "success");
    return;
  }
  $("#login-body", loginModal).innerHTML = `<div class="muted">1. Abra <b>${esc(data.url)}</b><br>2. Digite o código abaixo e entre com sua conta Microsoft.</div>
    <div class="code-box">${esc(data.code)}</div>
    <button class="btn primary block" id="login-open">${I.copy} Copiar código e abrir navegador</button>
    <div class="faint" style="margin-top:12px;display:flex;gap:8px;align-items:center"><span class="spin"></span> Aguardando confirmação...</div>`;
  $("#login-open", loginModal).addEventListener("click", () => {
    navigator.clipboard?.writeText(data.code);
    window.open(data.url, "_blank");
  });
}


// ---- menu de contexto
function menu(anchor, items) {
  document.querySelectorAll(".menu").forEach((x) => x.remove());
  const el = document.createElement("div");
  el.className = "menu";
  el.innerHTML = items.map((it) => it === "-" ? "<hr>" : `<button class="${it.danger ? "danger" : ""}">${it.icon || ""} ${esc(it.label)}</button>`).join("");
  const btns = [...el.querySelectorAll("button")];
  items.filter((it) => it !== "-").forEach((it, idx) => btns[idx].addEventListener("click", () => { el.remove(); it.run(); }));
  document.body.appendChild(el);
  const r = anchor.getBoundingClientRect();
  el.style.top = `${Math.min(r.bottom + 6, innerHeight - el.offsetHeight - 10)}px`;
  el.style.left = `${Math.max(10, r.right - el.offsetWidth)}px`;
  setTimeout(() => document.addEventListener("mousedown", function off(e) {
    if (!el.contains(e.target)) { el.remove(); document.removeEventListener("mousedown", off); }
  }), 0);
}


Object.assign(I, {
  cart: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="20" r="1.5"/><circle cx="18" cy="20" r="1.5"/><path d="M2 3h3l2.6 12.4a1 1 0 0 0 1 .8h9.7a1 1 0 0 0 1-.8L21 7H6"/></svg>',
  shirt: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><path d="M8 3 3 6l2 5 3-1v11h8V10l3 1 2-5-5-3a4 4 0 0 1-8 0z"/></svg>',
  sword: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.5 17.5 3 6V3h3l11.5 11.5M13 19l6-6M16 16l4 4M19 21l2-2"/></svg>',
  sliders: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M20 18h0"/><circle cx="16" cy="6" r="2"/><circle cx="10" cy="12" r="2"/><circle cx="18" cy="18" r="2"/></svg>',
  terminal: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="m7 9 3 3-3 3M13 15h4"/></svg>',
  check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="m5 12 5 5 9-10"/></svg>',
});

// ------------------------------------------------------------------ estado
const S = {
  data: null,
  view: "home",
  tasks: {},
  modules: null,
  catalog: null,
  catalogError: null,
  me: null,
  storeFilter: "all",
  cart: (() => { try { return JSON.parse(localStorage.getItem("cart") || "[]"); } catch { return []; } })(),
  logs: [],
};
const PLAY_KEY = "client";
const TYPE_LABEL = { cape: "Capa", wings: "Asas", bundle: "Pacote" };
const SLOT_LABEL = { cape: "Capa", wings: "Asas" };

const brl = (cents) => (cents / 100).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
const item = (id) => S.catalog?.items.find((x) => x.id === id);
const playTask = () => Object.values(S.tasks).find((t) => t.instance === PLAY_KEY && t.status === "running");
function saveCart() { try { localStorage.setItem("cart", JSON.stringify(S.cart)); } catch {} }
function owns(id) {
  const it = item(id);
  if (!S.me || !it) return false;
  const ids = it.type === "bundle" ? it.items : [id];
  return ids.every((x) => S.me.owned.includes(x));
}

async function refresh() {
  S.data = await api("/api/state");
  for (const t of S.data.tasks) S.tasks[t.id] = t;
  renderChrome();
  renderView();
}

async function loadStore() {
  try {
    S.catalog = await api("/api/store/catalog");
    S.catalogError = null;
  } catch (e) { S.catalogError = e.message; }
  S.cart = S.cart.filter((id) => item(id));
  if (S.data?.store_logged) {
    try { S.me = await api("/api/store/me"); } catch { S.me = null; }
  } else S.me = null;
  S.cart = S.cart.filter((id) => !owns(id));
  saveCart();
  renderChrome();
  renderView();
}

function go(view) {
  S.view = view;
  if (view === "mods") api("/api/modules").then((m) => { S.modules = m; renderView(); }).catch(fail);
  if (view === "logs") api("/api/logs").then((l) => { S.logs = l; renderView(); }).catch(fail);
  if ((view === "store" || view === "wardrobe") && !S.catalog) loadStore();
  renderChrome();
  renderView();
  $("#view").scrollTop = 0;
}

// ------------------------------------------------------------------ chrome
function renderChrome() {
  const d = S.data;
  if (!d) return;
  document.querySelectorAll("#nav button").forEach((b) => b.classList.toggle("active", b.dataset.nav === S.view));
  const acc = d.accounts.find((a) => a.uuid === d.default_account);
  $("#btn-account").innerHTML = acc
    ? `${avatar(acc)}<span>${esc(acc.name)}</span>`
    : `<span class="avatar" style="background:var(--surface-3)">${I.user}</span><span>Adicionar conta</span>`;
  $("#cart-count").textContent = S.cart.length || "";
  $("#side-play").innerHTML = playButton(true);
  // carrinho na barra lateral
  const total = S.cart.reduce((s, id) => s + (item(id)?.price || 0), 0);
  $("#sidebar-list").innerHTML = `
    <div class="sidebar-group">Atalhos</div>
    ${[["home", I.sword, "Jogar"], ["mods", I.sliders, "Mods do client"], ["store", I.cart, "Loja"], ["wardrobe", I.shirt, "Guarda-roupa"], ["logs", I.terminal, "Logs"]]
      .map(([v, icon, label]) => `<div class="side-item ${S.view === v ? "active" : ""}" data-act="nav" data-nav="${v}"><div class="thumb side-icon">${icon}</div><div class="info"><div class="name">${label}</div></div></div>`).join("")}
    <div class="sidebar-group">Carrinho (${S.cart.length})</div>
    ${S.cart.length ? S.cart.map((id) => `<div class="side-item" data-act="nav" data-nav="store">${preview(item(id), "thumb")}<div class="info"><div class="name">${esc(item(id).name)}</div><div class="meta">${brl(item(id).price)}</div></div><button class="quick-play" data-act="cart-remove" data-id="${esc(id)}" title="Remover">${I.x}</button></div>`).join("")
      + `<button class="btn primary block" style="margin-top:8px" data-act="checkout">${I.cart} Finalizar · ${brl(total)}</button>`
      : '<div class="faint" style="padding:4px 8px">Vazio. Veja a loja de cosméticos.</div>'}`;
  renderTasks();
}

function avatar(acc, size = "") {
  const h = hashHue(acc.name);
  const fallback = `<span class="avatar ${size}" style="background:hsl(${h} 55% 40%)">${esc(acc.name[0].toUpperCase())}</span>`;
  if (acc.type !== "msa") return fallback;
  return `<span class="avatar ${size}" style="background:hsl(${h} 55% 40%)"><img src="https://mc-heads.net/avatar/${esc(acc.uuid)}/64" alt="" onerror="this.replaceWith(document.createTextNode('${esc(acc.name[0].toUpperCase())}'))"></span>`;
}

function renderTasks() {
  const tasks = Object.values(S.tasks).filter((t) => t.status === "running" || t.status === "error").slice(-4);
  $("#tasks").innerHTML = tasks.map((t) => {
    const pct = t.total ? Math.round((t.done / t.total) * 100) : 0;
    return `<div class="task ${t.status}">
      <div class="task-title"><span>${esc(t.title)}</span>${t.status === "error" ? `<button class="icon-btn" style="width:20px;height:20px" data-act="dismiss-task" data-id="${t.id}">${I.x}</button>` : t.total ? `<span>${pct}%</span>` : ""}</div>
      <div class="task-msg" title="${esc(t.message)}">${esc(t.message || "Aguarde...")}</div>
      ${t.status === "running" ? `<div class="bar ${t.total ? "" : "indeterminate"}"><i style="width:${t.total ? pct : 35}%"></i></div>` : ""}
    </div>`;
  }).join("");
}

function playButton(block = false) {
  const task = playTask();
  const cls = block ? "block" : "";
  if (S.data.running) return `<button class="btn red big ${cls}" data-act="stop">${I.stop} Fechar jogo</button>`;
  if (task) return `<button class="btn big ${cls}" disabled><span class="spin"></span> ${task.total ? Math.round(task.done / task.total * 100) + "%" : "Preparando"}</button>`;
  return `<button class="btn green big ${cls}" data-act="play">${I.play} Jogar</button>`;
}

/** Prévia de um cosmético: frente da capa ou par de asas, em pixel art. */
function preview(it, cls = "preview") {
  if (!it) return `<div class="${cls}"></div>`;
  const tex = cssUrl(it.texture);
  const kind = it.type === "bundle" ? "cape" : it.type;
  if (kind === "wings") {
    return `<div class="${cls} cos-preview wings"><i style="background-image:${tex}"></i><i class="mirror" style="background-image:${tex}"></i></div>`;
  }
  return `<div class="${cls} cos-preview cape"><i style="background-image:${tex}"></i></div>`;
}

// ------------------------------------------------------------------ views
function renderView() {
  const v = $("#view");
  if (!S.data) { v.innerHTML = `<div class="center"><span class="spin"></span></div>`; return; }
  const views = { home: viewHome, mods: viewMods, store: viewStore, wardrobe: viewWardrobe, logs: viewLogs };
  v.innerHTML = views[S.view]();
  if (S.view === "logs") { const c = $("#console"); if (c) c.scrollTop = c.scrollHeight; }
}

function viewHome() {
  const i = S.data.instance;
  const featured = (S.catalog?.items || []).filter((x) => x.featured).slice(0, 4);
  const equipped = S.me ? Object.entries(S.me.equipped) : [];
  return `<div class="hero home-hero">
      <div class="hero-bg pvp-bg"></div>
      <div class="hero-inner">
        <div class="thumb brand-thumb">S</div>
        <div class="grow">
          <h1>SpkPvP Client</h1>
          <div class="badges">
            <span class="badge">${I.cube} Minecraft ${esc(S.data.settings.minecraft)}</span>
            <span class="badge">Fabric</span>
            <span class="badge">Sodium · Lithium</span>
            ${S.data.running ? '<span class="badge" style="color:var(--green)"><span class="dot"></span> Em execução</span>' : ""}
          </div>
        </div>
        <div class="hero-actions">
          <button class="icon-btn" data-act="open-folder" title="Abrir pasta do jogo">${I.folder}</button>
          ${playButton()}
        </div>
      </div>
    </div>
    <div class="page">
      <div class="stats">
        <div class="stat"><div class="label">Tempo de jogo</div><div class="value">${fmtPlaytime(i?.playtime)}</div></div>
        <div class="stat"><div class="label">Última vez</div><div class="value">${timeAgo(i?.last_played)}</div></div>
        <div class="stat"><div class="label">Memória</div><div class="value">${((i?.effective_memory || S.data.settings.default_memory_mb) / 1024).toFixed(1).replace(".0", "")} GB</div></div>
        <div class="stat"><div class="label">Cosméticos</div><div class="value">${S.me ? S.me.owned.length : "—"}</div></div>
      </div>
      <h2 class="section">Recursos do client</h2>
      <div class="feature-grid">
        ${[["Keystrokes e CPS", "Veja suas teclas e cliques por segundo na tela."], ["Armor Status", "Durabilidade da armadura e do item na mão."], ["Toggle Sprint", "Corrida sempre ligada, sem segurar Ctrl."], ["Zoom", "Segure C para dar zoom, como no OptiFine."], ["Editor de HUD", "Shift direito no jogo: mova e ligue módulos."], ["FPS alto", "Sodium e Lithium instalados automaticamente."]]
          .map(([t, d]) => `<div class="panel"><b>${t}</b><div class="muted">${d}</div></div>`).join("")}
      </div>
      ${equipped.length ? `<h2 class="section">Equipado</h2><div class="grid small">${equipped.map(([slot, id]) => item(id) ? `<div class="card" data-act="nav" data-nav="wardrobe">${preview(item(id), "card-img")}<div class="card-name">${esc(item(id).name)}</div><div class="card-meta">${SLOT_LABEL[slot]}</div></div>` : "").join("")}</div>` : ""}
      ${featured.length ? `<h2 class="section">Destaques da loja</h2><div class="grid small">${featured.map(storeCard).join("")}</div>` : ""}
    </div>`;
}

function viewMods() {
  if (!S.modules) return `<div class="center"><span class="spin"></span></div>`;
  const cats = [...new Set(S.modules.map((m) => m.category))];
  return `<div class="page">
    <div class="page-head"><h1>Mods do client</h1><div class="grow"></div>
      <button class="btn" data-act="open-folder" data-sub="config">${I.folder} Configurações</button></div>
    <div class="panel muted" style="margin-bottom:6px">No jogo, aperte <b>Shift direito</b> para abrir o menu do SpkPvP: ligue/desligue módulos e arraste os elementos do HUD. As mudanças feitas aqui valem na próxima vez que o jogo abrir.</div>
    ${cats.map((c) => `<h2 class="section">${esc(c)}</h2><div class="module-grid">${S.modules.filter((m) => m.category === c).map((m) => `
      <label class="module ${m.enabled ? "on" : ""}">
        <div class="grow"><div class="module-name">${esc(m.name)}</div><div class="faint">${esc(m.description)}</div></div>
        <span class="switch"><input type="checkbox" ${m.enabled ? "checked" : ""} data-act="toggle-module" data-id="${esc(m.id)}"><span></span></span>
      </label>`).join("")}</div>`).join("")}
  </div>`;
}

function storeCard(it) {
  const have = owns(it.id);
  const inCart = S.cart.includes(it.id);
  const btn = have ? `<span class="pill green">${I.check} Possui</span>`
    : it.price === 0 ? '<span class="pill">Grátis</span>'
      : `<button class="btn ${inCart ? "" : "primary"}" data-act="${inCart ? "cart-remove" : "cart-add"}" data-id="${esc(it.id)}">${inCart ? "No carrinho" : `${I.cart} ${brl(it.price)}`}</button>`;
  return `<div class="card store-card rarity-${esc(it.rarity.normalize("NFD").replace(/[^a-z]/g, ""))}">
    ${preview(it, "card-img")}
    <div class="card-badge-top"><span class="pill">${TYPE_LABEL[it.type]}</span>${it.type === "bundle" ? "" : `<span class="pill rarity">${esc(it.rarity)}</span>`}</div>
    <div class="card-name" title="${esc(it.name)}">${esc(it.name)}</div>
    <div class="card-meta">${esc(it.description)}</div>
    <div class="store-buy">${btn}</div>
  </div>`;
}

function storeLoginPanel() {
  const acc = S.data.accounts.find((a) => a.uuid === S.data.default_account);
  if (!acc) return `<div class="panel store-login"><div class="grow"><b>Adicione uma conta</b><div class="muted">Os cosméticos ficam vinculados à sua conta do Minecraft.</div></div><button class="btn primary" data-act="accounts">Adicionar conta</button></div>`;
  if (S.data.store_logged) return "";
  return `<div class="panel store-login">${avatar(acc)}<div class="grow"><b>Entrar na loja como ${esc(acc.name)}</b><div class="muted">${acc.type === "msa" ? "Sua conta Microsoft é verificada pela Mojang; nenhuma senha é enviada à loja." : "Contas offline só funcionam em servidores de loja em modo de desenvolvimento."}</div></div><button class="btn primary" data-act="store-login">Entrar</button></div>`;
}

function viewStore() {
  if (S.catalogError) return `<div class="page"><div class="empty"><h2>Loja indisponível</h2><div>${esc(S.catalogError)}</div><div class="faint" style="margin-top:6px">Servidor configurado: ${esc(S.data.settings.store_url)}</div><button class="btn" data-act="reload-store">${I.refresh} Tentar de novo</button></div></div>`;
  if (!S.catalog) return `<div class="center"><span class="spin"></span></div>`;
  const filters = [["all", "Tudo"], ["cape", "Capas"], ["wings", "Asas"], ["bundle", "Pacotes"]];
  const list = S.catalog.items.filter((x) => S.storeFilter === "all" || x.type === S.storeFilter);
  return `<div class="page">
    <div class="page-head"><h1>Loja de cosméticos</h1><div class="grow"></div>
      <div class="seg" style="margin:0;min-width:360px">${filters.map(([k, l]) => `<button class="${S.storeFilter === k ? "active" : ""}" data-act="store-filter" data-filter="${k}">${l}</button>`).join("")}</div>
      <button class="btn primary" data-act="checkout" ${S.cart.length ? "" : "disabled"}>${I.cart} Carrinho (${S.cart.length})</button>
    </div>
    ${storeLoginPanel()}
    <div class="grid store-grid">${list.map(storeCard).join("")}</div>
    <div class="faint" style="margin-top:22px">Pagamento por Pix, boleto bancário, cartão de crédito, cartão de débito ou PayPal. Cosméticos são apenas visuais e não dão vantagem no jogo.</div>
  </div>`;
}

function viewWardrobe() {
  if (!S.catalog) return `<div class="center"><span class="spin"></span></div>`;
  if (!S.me) return `<div class="page"><div class="page-head"><h1>Guarda-roupa</h1></div>${storeLoginPanel() || '<div class="center"><span class="spin"></span></div>'}</div>`;
  return `<div class="page">
    <div class="page-head"><h1>Guarda-roupa</h1><div class="grow"></div><button class="btn" data-act="nav" data-nav="store">${I.cart} Ir para a loja</button></div>
    ${S.catalog.slots.map((slot) => {
      const owned = S.catalog.items.filter((x) => x.type === slot && S.me.owned.includes(x.id));
      const cur = S.me.equipped[slot];
      return `<h2 class="section">${SLOT_LABEL[slot]}</h2><div class="grid small">
        <div class="card ${cur ? "" : "equipped"}" data-act="equip" data-slot="${slot}" data-id=""><div class="card-img none">${I.x}</div><div class="card-name">Nenhuma</div></div>
        ${owned.map((x) => `<div class="card ${cur === x.id ? "equipped" : ""}" data-act="equip" data-slot="${slot}" data-id="${esc(x.id)}">${preview(x, "card-img")}<div class="card-name">${esc(x.name)}</div><div class="card-meta">${cur === x.id ? "Equipado" : "Clique para equipar"}</div></div>`).join("")}
        ${owned.length ? "" : `<div class="card add" data-act="nav" data-nav="store"><div class="card-img">${I.plus}</div><div class="card-name faint">Comprar ${SLOT_LABEL[slot].toLowerCase()}</div></div>`}
      </div>`;
    }).join("")}
    ${S.me.orders.length ? `<h2 class="section">Pedidos</h2><div class="table">${S.me.orders.map((o) => `<div class="row"><div class="file">${o.items.map((id) => esc(item(id)?.name || id)).join(", ")}</div><span class="tag">${esc(METHOD_LABEL[o.method] || o.method)}</span><span class="tag ${o.status === "paid" ? "pack" : ""}">${esc(STATUS_LABEL[o.status] || o.status)}</span><span class="size">${brl(o.total)}</span></div>`).join("")}</div>` : ""}
  </div>`;
}
const STATUS_LABEL = { pending: "Aguardando", paid: "Pago", failed: "Falhou", refunded: "Estornado" };
const METHOD_LABEL = { pix: "Pix", boleto: "Boleto", credit_card: "Crédito", debit_card: "Débito", paypal: "PayPal", demo: "Demo" };

function logClass(line) {
  if (/\b(ERROR|FATAL|Exception|Erro)\b/.test(line)) return "err";
  if (/\bWARN\b/.test(line)) return "warn";
  if (/^(Preparando|Verificando|Iniciando|Baixando|Instalando|Adicionando|Mod SpkPvP)/.test(line)) return "info";
  return "";
}
function viewLogs() {
  return `<div class="page"><div class="toolbar"><div class="grow muted" style="flex:1">Saída do jogo e do launcher</div>
      <button class="btn" data-act="copy-logs">${I.copy} Copiar</button>
      <button class="btn" data-act="open-folder" data-sub="logs">${I.folder} Logs do jogo</button></div>
    <div class="console" id="console">${S.logs.map((l) => `<div class="${logClass(l)}">${esc(l)}</div>`).join("") || '<span class="faint">Nenhum log ainda. Inicie o jogo para ver a saída aqui.</span>'}</div></div>`;
}

// ------------------------------------------------------------------ checkout
let orderPoll = null;
async function checkoutModal() {
  if (!S.cart.length) return;
  if (!S.data.store_logged) { go("store"); return toast("Entre na loja para comprar", "error"); }
  const methods = S.catalog.methods;
  if (!methods.length) return toast("Nenhum método de pagamento configurado no servidor da loja", "error");
  let method = methods[0].id;
  const total = S.cart.reduce((s, id) => s + item(id).price, 0);
  const m = modal(`${head("Finalizar compra")}
    <div class="modal-body" id="co-body">
      <div class="table" style="margin-bottom:14px">${S.cart.map((id) => `<div class="row">${preview(item(id), "thumb")}<div class="file">${esc(item(id).name)}</div><span class="size">${brl(item(id).price)}</span></div>`).join("")}
        <div class="row"><div class="file">Total</div><span class="size" style="width:auto;font-weight:700;color:var(--text)">${brl(total)}</span></div></div>
      <div class="field"><label>Forma de pagamento</label><div class="pay-grid">${methods.map((x) => `<button type="button" data-method="${x.id}">${esc(x.label)}</button>`).join("")}</div></div>
      <form class="form" id="co-form" style="max-width:none;margin-top:14px"></form>
    </div>
    <div class="modal-foot"><button class="btn" data-close>Cancelar</button><button class="btn primary" id="co-pay">Pagar ${brl(total)}</button></div>`,
  { wide: true, onClose: () => { clearInterval(orderPoll); orderPoll = null; } });
  const saved = (() => { try { return JSON.parse(localStorage.getItem("payer") || "{}"); } catch { return {}; } })();
  const val = (k) => esc(saved[k] || "");
  const renderForm = () => {
    m.querySelectorAll("[data-method]").forEach((b) => b.classList.toggle("active", b.dataset.method === method));
    const person = `<div class="row2"><div class="field"><label>Nome</label><input class="input" name="first_name" value="${val("first_name")}" required></div>
        <div class="field"><label>Sobrenome</label><input class="input" name="last_name" value="${val("last_name")}" required></div></div>
      <div class="row2"><div class="field"><label>E-mail</label><input class="input" type="email" name="email" value="${val("email")}" required></div>
        <div class="field"><label>CPF</label><input class="input" name="cpf" value="${val("cpf")}" placeholder="000.000.000-00" required></div></div>`;
    const address = `<div class="row2" style="grid-template-columns:1fr 2fr 1fr"><div class="field"><label>CEP</label><input class="input" name="zip_code" value="${val("zip_code")}" required></div>
        <div class="field"><label>Rua</label><input class="input" name="street_name" value="${val("street_name")}" required></div>
        <div class="field"><label>Número</label><input class="input" name="street_number" value="${val("street_number")}" required></div></div>
      <div class="row2" style="grid-template-columns:2fr 2fr 1fr"><div class="field"><label>Bairro</label><input class="input" name="neighborhood" value="${val("neighborhood")}" required></div>
        <div class="field"><label>Cidade</label><input class="input" name="city" value="${val("city")}" required></div>
        <div class="field"><label>UF</label><input class="input" name="federal_unit" value="${val("federal_unit")}" maxlength="2" required></div></div>`;
    const forms = {
      pix: person + '<div class="hint faint">Você recebe um QR Code Pix. A confirmação é automática, em segundos.</div>',
      boleto: person + address + '<div class="hint faint">O boleto vence em poucos dias. A compensação pode levar até 3 dias úteis.</div>',
      credit_card: `<div class="field"><label>E-mail</label><input class="input" type="email" name="email" value="${val("email")}"></div><div class="hint faint">Você será levado ao checkout seguro do Mercado Pago para digitar o cartão (até 12x). Os dados do cartão não passam pelo SpkPvP.</div>`,
      debit_card: `<div class="field"><label>E-mail</label><input class="input" type="email" name="email" value="${val("email")}"></div><div class="hint faint">Você será levado ao checkout seguro do Mercado Pago para pagar com cartão de débito.</div>`,
      paypal: '<div class="hint faint">Você será levado ao PayPal para aprovar o pagamento.</div>',
      demo: '<div class="hint faint">Servidor em modo de desenvolvimento: nenhuma cobrança real é feita.</div>',
    };
    $("#co-form", m).innerHTML = forms[method] || "";
  };
  m.querySelectorAll("[data-method]").forEach((b) => b.addEventListener("click", () => { method = b.dataset.method; renderForm(); }));
  renderForm();
  $("#co-pay", m).addEventListener("click", async () => {
    const f = $("#co-form", m);
    if (!f.reportValidity()) return;
    const fd = Object.fromEntries(new FormData(f).entries());
    try { localStorage.setItem("payer", JSON.stringify({ ...saved, ...fd })); } catch {}
    const payer = { email: fd.email, first_name: fd.first_name, last_name: fd.last_name, cpf: fd.cpf,
      address: { zip_code: fd.zip_code, street_name: fd.street_name, street_number: fd.street_number, neighborhood: fd.neighborhood, city: fd.city, federal_unit: fd.federal_unit } };
    const btn = $("#co-pay", m);
    btn.disabled = true;
    btn.innerHTML = '<span class="spin"></span> Processando';
    try {
      const order = await api("/api/store/checkout", { method: "POST", body: { items: S.cart, method, payer } });
      showPayment(m, order);
    } catch (e) {
      fail(e);
      btn.disabled = false;
      btn.textContent = `Pagar ${brl(total)}`;
    }
  });
}

function showPayment(m, order) {
  const d = order.details || {};
  const waiting = '<div class="faint" style="margin-top:14px;display:flex;gap:8px;align-items:center;justify-content:center"><span class="spin"></span> Aguardando confirmação do pagamento...</div>';
  let body = "";
  if (d.kind === "pix") {
    body = `<div style="text-align:center"><div class="muted">Escaneie o QR Code no app do seu banco</div>
      ${d.qr_code_base64 ? `<img class="qr" src="data:image/png;base64,${esc(d.qr_code_base64)}" alt="QR Code Pix">` : ""}
      <div class="field" style="text-align:left"><label>Pix copia e cola</label><div class="row2" style="grid-template-columns:1fr auto"><input class="input" value="${esc(d.qr_code || "")}" readonly><button class="btn" id="copy-pix">${I.copy} Copiar</button></div></div>
      <div class="muted">Total: <b>${brl(order.total)}</b> · O código expira em 30 minutos.</div>${waiting}</div>`;
  } else if (d.kind === "boleto") {
    body = `<div class="muted">Boleto gerado. Pague no app do banco ou em lotéricas até o vencimento.</div>
      <div class="field" style="margin-top:12px"><label>Linha digitável</label><div class="row2" style="grid-template-columns:1fr auto"><input class="input" value="${esc(d.barcode || "")}" readonly><button class="btn" id="copy-boleto">${I.copy} Copiar</button></div></div>
      ${d.url ? `<button class="btn primary" data-act="open-browser" data-url="${esc(d.url)}">${I.external} Abrir boleto (PDF)</button>` : ""}
      <div class="faint" style="margin-top:10px">A compensação do boleto leva até 3 dias úteis. Os cosméticos aparecem automaticamente depois; pode fechar esta janela.</div>${waiting}`;
  } else {
    body = `<div style="text-align:center"><div class="muted">Conclua o pagamento na página que abriu no navegador.</div>
      <button class="btn" style="margin-top:12px" data-act="open-browser" data-url="${esc(d.url)}">${I.external} Abrir página de pagamento novamente</button>${waiting}</div>`;
    api("/api/open-url", { method: "POST", body: { url: d.url } }).catch(fail);
  }
  $("#co-body", m).innerHTML = body;
  $(".modal-foot", m).innerHTML = '<button class="btn" data-close>Fechar</button>';
  $(".modal-foot [data-close]", m).addEventListener("click", m.close);
  const copy = (id, text) => { const b = $(id, m); if (b) b.addEventListener("click", () => { navigator.clipboard?.writeText(text); toast("Copiado", "success"); }); };
  copy("#copy-pix", d.qr_code || "");
  copy("#copy-boleto", d.barcode || "");
  clearInterval(orderPoll);
  orderPoll = setInterval(async () => {
    try {
      const o = await api(`/api/store/orders/${order.id}`);
      if (o.status === "pending") return;
      clearInterval(orderPoll);
      orderPoll = null;
      if (o.status === "paid") {
        S.cart = S.cart.filter((id) => !o.items.includes(id));
        saveCart();
        $("#co-body", m).innerHTML = `<div class="center" style="padding:30px;text-align:center"><div class="success-mark">${I.check}</div><h2>Pagamento aprovado!</h2><div class="muted">Seus cosméticos já estão no guarda-roupa.</div><button class="btn primary" style="margin-top:14px" data-act="nav" data-nav="wardrobe">${I.shirt} Abrir guarda-roupa</button></div>`;
        $("[data-nav=wardrobe]", m).addEventListener("click", m.close);
        await loadStore();
      } else {
        $("#co-body", m).innerHTML = `<div class="center"><h2>Pagamento não aprovado</h2><div class="muted">${esc(STATUS_LABEL[o.status] || o.status)}. Tente outra forma de pagamento.</div></div>`;
      }
    } catch { /* tenta de novo no próximo ciclo */ }
  }, 4000);
}

// ---- configurações
async function settingsModal() {
  const s = S.data.settings;
  const i = S.data.instance || {};
  const m = modal(`${head("Configurações")}
    <form class="modal-body form" id="set-form" style="max-width:none">
      <div class="field"><label>Memória do jogo</label>
        <div class="range-row"><input type="range" name="default_memory_mb" min="1024" max="16384" step="512" value="${s.default_memory_mb}" data-act="mem-range">
        <span class="value" id="mem-value">${(s.default_memory_mb / 1024).toFixed(1)} GB</span></div>
        <div class="hint">Para PvP, 2–4 GB costumam ser o ideal.</div></div>
      <div class="field"><label>Argumentos JVM extras</label><input class="input" name="jvm_args" value="${esc(i.jvm_args || "")}" placeholder="-XX:+UseG1GC"></div>
      <div class="field"><label>Resolução da janela</label><div class="row2">
        <input class="input" name="width" type="number" min="0" value="${i.width || ""}" placeholder="Largura (padrão)">
        <input class="input" name="height" type="number" min="0" value="${i.height || ""}" placeholder="Altura (padrão)"></div></div>
      <div class="field"><label>Downloads simultâneos</label><input class="input" type="number" name="download_workers" min="1" max="32" value="${s.download_workers}"></div>
      <div class="field"><label style="display:flex;gap:8px;align-items:center;font-weight:600"><input type="checkbox" name="auto_download_java" ${s.auto_download_java ? "checked" : ""}> Baixar Java automaticamente</label></div>
      <div class="field"><label>Client ID do Azure (login Microsoft)</label><input class="input" name="msa_client_id" value="${esc(s.msa_client_id || "")}" placeholder="00000000-0000-0000-0000-000000000000">
        <div class="hint">Necessário para contas Microsoft. Veja o README.</div></div>
      <h2 class="section" style="margin:6px 0 0">Avançado</h2>
      <div class="field"><label>Servidor da loja</label><input class="input" name="store_url" value="${esc(s.store_url || "")}"></div>
      <div class="field"><label>Mod SpkPvP (URL ou arquivo .jar)</label><input class="input" name="mod_url" value="${esc(s.mod_url || "")}" placeholder="Release mais recente do GitHub"></div>
      <div class="field"><label>Pasta de dados</label><div class="row2" style="grid-template-columns:1fr auto"><input class="input" value="${esc(S.data.data_dir)}" readonly><button type="button" class="btn" data-act="open-folder" data-sub="data">${I.folder}</button></div></div>
    </form>
    <div class="modal-foot"><span class="faint" style="margin-right:auto;align-self:center">SpkPvP Client ${esc(S.data.version)}</span><button class="btn" data-close>Cancelar</button><button class="btn primary" id="set-save">Salvar</button></div>`);
  $("#set-save", m).addEventListener("click", async () => {
    const f = $("#set-form", m);
    const fd = new FormData(f);
    const storeChanged = fd.get("store_url") !== s.store_url;
    try {
      await api("/api/settings", { method: "POST", body: {
        default_memory_mb: +fd.get("default_memory_mb"), download_workers: +fd.get("download_workers"),
        auto_download_java: f.auto_download_java.checked, msa_client_id: fd.get("msa_client_id"),
        store_url: fd.get("store_url"), mod_url: fd.get("mod_url") } });
      await api("/api/instance", { method: "POST", body: { jvm_args: fd.get("jvm_args"), width: fd.get("width"), height: fd.get("height") } });
      m.close();
      toast("Configurações salvas", "success");
      if (storeChanged) { S.catalog = null; S.me = null; loadStore(); }
    } catch (e) { fail(e); }
  });
}

// ------------------------------------------------------------------ ações
const act = {
  nav: (el) => go(el.dataset.nav),
  play: async () => {
    if (!S.data.accounts.length) { toast("Adicione uma conta para jogar", "error"); return accountsModal(); }
    try { const t = await api("/api/play", { method: "POST" }); S.tasks[t.id] = t; renderChrome(); renderView(); }
    catch (e) { fail(e); }
  },
  stop: async () => {
    if (await confirmDialog("Fechar o jogo", "Forçar o fechamento do Minecraft? O progresso não salvo será perdido.", "Fechar", true))
      api("/api/stop", { method: "POST" }).catch(fail);
  },
  "open-folder": (el) => api("/api/open-folder", { method: "POST", body: { sub: el.dataset.sub || "" } }).catch(fail),
  "open-browser": (el) => api("/api/open-url", { method: "POST", body: { url: el.dataset.url } }).catch(fail),
  "open-url": (el) => window.open(el.dataset.url, "_blank"),
  accounts: () => accountsModal(),
  "dismiss-task": (el) => { delete S.tasks[el.dataset.id]; renderTasks(); },
  "copy-logs": () => { navigator.clipboard?.writeText(S.logs.join("\n")); toast("Logs copiados", "success"); },
  "store-filter": (el) => { S.storeFilter = el.dataset.filter; renderView(); },
  "reload-store": () => { S.catalogError = null; S.catalog = null; renderView(); loadStore(); },
  "store-login": async (el) => {
    el.disabled = true;
    try { const r = await api("/api/store/login", { method: "POST" }); toast(`Conectado à loja como <b>${esc(r.name)}</b>`, "success"); S.data = await api("/api/state"); await loadStore(); }
    catch (e) { fail(e); el.disabled = false; }
  },
  "cart-add": (el) => {
    if (!S.cart.includes(el.dataset.id)) S.cart.push(el.dataset.id);
    saveCart(); renderChrome(); renderView();
    toast(`<b>${esc(item(el.dataset.id).name)}</b> adicionado ao carrinho`, "success", 2500);
  },
  "cart-remove": (el) => { S.cart = S.cart.filter((x) => x !== el.dataset.id); saveCart(); renderChrome(); renderView(); },
  checkout: () => checkoutModal(),
  equip: async (el) => {
    try {
      S.me = await api("/api/store/equip", { method: "POST", body: { slot: el.dataset.slot, cosmetic: el.dataset.id || null } });
      renderView();
      toast(S.data.running ? "Equipado! Aparece no jogo em até 1 minuto." : "Equipado!", "success", 2500);
    } catch (e) { fail(e); }
  },
};

document.addEventListener("click", (e) => {
  const el = e.target.closest("[data-act]");
  if (!el || el.tagName === "INPUT" || el.tagName === "SELECT") return;
  const fn = act[el.dataset.act];
  if (!fn) return;
  e.preventDefault();
  e.stopPropagation();
  fn(el, e);
});

document.addEventListener("change", async (e) => {
  const el = e.target;
  if (el.dataset.act === "toggle-module") {
    try {
      await api("/api/modules", { method: "POST", body: { id: el.dataset.id, enabled: el.checked } });
      S.modules.find((m) => m.id === el.dataset.id).enabled = el.checked;
      renderView();
    } catch (err) { fail(err); }
  }
});

document.addEventListener("input", (e) => {
  const el = e.target;
  if (el.dataset.act === "mem-range") $("#mem-value", el.closest("form")).textContent = (el.value / 1024).toFixed(1) + " GB";
});

$("#btn-settings").innerHTML = I.gear;
$("#btn-settings").addEventListener("click", settingsModal);
$("#btn-account").addEventListener("click", accountsModal);
$("#btn-cart").innerHTML = `${I.cart}<span class="cart-count" id="cart-count"></span>`;
$("#btn-cart").addEventListener("click", () => (S.cart.length ? checkoutModal() : go("store")));
document.querySelectorAll("#nav button").forEach((b) => b.addEventListener("click", () => go(b.dataset.nav)));

// ------------------------------------------------------------------ eventos do servidor
function connect() {
  const es = new EventSource(`/api/events?t=${TOKEN}`);
  let stateTimer;
  es.addEventListener("state", () => {
    clearTimeout(stateTimer);
    stateTimer = setTimeout(async () => {
      const before = S.data?.default_account + "|" + S.data?.store_logged;
      await refresh().catch(() => {});
      if (S.data.default_account + "|" + S.data.store_logged !== before) loadStore();
    }, 120);
  });
  es.addEventListener("task", (ev) => {
    const t = JSON.parse(ev.data);
    const prev = S.tasks[t.id];
    S.tasks[t.id] = t;
    renderTasks();
    if (t.status !== "running" && prev?.status === "running") {
      if (t.status === "error") toast(`<b>${esc(t.title)}</b> falhou: ${esc(t.message)}`, "error", 9000);
      if (t.status === "done") setTimeout(() => { delete S.tasks[t.id]; renderTasks(); }, 1500);
    }
    if (t.instance === PLAY_KEY && (!prev || prev.status !== t.status || prev.total !== t.total || t.total)) {
      $("#side-play").innerHTML = playButton(true);
      if (S.view === "home") { const h = $(".hero-actions"); if (h) h.lastElementChild.outerHTML = playButton(); }
    }
  });
  es.addEventListener("log", (ev) => {
    const { line } = JSON.parse(ev.data);
    S.logs.push(line);
    if (S.logs.length > 3000) S.logs.shift();
    if (S.view !== "logs") return;
    const c = $("#console");
    if (!c) return;
    if (c.querySelector(".faint")) c.innerHTML = "";
    const atBottom = c.scrollHeight - c.scrollTop - c.clientHeight < 40;
    const div = document.createElement("div");
    div.className = logClass(line);
    div.textContent = line;
    c.appendChild(div);
    while (c.childElementCount > 3000) c.firstChild.remove();
    if (atBottom) c.scrollTop = c.scrollHeight;
  });
  es.addEventListener("exit", (ev) => {
    const { code } = JSON.parse(ev.data);
    if (![0, 1, 130, 143, -15].includes(code)) toast(`O Minecraft fechou com erro (código ${code}). Veja os Logs.`, "error", 10000);
  });
  es.addEventListener("login", (ev) => onLoginEvent(JSON.parse(ev.data)));
  es.onerror = () => {};
}

// ------------------------------------------------------------------ início
renderView();
refresh().then(loadStore).catch((e) => {
  $("#view").innerHTML = `<div class="page"><div class="empty"><h2>Não foi possível conectar ao launcher</h2><div>${esc(e.message)}</div>
    <div class="faint" style="margin-top:8px">Abra o SpkPvP Client novamente pelo atalho ou com <code>python -m spkpvp</code>.</div></div></div>`;
});
connect();
