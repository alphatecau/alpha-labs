"use strict";

const PAPER_PRODUCTS = ["BTC-USD", "ETH-USD", "SOL-USD"];
const PENDING_KEY = "alpha.paper.pending.v1";

function healthySnapshot(state, receivedAt, now) {
  const elapsed = Math.max(0, (now - receivedAt) / 1000);
  return !!state && state.mode === "SIMULATION_ONLY" && state.currency === "USD" &&
    state.risk?.data_healthy === true && state.portfolio?.reconciled === true &&
    PAPER_PRODUCTS.every(symbol => {
      const q = state.market?.[symbol];
      return q?.healthy === true && Number.isFinite(q.age_seconds) && q.age_seconds >= 0 &&
        q.age_seconds + elapsed <= 10 && Number.isFinite(Number(q.bid)) &&
        Number.isFinite(Number(q.ask)) && Number(q.bid) > 0 && Number(q.ask) >= Number(q.bid);
    });
}

function validIntent(value) {
  if (!value || !PAPER_PRODUCTS.includes(value.symbol) || !["BUY", "SELL"].includes(value.side)) return false;
  const decimal = /^[0-9]{1,9}(?:\.[0-9]{1,8})?$/;
  const limitValid = value.order_type === "LIMIT"
    ? typeof value.limit_price === "string" && decimal.test(value.limit_price) && Number(value.limit_price) > 0
    : value.order_type === undefined && value.limit_price === undefined;
  return limitValid && typeof value.quantity === "string" && decimal.test(value.quantity) && Number(value.quantity) > 0 &&
    (value.side === "SELL" || (typeof value.stop_price === "string" && decimal.test(value.stop_price) && Number(value.stop_price) > 0));
}

function createIntentStore(storage, randomId) {
  let pending = null;
  try {
    const saved = JSON.parse(storage.getItem(PENDING_KEY));
    if (validIntent(saved) && /^[A-Za-z0-9_-]{16,80}$/.test(saved.order_id)) pending = saved;
  } catch (_) { /* unavailable storage cannot fabricate a pending fill */ }
  return {
    current: () => pending,
    prepare(terms) {
      if (!validIntent(terms)) throw new Error("Enter a positive quantity and a BUY stop price.");
      const fields = ["symbol", "side", "quantity", "stop_price", "order_type", "limit_price"];
      if (pending && fields.some(key => pending[key] !== terms[key])) {
        throw new Error("Resolve the pending order before changing its terms.");
      }
      if (!pending) {
        pending = {...terms, order_id: randomId()};
        // If persistence is unavailable, keep this same ID in memory for retries.
        try { storage.setItem(PENDING_KEY, JSON.stringify(pending)); } catch (_) { /* no credentials stored */ }
      }
      return {...pending};
    },
    resolve() {
      pending = null;
      try { storage.removeItem(PENDING_KEY); } catch (_) { /* memory is authoritative for this page */ }
    }
  };
}

