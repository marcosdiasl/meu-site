const $ = (sel) => document.querySelector(sel);
const API = {
  base: () => localStorage.getItem("API_BASE_URL") || "",
  token: () => localStorage.getItem("API_TOKEN") || "",
  actionsUrl: () => localStorage.getItem("ACTIONS_API_URL") || "/api/acoes",
  useNgrok: () => (localStorage.getItem("USE_NGROK") || "false") === "true",
};

function headers() {
  const h = {"Content-Type":"application/json"};
  const t = API.token();
  if (t) h["X-API-TOKEN"] = t;
  if (API.useNgrok()) h["ngrok-skip-browser-warning"] = "true";
  return h;
}

async function apiGet(path) {
  const base = API.base() || "";
  const url = base ? `${base}${path}` : path;
  const r = await fetch(url, {headers: headers()});
  const j = await r.json();
  if (!r.ok) throw new Error(j.error || "Erro");
  return j;
}

async function apiPost(path, body) {
  const base = API.base() || "";
  const url = base ? `${base}${path}` : path;
  const r = await fetch(url, {method:"POST", headers: headers(), body: JSON.stringify(body || {})});
  const j = await r.json();
  if (!r.ok) throw new Error(j.error || "Erro");
  return j;
}

function toast(msg) {
  const el = $("#toast");
  el.textContent = msg;
  el.classList.add("show");
  setTimeout(()=>el.classList.remove("show"), 2400);
}

function fmtBRL(v, decimals=2) {
  const n = Number(v || 0);
  return n.toLocaleString("pt-BR", {minimumFractionDigits:decimals, maximumFractionDigits:decimals});
}

function route() {
  return (location.hash || "#/dashboard").replace("#","");
}

function setActiveNav(path) {
  document.querySelectorAll(".nav a").forEach(a=>{
    a.classList.toggle("active", a.getAttribute("href") === `#${path}`);
  });
}

function page(html) {
  $("#app").innerHTML = html;
}

async function renderDashboard() {
  setActiveNav("/dashboard");
  const data = await apiGet("/api/dashboard");
  const w = data.wallet;
  const u = data.user;
  $("#hello").textContent = `Olá ${u.name}, tudo bem?`;

  const rows = data.daily_earnings || [];
  const points = rows.map(r => `${r.date}: R$ ${fmtBRL(r.amount,2)}`).join("<br>") || "Sem dados ainda";

  page(`
    <div class="card">
      <div class="row">
        <div class="col">
          <div class="muted">Saldo Disponível</div>
          <div class="big">R$ ${fmtBRL(w.saldo_disponivel,2)}</div>
          <div class="muted">retirar saldo disponível</div>
        </div>
        <div class="col">
          <div class="muted">Saldo Bloqueado</div>
          <div class="big">R$ ${fmtBRL(w.saldo_bloqueado,2)}</div>
          <div class="muted">aguardando confirmação das ações feitas pelos seus perfis</div>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="h2" style="text-align:center">Histórico de ganhos diários</div>
      <div class="muted" style="text-align:center;margin-bottom:10px">Histórico dos últimos dias</div>
      <div class="muted">${points}</div>
    </div>
  `);
}

async function renderGanhar() {
  setActiveNav("/ganhar");
  page(`
    <div class="card">
      <div class="h1">Como você ganhar?</div>
      <div class="muted">Escolha qual forma você quer ganhar</div>
      <hr>
      <button class="btn green block" id="goIg">Realizar ações Instagram</button>
    </div>
  `);
  $("#goIg").onclick = () => (location.hash = "#/ganhar/instagram");
}

