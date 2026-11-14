"use strict";
const $ = (s, r = document) => r.querySelector(s),
  $$ = (s, r = document) => [...r.querySelectorAll(s)];
const h = (v) =>
  String(v ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const paths = {
  dashboard: "M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z",
  report: "M6 3h9l4 4v14H6zM14 3v5h5M9 12h7M9 16h7",
  server: "M4 4h16v6H4zM4 14h16v6H4zM7 7h.01M7 17h.01",
  users:
    "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M16 3a4 4 0 0 1 0 8M22 21v-2a4 4 0 0 0-3-3.87M13 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0",
  menu: "M4 6h16M4 12h16M4 18h16",
  chevron: "m9 5 7 7-7 7",
  arrow: "M5 12h14m-5-5 5 5-5 5",
  download: "M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5",
  refresh: "M20 7v5h-5M4 17v-5h5M6 6a8 8 0 0 1 13 4M18 18A8 8 0 0 1 5 14",
  search: "m21 21-5-5M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0",
  plus: "M12 5v14M5 12h14",
  close: "m6 6 12 12M6 18 18 6",
  logout: "M10 17v4H3V3h7v4M8 12h13m-4-4 4 4-4 4",
  shield: "M12 3 3 7v6c0 5 9 9 9 9s9-4 9-9V7zM8 12l3 3 5-6",
  activity: "M2 12h4l3-8 5 16 3-8h5",
  check: "m5 12 4 4L19 6",
  eye: "M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0",
  clock: "M12 8v5l3 2M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0",
  edit: "m16 3 5 5-12 12-6 1 1-6zM14 5l5 5",
  key: "M14 7a5 5 0 1 0 0 6h3v-3h3V7z",
  info: "M12 11v6M12 7h.01M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0",
  trash: "M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7M14 10v7",
  network:
    "M8 3h8v6H8zM3 16h6v5H3zM15 16h6v5h-6zM12 9v4M6 13h12M6 13v3M18 13v3",
};
const icon = (name) =>
  `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="${paths[name] || paths.info}"/></svg>`;
const number = (n) => new Intl.NumberFormat("pt-BR").format(n || 0);
const date = (v, short = false) =>
  v
    ? new Intl.DateTimeFormat("pt-BR", {
        day: "2-digit",
        month: "2-digit",
        ...(short ? {} : { year: "numeric" }),
        hour: "2-digit",
        minute: "2-digit",
        second: short ? undefined : "2-digit",
      }).format(new Date(v))
    : "—";
const kinds = {
  "pppoe.authenticated": "Autenticação PPPoE",
  "pppoe.session.started": "Conexão estabelecida",
  "pppoe.session.ended": "Sessão encerrada",
  "ppp.user.created": "Cliente PPP criado",
  "ppp.user.updated": "Cliente PPP alterado",
  "ppp.user.deleted": "Cliente PPP removido",
  "ppp.user.enabled": "Cliente PPP ativado",
  "ppp.user.disabled": "Cliente PPP desativado",
  "routeros.admin.login": "Login administrativo",
  "routeros.admin.logout": "Logout administrativo",
  "routeros.admin_user.created": "Conta administrativa criada",
  "routeros.admin_user.updated": "Conta administrativa alterada",
  "routeros.admin_user.disabled": "Conta administrativa desativada",
};
const kind = (k) =>
  kinds[k] ||
  String(k || "Evento de sistema").replace(
    "routeros.configuration.",
    "Configuração · ",
  );
const shortSource = (s) => String(s || "").replace("mikrotik:", "");
let state = {
    user: null,
    csrf: "",
    days: 1,
    clients: [],
    users: [],
    page: 1,
    size: 25,
    total: 0,
    filters: {},
    collapsed: localStorage.getItem("logsai-nav") === "small",
  },
  refreshTimer;
function toast(message) {
  const el = $("#toast");
  el.textContent = message;
  el.classList.add("show");
  clearTimeout(el.timer);
  el.timer = setTimeout(() => el.classList.remove("show"), 5500);
}
async function api(path, options = {}) {
  const headers = {
    ...(options.body ? { "Content-Type": "application/json" } : {}),
    ...(options.method && options.method !== "GET"
      ? { "X-CSRF-Token": state.csrf }
      : {}),
    ...options.headers,
  };
  const r = await fetch("/api" + path, {
    ...options,
    headers,
    credentials: "same-origin",
  });
  if (!r.ok) {
    const j = await r
      .json()
      .catch(() => ({ detail: "Não foi possível concluir a operação." }));
    if (r.status === 401 && path !== "/auth/login") {
      state.user = null;
      loginView();
    }
    if (j.detail?.code === "password_change_required") {
      state.user.must_change_password = true;
      passwordView();
    }
    throw new Error(
      typeof j.detail === "string"
        ? j.detail
        : j.detail?.message || "Verifique os campos informados.",
    );
  }
  return options.raw ? r : r.json();
}
function brand() {
  return `<span class="brand-mark">≋</span><div class="brand-text">logs<span class="dot">.</span>ai<small>CENTRAL DE OBSERVABILIDADE</small></div>`;
}
function loginStory() {
  return `<div class="login-story"><div class="brand">${brand()}</div><div class="eyebrow">VISIBILIDADE PARA SUA REDE</div><h1>Cada evento.<br>Uma visão <span>mais clara.</span></h1><p>Conecte os pontos da sua operação com logs organizados, relatórios precisos e controle em um só lugar.</p><div class="login-mini"><span class="live-dot"></span><small>SUA OPERAÇÃO, EM PERSPECTIVA</small><svg viewBox="0 0 300 70" width="100%" height="90" aria-hidden="true">${[16, 25, 20, 40, 30, 47, 32, 55, 43, 63, 50, 37, 47, 65, 53, 59, 43, 68].map((v, i) => `<rect x="${i * 17}" y="${70 - v}" width="9" height="${v}" rx="3" fill="${i > 12 ? "#4dd4b5" : "#2b746d"}"/>`).join("")}</svg><small>Coleta privada · Acesso autenticado · Dados centralizados</small></div></div>`;
}
function passwordInput(name, label, autocomplete = "current-password") {
  return `<label for="${name}">${label}</label><div class="password-field"><input id="${name}" name="${name}" type="password" autocomplete="${autocomplete}" required maxlength="128"><button type="button" class="icon-button toggle-password" aria-label="Mostrar senha">${icon("eye")}</button></div>`;
}
function bindPasswords(root = document) {
  $$(".toggle-password", root).forEach(
    (b) =>
      (b.onclick = () => {
        const input = $("input", b.parentElement);
        input.type = input.type === "password" ? "text" : "password";
        b.setAttribute(
          "aria-label",
          input.type === "password" ? "Mostrar senha" : "Ocultar senha",
        );
      }),
  );
}
function loginView() {
  clearInterval(refreshTimer);
  $("#app").innerHTML =
    `<div class="login-shell">${loginStory()}<div class="login-form-side"><div class="login-form"><div class="brand">${brand()}</div><div class="eyebrow">BEM-VINDO À SUA CENTRAL</div><h1>Entre na sua operação</h1><p>Acompanhe sua rede. Encontre o que importa.</p><form id="login-form"><div id="login-error"></div><div class="form-field"><label for="username">Usuário</label><input id="username" name="username" autocomplete="username" placeholder="Seu usuário" required maxlength="48"></div><div class="form-field">${passwordInput("password", "Senha")}</div><button class="btn primary" type="submit">Entrar na central ${icon("arrow")}</button></form><div class="login-footer">${icon("shield")} Ambiente protegido · logs-ai</div></div></div></div>`;
  bindPasswords();
  $("#login-form").onsubmit = async (e) => {
    e.preventDefault();
    const b = $("button[type=submit]", e.target);
    b.disabled = true;
    try {
      const v = await api("/auth/login", {
        method: "POST",
        body: JSON.stringify(Object.fromEntries(new FormData(e.target))),
      });
      state.user = v.user;
      state.csrf = v.csrf;
      e.target.reset();
      if (state.user.must_change_password) passwordView();
      else navigate("/");
    } catch (err) {
      $("#login-error").innerHTML =
        `<div class="form-error" role="alert">${h(err.message)}</div>`;
    } finally {
      b.disabled = false;
    }
  };
}
function passwordView(optional = false) {
  clearInterval(refreshTimer);
  $("#app").innerHTML =
    `<div class="login-shell">${loginStory()}<div class="login-form-side"><div class="login-form"><div class="brand">${brand()}</div><div class="eyebrow">SEGURANÇA DA SUA CONTA</div><h1>${optional ? "Altere sua senha" : "Uma senha só sua"}</h1><p>${optional ? "Escolha uma nova senha para proteger seu acesso." : "Antes de continuar, substitua a senha temporária do seu primeiro acesso."}</p><form id="password-form"><div id="password-error"></div><div class="form-field">${passwordInput("current_password", "Senha atual")}</div><div class="form-field">${passwordInput("new_password", "Nova senha", "new-password")}<p class="form-hint">12 a 128 caracteres. Combine três tipos entre letras maiúsculas, minúsculas, números e símbolos.</p></div><div class="form-field">${passwordInput("confirm_password", "Confirme a nova senha", "new-password")}</div><button type="submit" class="btn primary">Salvar e continuar ${icon("arrow")}</button></form><button id="password-back" class="btn ghost">${optional ? "Voltar ao dashboard" : "Sair da conta"}</button></div></div></div>`;
  bindPasswords();
  $("#password-back").onclick = () => (optional ? navigate("/") : logout());
  $("#password-form").onsubmit = async (e) => {
    e.preventDefault();
    const values = Object.fromEntries(new FormData(e.target));
    if (values.new_password !== values.confirm_password) {
      $("#password-error").innerHTML =
        '<div class="form-error">As novas senhas não coincidem.</div>';
      return;
    }
    const b = $("button[type=submit]", e.target);
    b.disabled = true;
    try {
      const v = await api("/auth/password", {
        method: "POST",
        body: JSON.stringify(values),
      });
      state.csrf = v.csrf;
      state.user.must_change_password = false;
      e.target.reset();
      toast("Sua senha foi atualizada.");
      navigate("/");
    } catch (err) {
      $("#password-error").innerHTML =
        `<div class="form-error">${h(err.message)}</div>`;
    } finally {
      b.disabled = false;
    }
  };
}
const nav = [
  ["/", "dashboard", "Dashboard"],
  ["/relatorios", "report", "Relatórios"],
  ["/clientes", "server", "Clientes rsyslog"],
  ["/usuarios", "users", "Usuários"],
];
function layout() {
  const active = nav.find((n) => n[0] === location.pathname) || nav[0];
  $("#app").innerHTML =
    `<div class="layout ${state.collapsed ? "collapsed" : ""}"><aside class="sidebar"><a href="/" class="brand">${brand()}</a><div class="nav-caption">WORKSPACE</div><nav>${nav
      .filter(
        (n) =>
          state.user.role === "admin" || ["/", "/relatorios"].includes(n[0]),
      )
      .map(
        (n) =>
          `<a href="${n[0]}" class="nav-item ${n[0] === active[0] ? "active" : ""}" title="${n[2]}">${icon(n[1])}<span class="nav-text">${n[2]}</span></a>`,
      )
      .join(
        "",
      )}</nav><div class="nav-bottom"><div class="nav-server"><span class="live-dot"></span><b>Coleta privada TCP / CEF</b><br><span class="muted">MikroTik RouterOS 7</span></div><button id="account-password" class="nav-item">${icon("shield")}<span class="nav-text">Minha senha</span></button><button id="logout" class="nav-item">${icon("logout")}<span class="nav-text">Sair da conta</span></button></div></aside><main class="main"><header class="topbar"><div class="top-left"><button id="nav-toggle" class="icon-button" aria-label="Recolher ou expandir menu" aria-expanded="${!state.collapsed}">${icon("menu")}</button><span class="divider"></span><div class="breadcrumb"><span class="mobile-hide">Workspace <span class="muted">/</span> </span><b>${active[2]}</b></div></div><div class="top-right"><span class="status-pill mobile-hide" id="connection-status"><span class="live-dot"></span>Central conectada</span><span class="divider mobile-hide"></span><div class="avatar">${h(state.user.username.slice(0, 2).toUpperCase())}</div><div class="user-name mobile-hide">${h(state.user.username)}<small>${state.user.role === "admin" ? "Administrador" : "Visualizador"}</small></div></div></header><div class="content"><div id="page"><div class="loading">Carregando sua operação…</div></div><footer class="footer"><span>logs.ai <span class="muted">/</span> Sua rede, em perspectiva.</span><span>Coleta privada <span class="muted">·</span> Acesso seguro</span></footer></div></main></div>`;
  $("#nav-toggle").onclick = () => {
    if (innerWidth < 1000) {
      $(".sidebar").classList.toggle("open");
      let overlay = $(".overlay");
      if (overlay) overlay.remove();
      else {
        overlay = document.createElement("div");
        overlay.className = "overlay";
        overlay.onclick = () => {
          $(".sidebar").classList.remove("open");
          overlay.remove();
        };
        $("#app").append(overlay);
      }
    } else {
      state.collapsed = !state.collapsed;
      $(".layout").classList.toggle("collapsed", state.collapsed);
      localStorage.setItem("logsai-nav", state.collapsed ? "small" : "large");
      $("#nav-toggle").setAttribute("aria-expanded", String(!state.collapsed));
    }
  };
  $$('a[href^="/"]', $("#app")).forEach(
    (a) =>
      (a.onclick = (e) => {
        e.preventDefault();
        navigate(a.getAttribute("href"));
      }),
  );
  $("#logout").onclick = logout;
  $("#account-password").onclick = () => passwordView(true);
}
async function logout() {
  try {
    await api("/auth/logout", { method: "POST" });
  } catch {}
  state.user = null;
  state.csrf = "";
  history.replaceState(null, "", "/");
  loginView();
}
function navigate(path) {
  if (location.pathname !== path) history.pushState(null, "", path);
  render();
}
async function render() {
  if (!state.user) return loginView();
  if (state.user.must_change_password) return passwordView();
  clearInterval(refreshTimer);
  layout();
  try {
    if (location.pathname === "/relatorios") await reportsPage();
    else if (location.pathname === "/clientes" && state.user.role === "admin")
      await clientsPage();
    else if (location.pathname === "/usuarios" && state.user.role === "admin")
      await usersPage();
    else {
      await dashboard();
      refreshTimer = setInterval(() => {
        if (!document.hidden && location.pathname === "/")
          dashboard(true).catch(() => {});
      }, 30000);
    }
  } catch (err) {
    if ($("#page"))
      $("#page").innerHTML =
        `<div class="error-box">${h(err.message)} <button class="btn" id="retry">Tentar novamente</button></div>`;
    if ($("#retry")) $("#retry").onclick = render;
  }
}
function eventRow(row, report = false) {
  const label = kind(row.event_kind),
    isEnd =
      row.event_kind?.includes("ended") || row.event_kind?.includes("logout"),
    isChange =
      row.event_kind?.includes("user.") ||
      row.event_kind?.includes("configuration");
  const badge = isEnd
    ? "gray"
    : isChange
      ? "blue"
      : row.severity <= 3
        ? "amber"
        : "";
  return `<tr><td><span class="event-cell"><span class="event-symbol ${isChange ? "blue" : isEnd ? "orange" : ""}">${icon(isChange ? "edit" : isEnd ? "logout" : "activity")}</span><span><span class="cell-title">${h(label)}</span><small>${h(row.event_kind || "Evento de sistema")}</small></span></span></td><td class="mono">${h(row.source_name || "Origem não cadastrada")}</td><td>${h(row.username || row.actor || "—")}</td>${report ? `<td class="mono">${h(row.pppoe_ip || "—")}</td><td class="message-cell" title="${h(row.message)}">${h(row.message)}</td>` : ""}${report ? "" : `<td><span class="badge ${badge}">${isEnd ? "Encerramento" : isChange ? "Alteração" : row.severity <= 3 ? "Atenção" : "Informativo"}</span></td>`}<td>${h(date(row.received_at, true))}</td></tr>`;
}
function table(rows, report = false) {
  return `<div class="table-wrap"><table class="data-table"><thead><tr><th>Evento</th><th>Origem</th><th>Usuário / ator</th>${report ? "<th>IP PPPoE</th><th>Mensagem</th>" : "<th>Categoria</th>"}<th>Recebido em</th></tr></thead><tbody>${rows.length ? rows.map((r) => eventRow(r, report)).join("") : `<tr><td colspan="${report ? 6 : 5}"><div class="empty">${icon("report")}<strong>Nenhum evento neste período</strong>Novos registros aparecerão aqui conforme forem recebidos.</div></td></tr>`}</tbody></table></div>`;
}
function chart(trend, days) {
  const now = Date.now(),
    step = days === 1 ? 3600000 : 86400000,
    n = days === 1 ? 25 : days + 1;
  const aligned = Math.floor(now / step) * step;
  const vals = Array.from({ length: n }, (_, i) => {
    const t = aligned - (n - 1 - i) * step;
    return {
      time: t,
      count: Number(
        trend.find(
          (p) => Math.floor(new Date(p.time).getTime() / step) * step === t,
        )?.count || 0,
      ),
    };
  });
  const max = Math.max(4, ...vals.map((v) => v.count));
  const points = vals.map((v, i) => [
    42 + (i * 660) / Math.max(1, n - 1),
    175 - (v.count / max) * 140,
  ]);
  let d = points
    .map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(1)},${p[1].toFixed(1)}`)
    .join(" ");
  return `<svg class="chart" viewBox="0 0 735 215" role="img" aria-label="Volume de eventos no período"><defs><linearGradient id="chart-area" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#5d8cf4" stop-opacity=".23"/><stop offset="100%" stop-color="#5d8cf4" stop-opacity=".01"/></linearGradient></defs>${[0, 1, 2, 3, 4].map((i) => `<line class="chart-grid" x1="40" y1="${35 + i * 35}" x2="710" y2="${35 + i * 35}"/><text x="28" y="${38 + i * 35}" text-anchor="end">${Math.round((max * (4 - i)) / 4)}</text>`).join("")}<path d="${d} L702,177 L42,177 Z" fill="url(#chart-area)"/><path d="${d}" fill="none" stroke="#6088ed" stroke-width="2.3" stroke-linejoin="round"/>${vals.map((v, i) => (i % (days === 1 ? 4 : Math.max(1, Math.floor(n / 6))) === 0 ? `<text x="${points[i][0]}" y="202" text-anchor="middle">${h(new Intl.DateTimeFormat("pt-BR", days === 1 ? { hour: "2-digit" } : { day: "2-digit", month: "2-digit" }).format(v.time))}</text>` : "")).join("")}</svg>`;
}
async function dashboard(silent = false) {
  const data = await api("/dashboard?days=" + state.days);
  if (location.pathname !== "/") return;
  const n = data.counts,
    delta = data.previous
      ? Math.round(((n.total - data.previous) / data.previous) * 100)
      : null;
  $("#page").innerHTML =
    `<div class="page-head"><div><div class="eyebrow">VISÃO GERAL DA OPERAÇÃO</div><h1>Dashboard</h1><p>O que acontece na sua rede, em uma visão.</p></div><div class="actions"><select id="days" class="period-select" aria-label="Período"><option value="1" ${state.days === 1 ? "selected" : ""}>Últimas 24 horas</option><option value="7" ${state.days === 7 ? "selected" : ""}>Últimos 7 dias</option><option value="30" ${state.days === 30 ? "selected" : ""}>Últimos 30 dias</option></select><button class="btn" id="dash-refresh">${icon("refresh")} Atualizar</button></div></div><div class="stats">${[
      [
        n.total,
        "Eventos recebidos",
        "activity",
        "",
        delta === null
          ? "Sem comparação anterior"
          : `${delta >= 0 ? "+" : ""}${delta}% em relação ao período anterior`,
      ],
      [
        n.authentications,
        "Autenticações PPPoE",
        "shield",
        "teal",
        "Autenticações bem-sucedidas",
      ],
      [
        n.sources,
        "Origens enviando logs",
        "network",
        "violet",
        `${data.configured_clients} clientes configurados ativos`,
      ],
      [
        n.critical,
        "Eventos críticos",
        "info",
        "amber",
        n.critical ? "Severidade de 0 a 3" : "Nenhum evento crítico no período",
      ],
    ]
      .map(
        ([value, label, ic, color, note]) =>
          `<article class="stat"><div class="stat-top"><span>${label}</span><span class="stat-icon ${color}">${icon(ic)}</span></div><div class="stat-value">${number(value)}</div><div class="stat-note">${h(note)}</div></article>`,
      )
      .join(
        "",
      )}</div><div class="dashboard-charts"><section class="card"><div class="card-head"><div><h2>Volume de eventos</h2><p>Distribuição dos registros recebidos no período</p></div><span class="chart-legend"><i></i> Eventos</span></div><div class="card-body">${chart(data.trend, state.days)}</div></section><section class="card"><div class="card-head"><div><h2>Principais origens</h2><p>Quem está enviando dados para a central</p></div>${icon("server")}</div><div class="card-body">${
      data.sources.length
        ? data.sources
            .slice(0, 5)
            .map(
              (s, i) =>
                `<div class="source-row"><div class="source-label"><span class="mono">${h(shortSource(s.source))}</span><strong>${number(s.count)} <span class="muted">eventos</span></strong></div><svg class="source-bar" viewBox="0 0 300 6" preserveAspectRatio="none"><rect width="300" height="6" rx="3" fill="#eef2f7"/><rect width="${Math.max(2, (Number(s.count) / Math.max(1, n.total)) * 300)}" height="6" rx="3" fill="${["#51bea7", "#7294eb", "#b69ce4", "#e8bd70", "#91acbf"][i]}"/></svg></div>`,
            )
            .join("")
        : '<div class="empty">Aguardando a primeira origem.</div>'
    }<div class="sources-foot">${icon("clock")} Atualização automática a cada 30 segundos</div></div></section></div><section class="card"><div class="card-head"><div><h2>Atividade recente</h2><p>Os últimos eventos recebidos pela sua central</p></div><a class="table-link" href="/relatorios" id="all-reports">Ver todos ${icon("arrow")}</a></div><div class="card-body"></div>${table(data.recent)}<div class="table-footer"><span>Mostrando os ${data.recent.length} eventos mais recentes</span><span><span class="live-dot"></span> Atualizado às ${h(new Intl.DateTimeFormat("pt-BR", { hour: "2-digit", minute: "2-digit" }).format(new Date(data.generated_at)))}</span></div></section>`;
  $("#days").onchange = (e) => {
    state.days = Number(e.target.value);
    dashboard();
  };
  $("#dash-refresh").onclick = () =>
    dashboard().catch((err) => toast(err.message));
  $("#all-reports").onclick = (e) => {
    e.preventDefault();
    navigate("/relatorios");
  };
  if (!silent) document.title = "Dashboard · logs-ai";
}
function localInput(d) {
  const value = new Date(d);
  return new Date(value.getTime() - value.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 16);
}
async function reportsPage() {
  const options = await api("/report-options");
  if (!state.filters.from) {
    state.filters.from = new Date(Date.now() - 86400000).toISOString();
    state.filters.to = new Date().toISOString();
  }
  $("#page").innerHTML =
    `<div class="page-head"><div><div class="eyebrow">EXPLORE SEUS DADOS</div><h1>Relatórios</h1><p>Encontre eventos, refine sua busca e leve os dados com você.</p></div><div class="actions"><button id="export-csv" class="btn">${icon("download")} CSV</button><button id="export-pdf" class="btn primary">${icon("download")} PDF</button></div></div><section class="card"><form id="filters-form"><div class="filters"><div><label class="filter-label" for="filter-q">Buscar evento, usuário ou ator</label><div class="search-box">${icon("search")}<input id="filter-q" name="q" placeholder="O que você procura?" value="${h(state.filters.q || "")}" maxlength="160"></div></div><div><label class="filter-label" for="filter-source">Origem</label><select id="filter-source" name="source"><option value="">Todas as origens</option>${options.sources.map((s) => `<option value="${h(s)}" ${state.filters.source === s ? "selected" : ""}>${h(options.source_names[s] || "Origem não cadastrada")}</option>`).join("")}</select></div><div><label class="filter-label" for="filter-kind">Tipo de evento</label><select id="filter-kind" name="kind"><option value="">Todos os tipos</option>${options.kinds.map((k) => `<option value="${h(k)}" ${state.filters.kind === k ? "selected" : ""}>${h(kind(k))}</option>`).join("")}</select></div><div><label class="filter-label" for="filter-severity">Severidade</label><select id="filter-severity" name="severity"><option value="">Todas</option>${["Emergência", "Alerta", "Crítico", "Erro", "Aviso", "Notificação", "Informativo", "Debug"].map((s, i) => `<option value="${i}" ${state.filters.severity === String(i) ? "selected" : ""}>${s}</option>`).join("")}</select></div><div><label class="filter-label" for="filter-from">Data inicial</label><input type="datetime-local" id="filter-from" name="from" value="${localInput(state.filters.from)}" required></div><div><label class="filter-label" for="filter-to">Data final</label><input type="datetime-local" id="filter-to" name="to" value="${localInput(state.filters.to)}" required></div></div><div class="filter-bottom"><span class="small muted">Horários no seu fuso local · intervalo máximo de 93 dias</span><div class="actions"><button type="button" id="clear-filters" class="btn ghost">Limpar filtros</button><button type="submit" class="btn primary">${icon("search")} Aplicar filtros</button></div></div></form></section><section class="card" id="results-card"><div class="loading">Consultando eventos…</div></section><p class="form-hint">CSV: até 10.000 eventos · PDF: até 2.000. Uma exportação limitada é identificada no arquivo ou no aviso de download.</p>`;
  $("#results-card").classList.add("results");
  $("#filters-form").onsubmit = async (e) => {
    e.preventDefault();
    state.filters = Object.fromEntries(new FormData(e.target));
    state.filters.from = new Date(state.filters.from).toISOString();
    state.filters.to = new Date(state.filters.to).toISOString();
    state.page = 1;
    await loadResults().catch((err) => toast(err.message));
  };
  $("#clear-filters").onclick = () => {
    state.filters = {};
    state.page = 1;
    reportsPage();
  };
  $("#export-csv").onclick = () => downloadReport("csv");
  $("#export-pdf").onclick = () => downloadReport("pdf");
  await loadResults();
  document.title = "Relatórios · logs-ai";
}
async function loadResults() {
  const params = new URLSearchParams({
    ...state.filters,
    page: state.page,
    page_size: state.size,
  });
  const result = await api("/reports?" + params);
  state.total = result.total;
  const pages = Math.max(1, Math.ceil(result.total / state.size));
  $("#results-card").innerHTML =
    `<div class="card-head"><div><h2>Eventos encontrados <span class="badge blue">${number(result.total)}</span></h2><p>Registros conforme os filtros aplicados</p></div></div><div class="card-body"></div>${table(result.items, true)}<div class="table-footer"><span>${result.total ? number((state.page - 1) * state.size + 1) : 0}–${number(Math.min(state.page * state.size, result.total))} de ${number(result.total)} eventos</span><div class="pagination"><label for="page-size" class="muted">Por página</label><select id="page-size" class="page-size">${[10, 25, 50, 100].map((v) => `<option ${v === state.size ? "selected" : ""}>${v}</option>`).join("")}</select><button class="page-btn" id="prev-page" aria-label="Página anterior" ${state.page <= 1 ? "disabled" : ""}>‹</button><span class="page-btn active">${state.page}</span><span>de ${number(pages)}</span><button class="page-btn" id="next-page" aria-label="Próxima página" ${state.page >= pages ? "disabled" : ""}>›</button></div></div>`;
  $("#prev-page").onclick = () => {
    state.page--;
    loadResults().catch((err) => toast(err.message));
  };
  $("#next-page").onclick = () => {
    state.page++;
    loadResults().catch((err) => toast(err.message));
  };
  $("#page-size").onchange = (e) => {
    state.size = Number(e.target.value);
    state.page = 1;
    loadResults().catch((err) => toast(err.message));
  };
}
async function downloadReport(format) {
  try {
    const response = await api(
      "/reports/export/" + format + "?" + new URLSearchParams(state.filters),
      { raw: true },
    );
    const blob = await response.blob(),
      url = URL.createObjectURL(blob),
      a = document.createElement("a");
    a.href = url;
    a.download =
      response.headers
        .get("Content-Disposition")
        ?.match(/filename="([^"]+)"/)?.[1] || "logs-ai-relatorio." + format;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    toast(
      response.headers.get("X-Export-Truncated") === "true"
        ? `Exportados ${response.headers.get("X-Export-Count")} de ${response.headers.get("X-Result-Total")} eventos. Refine os filtros para exportar o restante.`
        : "Relatório exportado.",
    );
  } catch (err) {
    toast(err.message);
  }
}
async function clientsPage() {
  const data = await api("/clients");
  state.clients = data.items;
  $("#page").innerHTML =
    `<div class="page-head"><div><div class="eyebrow">FONTES DA SUA OPERAÇÃO</div><h1>Clientes rsyslog</h1><p>Gerencie as origens MikroTik RouterOS 7 da sua central.</p></div><button id="new-client" class="btn primary">${icon("plus")} Novo cliente</button></div><div class="notice">${icon("network")}<span>Receptor privado <b class="mono">${h(data.receiver)}:${data.port}</b> · TCP / CEF. Cadastros ativos autorizam o IP de origem; novas conexões refletem as alterações em até 3 segundos.</span></div><div class="client-grid">${data.items.map((c) => `<article class="card client-card"><div class="client-top"><span class="client-icon">${icon("server")}</span><div><h2>${h(c.name)}</h2><span class="mono muted">${h(c.source_ip)}</span></div><span class="badge ${c.enabled ? "" : "gray"}">${c.enabled ? "Ativo" : "Inativo"}</span></div><div class="client-info"><div><span>PLATAFORMA</span><b>MikroTik RouterOS 7</b></div><div><span>COLETA</span><b>TCP / CEF</b></div><div><span>PORTA SSH</span><b>${c.ssh_port}</b></div><div><span>ÚLTIMO EVENTO</span><b>${h(date(c.last_seen, true))}</b></div></div><div class="client-actions"><button class="btn client-edit" data-id="${c.id}">${icon("edit")} Editar</button><button class="btn client-download" data-id="${c.id}">${icon("download")} Script</button><button class="btn primary client-apply" data-id="${c.id}">${icon("arrow")} Aplicar SSH</button></div><p class="client-status">${c.last_apply_status === "success" ? "✓ Configuração aplicada em " + h(date(c.last_applied_at, true)) : c.last_apply_status === "failed" ? "Última aplicação não concluída. Confira o acesso SSH." : "Configuração pronta para download ou aplicação remota."}</p></article>`).join("") || '<div class="card empty">' + icon("server") + "<strong>Nenhum cliente cadastrado</strong>Adicione seu primeiro MikroTik para começar.</div>"}</div>`;
  $("#new-client").onclick = () => clientModal();
  $$(".client-edit").forEach(
    (b) =>
      (b.onclick = () =>
        clientModal(state.clients.find((c) => c.id === Number(b.dataset.id)))),
  );
  $$(".client-download").forEach(
    (b) => (b.onclick = () => configDownload(b.dataset.id)),
  );
  $$(".client-apply").forEach(
    (b) =>
      (b.onclick = () =>
        applyModal(state.clients.find((c) => c.id === Number(b.dataset.id)))),
  );
  document.title = "Clientes rsyslog · logs-ai";
}
function modal(title, subtitle, body, footer) {
  $("#modal-root").innerHTML =
    `<div class="modal-backdrop"><section class="modal" role="dialog" aria-modal="true" aria-label="${h(title)}"><div class="modal-head"><div><h2>${h(title)}</h2><p>${h(subtitle)}</p></div><button class="icon-button close-modal" aria-label="Fechar">${icon("close")}</button></div><div class="modal-body">${body}</div><div class="modal-footer">${footer}</div></section></div>`;
  $$(".close-modal").forEach((b) => (b.onclick = closeModal));
  $(".modal-backdrop").onclick = (e) => {
    if (e.target === $(".modal-backdrop")) closeModal();
  };
  document.body.style.overflow = "hidden";
  setTimeout(() => $("input", $("#modal-root"))?.focus(), 0);
  bindPasswords($("#modal-root"));
}
function closeModal() {
  $("#modal-root").innerHTML = "";
  document.body.style.overflow = "";
}
function field(name, label, value = "", type = "text", extra = "") {
  return `<div class="form-field"><label for="${name}">${label}</label><input id="${name}" name="${name}" type="${type}" value="${h(value)}" ${extra}></div>`;
}
function clientModal(c = {}) {
  modal(
    c.id ? "Editar cliente" : "Novo cliente",
    "Configuração da origem MikroTik",
    `<form id="client-form"><div id="client-error"></div><div class="modal-grid">${field("name", "Nome do cliente", c.name || "", "text", 'required maxlength="80"')}${field("source_ip", "IPv4 privado de origem", c.source_ip || "", "text", 'required placeholder="Ex.: 192.168.10.1"')}${field("ssh_port", "Porta SSH", c.ssh_port || 22, "number", 'required min="1" max="65535"')}${field("ssh_username", "Usuário SSH", c.ssh_username || "", "text", 'autocomplete="off" maxlength="64"')}${field("action_name", "Nome da ação RouterOS", c.action_name || "logsaiPrivate", "text", 'required pattern="[A-Za-z0-9]{1,32}" maxlength="32"')}<div class="form-field"><label for="host_fingerprint">Fingerprint SSH confirmado</label><input class="fingerprint" id="host_fingerprint" name="host_fingerprint" value="${h(c.host_fingerprint || "")}" placeholder="SHA256:…" maxlength="60"><p class="form-hint">Confirme por um canal independente. Obrigatório para aplicação remota.</p>${c.id ? '<button type="button" class="btn" id="probe-key">Consultar chave observada</button><p id="probe-key-result" class="form-hint"></p>' : ""}</div><div class="form-field full"><label for="notes">Observações</label><textarea id="notes" name="notes" maxlength="300">${h(c.notes || "")}</textarea></div></div><div class="check-line"><input type="checkbox" name="enabled" id="enabled" ${c.enabled !== false ? "checked" : ""}><label for="enabled">Permitir o recebimento de logs desta origem</label></div></form>`,
    `${c.id ? `<button id="delete-client" class="btn danger">${icon("trash")} Excluir</button><button id="remove-config" class="btn">Script de reversão</button>` : ""}<button class="btn close-modal">Cancelar</button><button type="submit" form="client-form" class="btn primary">Salvar cliente</button>`,
  );
  if (c.id) {
    $("#probe-key").onclick = async () => {
      const b = $("#probe-key");
      b.disabled = true;
      try {
        const v = await api("/clients/" + c.id + "/ssh-key", {
          method: "POST",
        });
        $("#probe-key-result").textContent =
          "Chave observada: " +
          v.fingerprint +
          ". Compare por canal independente antes de copiar para o campo confirmado. Não foi salva automaticamente.";
      } catch (err) {
        $("#probe-key-result").textContent = err.message;
      } finally {
        b.disabled = false;
      }
    };
    $("#delete-client").onclick = async () => {
      if (
        !confirm(
          "Excluir o cadastro desta origem? Isso não remove a configuração do roteador.",
        )
      )
        return;
      try {
        await api("/clients/" + c.id, { method: "DELETE" });
        closeModal();
        await clientsPage();
        toast("Cadastro removido.");
      } catch (err) {
        toast(err.message);
      }
    };
    $("#remove-config").onclick = () => configDownload(c.id, "remove");
  }
  $("#client-form").onsubmit = async (e) => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(e.target));
    data.enabled = $("#enabled").checked;
    data.ssh_port = Number(data.ssh_port);
    try {
      await api("/clients" + (c.id ? "/" + c.id : ""), {
        method: c.id ? "PUT" : "POST",
        body: JSON.stringify(data),
      });
      closeModal();
      await clientsPage();
      toast("Cliente salvo.");
    } catch (err) {
      $("#client-error").innerHTML =
        `<div class="form-error">${h(err.message)}</div>`;
    }
  };
}
async function configDownload(id, operation = "install") {
  try {
    const r = await api("/clients/" + id + "/config/" + operation, {
      raw: true,
    });
    const url = URL.createObjectURL(await r.blob()),
      a = document.createElement("a");
    a.href = url;
    a.download = "logs-ai-" + id + "-" + operation + ".rsc";
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    toast("Script gerado. Revise antes de importar no RouterOS.");
  } catch (err) {
    toast(err.message);
  }
}
function applyModal(c) {
  modal(
    "Aplicar configuração por SSH",
    `${c.name} · ${c.source_ip}:${c.ssh_port}`,
    `<div class="notice amber">${icon("shield")}<span>A ação instala somente as regras desta integração. Configurações conflitantes são recusadas. A senha SSH não é armazenada.</span></div><form id="apply-form"><div id="apply-error"></div><div class="form-field"><label>Chave do host</label><div class="mono fingerprint">${h(c.host_fingerprint || "Não configurada — edite o cliente antes de aplicar.")}</div></div>${field("ssh-user", "Usuário SSH", c.ssh_username || "", "text", 'required autocomplete="off"')}<div class="form-field">${passwordInput("ssh-password", "Senha SSH", "off")}</div><div class="check-line"><input id="apply-confirm" type="checkbox" required><label for="apply-confirm">Conferi o fingerprint por um canal independente e autorizo aplicar neste roteador.</label></div></form>`,
    `<button class="btn close-modal">Cancelar</button><button class="btn primary" id="apply-submit" type="submit" form="apply-form" ${c.host_fingerprint ? "" : "disabled"}>${icon("arrow")} Aplicar no MikroTik</button>`,
  );
  $("#apply-form").onsubmit = async (e) => {
    e.preventDefault();
    const button = $("#apply-submit");
    button.disabled = true;
    button.innerHTML = '<span class="spinner"></span> Aplicando…';
    const data = {
      username: $("#ssh-user").value,
      password: $("#ssh-password").value,
      confirm: $("#apply-confirm").checked,
    };
    $("#ssh-password").value = "";
    try {
      await api("/clients/" + c.id + "/apply", {
        method: "POST",
        body: JSON.stringify(data),
      });
      closeModal();
      await clientsPage();
      toast("Configuração aplicada. Confira a chegada de novos eventos.");
    } catch (err) {
      $("#apply-error").innerHTML =
        `<div class="form-error">${h(err.message)}</div>`;
      button.disabled = false;
      button.innerHTML = "Aplicar no MikroTik";
    } finally {
      data.password = "";
    }
  };
}
async function usersPage() {
  state.users = await api("/users");
  $("#page").innerHTML =
    `<div class="page-head"><div><div class="eyebrow">ACESSO E RESPONSABILIDADE</div><h1>Usuários</h1><p>As pessoas que acompanham e administram sua operação.</p></div><button class="btn primary" id="new-user">${icon("plus")} Novo usuário</button></div><section class="card"><div class="card-head"><div><h2>Equipe da central <span class="badge blue">${state.users.length}</span></h2><p>Gerencie permissões e acesso à plataforma</p></div>${icon("users")}</div><div class="card-body"></div><div class="table-wrap"><table class="data-table"><thead><tr><th>Usuário</th><th>Perfil</th><th>Status</th><th>Último acesso</th><th>Segurança</th><th>Ações</th></tr></thead><tbody>${state.users.map((u) => `<tr><td><div class="event-cell"><span class="avatar">${h(u.username.slice(0, 2).toUpperCase())}</span><span class="cell-title">${h(u.username)} ${u.id === state.user.id ? '<span class="muted small">(você)</span>' : ""}</span></div></td><td><span class="badge ${u.role === "admin" ? "blue" : "gray"}">${u.role === "admin" ? "Administrador" : "Visualizador"}</span></td><td><span class="badge ${u.active ? "" : "gray"}">${u.active ? "Ativo" : "Desativado"}</span></td><td>${h(date(u.last_login, true))}</td><td>${u.must_change_password ? '<span class="badge amber">Troca de senha pendente</span>' : '<span class="muted">Senha pessoal</span>'}</td><td><button class="icon-button user-edit" data-id="${u.id}" aria-label="Editar ${h(u.username)}">${icon("edit")}</button></td></tr>`).join("")}</tbody></table></div><div class="table-footer"><span>Administradores gerenciam clientes e usuários. Visualizadores consultam e exportam relatórios.</span></div></section>`;
  $("#new-user").onclick = () => userModal();
  $$(".user-edit").forEach(
    (b) =>
      (b.onclick = () =>
        userModal(state.users.find((u) => u.id === Number(b.dataset.id)))),
  );
  document.title = "Usuários · logs-ai";
}
function userModal(u = {}) {
  modal(
    u.id ? "Editar usuário" : "Novo usuário",
    "Acesso seguro à sua central de logs",
    `<form id="user-form"><div id="user-error"></div>${field("user-username", "Nome de usuário", u.username || "", "text", 'required autocomplete="off" pattern="[A-Za-z](?:[A-Za-z0-9_.]|-){2,47}" maxlength="48"')}<div class="form-field"><label for="role">Perfil de acesso</label><select name="role" id="role"><option value="viewer" ${u.role !== "admin" ? "selected" : ""}>Visualizador — consultar e exportar</option><option value="admin" ${u.role === "admin" ? "selected" : ""}>Administrador — acesso completo</option></select></div><div class="form-field">${passwordInput("temp-password", u.id ? "Nova senha temporária (opcional)" : "Senha temporária", "new-password")}<p class="form-hint">Mínimo de 12 caracteres e três tipos de caracteres. Troca obrigatória no próximo login.</p></div><div class="check-line"><input type="checkbox" id="user-active" ${u.active !== false ? "checked" : ""}><label for="user-active">Usuário ativo</label></div></form>`,
    `<button class="btn close-modal">Cancelar</button><button class="btn primary" form="user-form" type="submit">Salvar usuário</button>`,
  );
  $("#temp-password").required = !u.id;
  $("#user-form").onsubmit = async (e) => {
    e.preventDefault();
    const data = {
      username: $("#user-username").value,
      role: $("#role").value,
      active: $("#user-active").checked,
      password: $("#temp-password").value || null,
    };
    try {
      await api("/users" + (u.id ? "/" + u.id : ""), {
        method: u.id ? "PUT" : "POST",
        body: JSON.stringify(data),
      });
      closeModal();
      toast("Usuário salvo.");
      if (u.id === state.user.id) {
        const me = await api("/auth/me");
        state.user = me.user;
        state.csrf = me.csrf;
        render();
      } else await usersPage();
    } catch (err) {
      if ($("#user-error"))
        $("#user-error").innerHTML =
          `<div class="form-error">${h(err.message)}</div>`;
    } finally {
      data.password = null;
    }
  };
}
window.addEventListener("popstate", () => render());
window.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeModal();
});
(async () => {
  try {
    const data = await api("/auth/me");
    state.user = data.user;
    state.csrf = data.csrf;
    await render();
  } catch {
    loginView();
  }
})();