function installPaperConsole(win) {
  const doc = win.document;
  const el = id => doc.getElementById(id);
  const text = (id, value) => { el(id).textContent = value; };
  const csrf = doc.querySelector('meta[name="alpha-csrf"]').content;
  let storage;
  try { storage = win.sessionStorage; } catch (_) { storage = null; }
  storage ||= {getItem: () => null, setItem: () => {}, removeItem: () => {}};
  const intents = createIntentStore(storage, () => win.crypto.randomUUID());
  let state = null, receivedAt = 0, busy = false, refreshing = false;
  const money = value => value === undefined || value === null || value === "" || !Number.isFinite(Number(value)) ? "—" :
    Number(value).toLocaleString("en-US", {minimumFractionDigits: 2, maximumFractionDigits: 2});

  async function request(path, payload) {
    const options = {credentials: "same-origin", cache: "no-store", redirect: "error", headers: {Accept: "application/json"}, signal: win.AbortSignal.timeout(10000)};
    if (payload !== undefined) {
      options.method = "POST";
      options.headers["Content-Type"] = "application/json";
      options.headers["X-Alpha-CSRF"] = csrf;
      options.body = JSON.stringify(payload);
    }
    const response = await win.fetch("/api/v1/paper/" + path, options);
    const data = await response.json();
    if (!response.ok) {
      const error = new Error(data.error || "PAPER_API_UNAVAILABLE");
      error.status = response.status;
      throw error;
    }
    if (data.mode !== "SIMULATION_ONLY") throw new Error("UNVERIFIED_PAPER_RESPONSE");
    return data;
  }

  function pendingLabel() {
    const pending = intents.current();
    text("pending", pending ? "Pending outcome · " + pending.order_id + ". Retry preserves this identifier and these exact terms." : "");
    el("retry-pending").hidden = !pending;
    el("retry-pending").disabled = busy;
  }

  function tick() {
    const healthy = healthySnapshot(state, receivedAt, Date.now());
    el("submit-order").disabled = busy || !healthy || state?.risk?.armed !== true || !!intents.current();
    el("arm").disabled = busy || !healthy || state?.risk?.can_arm !== true || state?.risk?.armed === true;
    text("risk-status", !healthy ? "UNAVAILABLE · LOCKED" : state.risk.armed ? "ARMED · PAPER ONLY" : "HALTED");
    for (const symbol of PAPER_PRODUCTS) {
      const asset = symbol.split("-")[0], q = state?.market?.[symbol];
      const fresh = healthy && q?.healthy === true;
      text(asset + "-health", fresh ? "FRESH" : "UNAVAILABLE / STALE");
      el(asset + "-health").className = "badge" + (fresh ? " fresh" : "");
    }
    pendingLabel();
  }

  function table(id, rows, columns, empty) {
    const body = el(id);
    body.replaceChildren();
    if (!rows.length) {
      const tr = doc.createElement("tr"), td = doc.createElement("td");
      td.colSpan = columns; td.textContent = empty; tr.append(td); body.append(tr); return;
    }
    for (const values of rows) {
      const tr = doc.createElement("tr");
      for (const value of values) {
        const td = doc.createElement("td");
        if (typeof value === "string") td.textContent = value;
        else td.append(value);
        tr.append(td);
      }
      body.append(tr);
    }
  }

  function cancelButton(order) {
    const button = doc.createElement("button");
    button.type = "button"; button.className = "secondary"; button.textContent = "Cancel";
    button.addEventListener("click", async () => {
      button.disabled = true;
      try {
        await request("cancel", {order_id: order.order_id});
        await refresh();
        text("message", "Unfilled quantity cancelled.");
      } catch (error) {
        text("message", "Cancellation unavailable. " + error.message);
        button.disabled = false;
      }
    });
    return button;
  }

  function render() {
    for (const symbol of PAPER_PRODUCTS) {
      const asset = symbol.split("-")[0], q = state.market?.[symbol];
      text(asset + "-bid", money(q?.bid)); text(asset + "-ask", money(q?.ask));
      text(asset + "-source", q ? q.source + " · " + q.age_seconds + "s at receipt" : "Provider unavailable");
      text(asset + "-time", q?.source_time || "No verified event timestamp");
    }
    for (const key of ["nav", "cash", "realised", "unrealised", "fees"]) text(key, money(state.portfolio?.[key]));
    if (state.execution_costs) {
      text("costs", "Simulated costs · " + Number(state.execution_costs.fee_bps) + " bps fee, " +
        Number(state.execution_costs.slippage_bps) + " bps slippage.");
    }
    text("reconciled", state.portfolio?.reconciled ? "RECONCILED" : "VALUATION UNAVAILABLE");
    text("risk-reason", (state.risk?.reason || "UNKNOWN").replaceAll("_", " "));
    text("updated", "Server UTC · " + state.server_time);
    const recovery = state.recovery;
    text("recovery", recovery?.status === "VERIFIED"
      ? "Verified checkpoint " + recovery.checkpoint_sequence + " · Fill sequence " + recovery.journal_sequence
      : "Protected recovery unverified");
    table("positions", Object.entries(state.portfolio?.positions || {}).map(([symbol, qty]) =>
      [symbol, qty, money(state.market?.[symbol]?.bid), money(state.portfolio?.cost_basis?.[symbol])]), 4, "No virtual positions");
    table("orders", (state.orders || []).map(order => [
      order.symbol + " / " + order.side, money(order.limit), order.remaining,
      (order.status + (order.reason ? " · " + order.reason : "")).replaceAll("_", " "),
      ["PENDING", "PARTIALLY_FILLED"].includes(order.status) ? cancelButton(order) : "—"
    ]), 5, "No limit orders");
    table("fills", (state.fills || []).map(fill => [fill.details?.filled_at || "—", fill.symbol + " / " + fill.side, fill.quantity, money(fill.price), money(fill.fee), fill.order_id]), 6, "No simulated fills");
    tick();
  }

  async function refresh() {
    if (refreshing) return;
    refreshing = true;
    try {
      const fresh = await request("state");
      if (fresh.currency !== "USD" || !fresh.risk || !fresh.portfolio) throw new Error("UNVERIFIED_PAPER_RESPONSE");
      state = fresh; receivedAt = Date.now(); render();
      text("message", healthySnapshot(state, receivedAt, Date.now()) ? "Verified public books · simulated execution only" : "Market evidence unavailable. Paper execution remains halted.");
    } catch (error) {
      state = null; tick();
      text("recovery", "Protected recovery unverified");
      for (const key of ["nav", "cash", "realised", "unrealised", "fees"]) text(key, "—");
      table("positions", [], 4, "Positions unavailable");
      table("fills", [], 6, "Fill history unavailable");
      table("checkpoints", [], 2, "Checkpoint history unavailable");
      table("orders", [], 5, "Order status unavailable");
      text("message", error.message + ". Trading controls disabled. Emergency HALT remains available.");
    } finally { refreshing = false; }
  }

  async function submit(payload) {
    if (busy) return;
    busy = true; tick();
    try {
      const result = await request("orders", payload);
      if (!["SIMULATED_FILL", "ALREADY_COMMITTED", "PENDING", "PARTIALLY_FILLED", "FILLED", "CANCELLED", "REJECTED"].includes(result.status)) {
        throw new Error("UNVERIFIED_ORDER_OUTCOME");
      }
      intents.resolve();
      await refresh();
      text("message", result.status === "ALREADY_COMMITTED" ? "This simulated order was already recorded." :
        "Simulated order · " + result.status.replaceAll("_", " ") + (result.order?.reason ? " · " + result.order.reason : ""));
    } catch (error) {
      // A server rejection below 500 proves this request did not execute. A
      // transport/5xx failure has an unknown outcome: retain exactly the same ID.
      if (error.status && error.status < 500 && error.message !== "IDEMPOTENCY_CONFLICT") intents.resolve();
      text("message", error.message + (intents.current() ? ". Outcome unresolved; retry the same order ID." : ". No simulated fill from this request."));
    } finally { busy = false; tick(); }
  }

  el("order-form").addEventListener("submit", async event => {
    event.preventDefault();
    if (!healthySnapshot(state, receivedAt, Date.now()) || !state.risk.armed || busy) return;
    const terms = {symbol: el("symbol").value, side: el("side").value, quantity: el("quantity").value.trim()};
    if (terms.side === "BUY") terms.stop_price = el("stop-price").value.trim();
    if (el("order-type").value === "LIMIT") {
      terms.order_type = "LIMIT";
      terms.limit_price = el("limit-price").value.trim();
    }
    try {
      if (!validIntent(terms)) throw new Error("Enter a positive quantity and a BUY stop price.");
      const limit = terms.limit_price ? " with limit USD " + terms.limit_price : "";
      if (!win.confirm("Simulate " + terms.side + " " + terms.quantity + " " + terms.symbol + limit + "?")) return;
      await submit(intents.prepare(terms));
    } catch (error) { text("message", error.message); }
  });
  el("retry-pending").addEventListener("click", () => { const pending = intents.current(); if (pending) submit(pending); });
  el("side").addEventListener("change", () => { el("stop-label").hidden = el("side").value === "SELL"; });
  el("order-type").addEventListener("change", () => { el("limit-label").hidden = el("order-type").value !== "LIMIT"; });
  el("load-checkpoints").addEventListener("click", async () => {
    try {
      const data = await request("checkpoints");
      table("checkpoints", data.checkpoints.map(item => [String(item.sequence), item.head]), 2, "No checkpoints");
    } catch (error) { text("message", "Checkpoint history unavailable. " + error.message); }
  });
  el("sign-out").addEventListener("click", async () => {
    try {
      const response = await win.fetch("/auth/logout", {method: "POST", credentials: "same-origin", redirect: "error"});
      if (!response.ok) throw new Error("SIGN_OUT_UNAVAILABLE");
      win.location.replace("/owner-paper/signed-out");
    } catch (error) { text("message", error.message); }
  });
  el("halt").addEventListener("click", async () => {
    try { await request("control", {action: "halt"}); text("message", "Emergency HALT recorded."); }
    catch (error) { text("message", "HALT acknowledgement unavailable: " + error.message + ". Execution status is unknown."); }
    finally { state = null; tick(); }
  });
  el("arm").addEventListener("click", async () => {
    if (!state || !healthySnapshot(state, receivedAt, Date.now()) || !win.confirm("Arm virtual paper execution with current risk limits? No real money.")) return;
    try { await request("control", {action: "arm", revision: state.risk.revision}); await refresh(); }
    catch (error) { text("message", error.message); state = null; tick(); }
  });
  tick(); refresh();
  win.setInterval(refresh, 5000);
  win.setInterval(tick, 1000);
  return {refresh, tick};
}

if (typeof module !== "undefined") module.exports = {healthySnapshot, validIntent, createIntentStore, installPaperConsole};
if (typeof window !== "undefined") installPaperConsole(window);