async function renderInstagramList() {
  setActiveNav("/ganhar");
  let res;
  try {
    res = await apiPost("/api/acoes", {origem:"instagram", acao:"listar"});
  } catch (e) {
    page(`<div class="card"><div class="h1">Ações Instagram</div><div class="muted">Erro ao buscar ações: ${e.message}</div></div>`);
    return;
  }

  const acoes = (res.acoes || []).filter(x => x && x.tipo && x.target_url);

  const list = acoes.length ? acoes.map((a, i) => `
      <div class="card">
        <div class="row" style="align-items:center;justify-content:space-between">
          <div>
            <div class="h2" style="margin:0">[TT] ${a.tipo}</div>
            <div class="muted">${a.target_url}</div>
            <div class="muted">R$ ${fmtBRL(0.01,3)}</div>
          </div>
          <button class="btn green" data-idx="${i}">Começar</button>
        </div>
      </div>
  `).join("") : `<div class="card"><div class="h1">Ações Instagram</div><div class="muted">Nenhuma ação disponível no momento.</div></div>`;

  page(`<div class="h1" style="margin:8px 0 12px">Ações Instagram</div>${list}`);

  document.querySelectorAll("button[data-idx]").forEach(btn=>{
    btn.onclick = async () => {
      try {
        const claim = await apiPost("/api/claims", {origem:"instagram"});
        localStorage.setItem("CURRENT_CLAIM_ID", String(claim.claim_id));
        location.hash = `#/ganhar/instagram/acao/${claim.claim_id}`;
      } catch (e) {
        toast(e.message);
      }
    };
  });
}

function secondsLeft(expiresAt) {
  const t = new Date(expiresAt).getTime() - Date.now();
  return Math.max(0, Math.floor(t/1000));
}

async function openActionViaApi(claimId, botao) {
  const url = API.actionsUrl();
  const r = await fetch(url, {method:"POST", headers: headers(), body: JSON.stringify({claim_id: Number(claimId), origem:"instagram", botao})});
  const j = await r.json();
  if (!r.ok) throw new Error(j.error || "Erro na API de ações");
  const acoes = j.acoes || [];

  let pick = null;
  if (botao === "acessar_perfil") {
    pick = acoes.find(a => ["seguir","perfil","acessar_perfil"].includes((a.tipo||"").toLowerCase()));
  } else {
    pick = acoes.find(a => ["curtir","comentar","visualizar","acesso_direto","direto"].includes((a.tipo||"").toLowerCase()));
  }
  if (!pick) throw new Error("Nenhuma ação compatível disponível");

  window.open(pick.target_url, "_blank", "noopener,noreferrer");
  await apiPost(`/api/claims/${claimId}/opened`, {});
  toast("Abrindo link…");
}

async function renderExecuteAction(claimId) {
  setActiveNav("/ganhar");
  let claim;
  try {
    claim = await apiGet(`/api/claims/${claimId}`);
  } catch (e) {
    page(`<div class="card"><div class="h1">Ação</div><div class="muted">${e.message}</div></div>`);
    return;
  }

  const tick = () => {
    const left = secondsLeft(claim.expires_at);
    const el = $("#secondsLeft");
    if (el) el.textContent = String(left);
    if (left <= 0) {
      const msg = $("#expiredMsg");
      if (msg) msg.style.display = "block";
      ["btnPerfil","btnDireto","btnConfirmar"].forEach(id=>{ const b = document.getElementById(id); if (b) b.disabled = true; });
    }
  };

  page(`
    <div class="card">
      <div class="h2">[TT] ${claim.action_tipo || "Ação"} [R$ ${fmtBRL(claim.payout_amount,3)}]</div>
      <div class="muted" style="margin-bottom:10px">Instruções</div>
      <div class="muted">
        • Leia as instruções acima!<br>
        • Ações puladas não aparecem novamente!<br>
        • Não siga perfis privados!<br>
        • Você tem <b id="secondsLeft">${secondsLeft(claim.expires_at)}</b> segundo(s) para realizar a tarefa.
      </div>

      <div id="expiredMsg" class="muted" style="display:none;margin-top:10px">
        Tempo expirado. Volte para pegar outra ação.
      </div>

      <hr>

      <div class="row">
        <button class="btn orange col" id="btnPular">Pular Ação</button>
        <button class="btn green col" id="btnConfirmar">Confirmar Ação</button>
        <button class="btn blue col" id="btnPerfil">Acessar Perfil</button>
      </div>
      <div style="margin-top:10px">
        <button class="btn red block" id="btnDireto">Acesso Direto</button>
      </div>
    </div>
  `);

  $("#btnPular").onclick = () => { toast("Ação pulada"); location.hash = "#/ganhar/instagram"; };
  $("#btnPerfil").onclick = async () => {
    try { await openActionViaApi(claimId, "acessar_perfil"); }
    catch(e){ toast(e.message); }
  };
  $("#btnDireto").onclick = async () => {
    try { await openActionViaApi(claimId, "acesso_direto"); }
    catch(e){ toast(e.message); }
  };
  $("#btnConfirmar").onclick = async () => {
    try {
      const refreshed = await apiGet(`/api/claims/${claimId}`);
      if (!refreshed.opened_link) {
        toast("Você precisa acessar o link antes de confirmar.");
        return;
      }
      await apiPost(`/api/claims/${claimId}/confirm`, {opened_link:true});
      toast("Ação enviada para confirmação.");
      location.hash = "#/dashboard";
    } catch (e) {
      toast(e.message);
    }
  };

  tick();
  const timer = setInterval(tick, 1000);
  window.addEventListener("hashchange", ()=>clearInterval(timer), {once:true});
}

async function renderHistorico() {
  setActiveNav("/historico-acoes");
  page(`
    <div class="card">
      <div class="h1">Histórico de Ações</div>
      <div class="muted">Nesta página você pode acompanhar todas as últimas 2000 ações realizadas por você.</div>
      <hr>
      <div class="row">
        <div class="col"><input id="q" placeholder="Pesquisar (id, username, status)"></div>
        <div style="width:180px"><select id="limit">
          <option value="10">10</option>
          <option value="25" selected>25</option>
          <option value="50">50</option>
          <option value="100">100</option>
        </select></div>
        <div style="width:140px"><button class="btn gray block" id="btnBuscar">Buscar</button></div>
      </div>
      <div id="tblWrap" style="margin-top:12px"></div>
    </div>
  `);

  async function load() {
    const limit = Number($("#limit").value || 25);
    const q = $("#q").value || "";
    const data = await apiGet(`/api/historico-acoes?limit=${limit}&q=${encodeURIComponent(q)}`);
    const items = data.items || [];
    const rows = items.map(it=>{
      const dt = it.submitted_at || it.claimed_at || "";
      const v = (it.validity || "pending").toLowerCase();
      const badge = v === "valid" ? `<span class="badge ok">Válida</span>` : v === "invalid" ? `<span class="badge bad">Inválida</span>` : `<span class="badge pending">Pendente</span>`;
      return `<tr>
        <td>${it.id}</td>
        <td>${dt}</td>
        <td>${it.type_code || "TT"}</td>
        <td>${it.profile_username || "-"}</td>
        <td>R$ ${fmtBRL(it.payout_amount,3)}</td>
        <td>${badge}</td>
      </tr>`;
    }).join("");

    $("#tblWrap").innerHTML = `
      <table class="table">
        <thead><tr>
          <th>ID</th><th>Data</th><th>Tipo</th><th>Nome de Usuário</th><th>Valor</th><th>Status</th>
        </tr></thead>
        <tbody>${rows || `<tr><td colspan="6" class="muted">Sem registros</td></tr>`}</tbody>
      </table>
    `;
  }

  $("#btnBuscar").onclick = () => load().catch(e=>toast(e.message));
  load().catch(e=>toast(e.message));
}

async function renderSaques() {
  setActiveNav("/saques");
  const w = await apiGet("/api/dashboard");
  const wallet = w.wallet;
  const profile = await apiGet("/api/payout-profile");
  const bank = (profile.payout_method || "PIX") === "PIX" ? "PIX" : (profile.bank_name || "-");
  const agency = (profile.payout_method || "PIX") === "PIX" ? "-" : (profile.agency || "-");
  const account = (profile.payout_method || "PIX") === "PIX" ? "-" : (profile.account || "-");
  const cpf = profile.cpf || "";

  const withdraws = await apiGet("/api/withdraws");
  const rows = (withdraws.items || []).map(x => `
    <tr><td>${x.id}</td><td>${x.requested_at}</td><td>R$ ${fmtBRL(x.amount,2)}</td><td>${x.status}</td></tr>
  `).join("");

  page(`
    <div class="card">
      <div class="row" style="align-items:center;justify-content:space-between">
        <button class="btn green" id="btnSaque">Solicitar Saque</button>
        <div class="muted">Saldo disponível: <b>R$ ${fmtBRL(wallet.saldo_disponivel,2)}</b></div>
      </div>
      <hr>
      <table class="table">
        <thead><tr><th>Banco</th><th>Agência</th><th>Conta</th><th>CPF</th></tr></thead>
        <tbody><tr><td>${bank}</td><td>${agency}</td><td>${account}</td><td>${cpf || "-"}</td></tr></tbody>
      </table>
    </div>

    <div class="card">
      <div class="h2">Meus Saques</div>
      <table class="table">
        <thead><tr><th>ID</th><th>Data</th><th>Valor</th><th>Status</th></tr></thead>
        <tbody>${rows || `<tr><td colspan="4" class="muted">Sem saques</td></tr>`}</tbody>
      </table>
    </div>
  `);

  $("#btnSaque").onclick = async () => {
    const amountStr = prompt("Valor do saque (R$):");
    if (!amountStr) return;
    const amount = Number(String(amountStr).replace(",", "."));
    if (!Number.isFinite(amount) || amount <= 0) { toast("Valor inválido"); return; }
    try {
      await apiPost("/api/withdraw", {amount});
      toast("Saque solicitado com sucesso.");
      location.hash = "#/saques";
    } catch (e) {
      toast(e.message);
    }
  };
}

async function renderConfiguracoes() {
  setActiveNav("/configuracoes");
  page(`
    <div class="card">
      <div class="h1">Configurações</div>
      <div class="muted">Configure a URL da sua API (opcional) e a API de ações (obrigatória).</div>
      <hr>
      <div class="grid">
        <div>
          <div class="muted">API_BASE_URL (opcional)</div>
          <input id="baseUrl" placeholder="ex: https://seu-app.onrender.com" value="${API.base()}">
        </div>
        <div>
          <div class="muted">ACTIONS_API_URL (obrigatório)</div>
          <input id="actionsUrl" placeholder="ex: https://sua-api/acoes (ou /api/acoes)" value="${API.actionsUrl()}">
        </div>
        <div>
          <div class="muted">API_TOKEN (opcional)</div>
          <input id="token" placeholder="seu token" value="${API.token()}">
        </div>
        <div>
          <label class="muted"><input type="checkbox" id="ngrok" ${API.useNgrok() ? "checked" : ""}> usar ngrok-skip-browser-warning</label>
        </div>
        <button class="btn green" id="save">Salvar</button>
      </div>
    </div>
  `);
  $("#save").onclick = () => {
    localStorage.setItem("API_BASE_URL", $("#baseUrl").value.trim());
    localStorage.setItem("ACTIONS_API_URL", $("#actionsUrl").value.trim());
    localStorage.setItem("API_TOKEN", $("#token").value.trim());
    localStorage.setItem("USE_NGROK", $("#ngrok").checked ? "true" : "false");
    toast("Salvo!");
  };
}

async function renderPlaceholder(path) {
  setActiveNav(path);
  page(`<div class="card"><div class="h1">Em construção</div><div class="muted">Página ${path}</div></div>`);
}

async function render() {
  const p = route();
  try {
    if (p === "/dashboard") return await renderDashboard();
    if (p === "/ganhar") return await renderGanhar();
    if (p === "/ganhar/instagram") return await renderInstagramList();
    if (p.startsWith("/ganhar/instagram/acao/")) {
      const claimId = p.split("/").pop();
      return await renderExecuteAction(claimId);
    }
    if (p === "/historico-acoes") return await renderHistorico();
    if (p === "/saques") return await renderSaques();
    if (p === "/configuracoes") return await renderConfiguracoes();
    if (p === "/minha-conta") return await renderPlaceholder("/minha-conta");
    if (p === "/indicados") return await renderPlaceholder("/indicados");
    if (p === "/logout") { toast("Saiu"); location.hash = "#/dashboard"; return; }
    location.hash = "#/dashboard";
  } catch (e) {
    page(`<div class="card"><div class="h1">Erro</div><div class="muted">${e.message}</div></div>`);
  }
}

window.addEventListener("hashchange", render);
render();
