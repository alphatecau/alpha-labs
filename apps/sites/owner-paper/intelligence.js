"use strict";

(() => {
  const status = document.getElementById("intelligence-status");
  const updated = document.getElementById("intelligence-time");
  const markets = document.getElementById("intelligence-markets");
  const risk = document.getElementById("intelligence-risk");
  const products = ["BTC-USD", "ETH-USD", "SOL-USD"];
  const labels = {
    TRENDING_UP: "Uptrend", TRENDING_DOWN: "Downtrend", RANGE_BOUND: "Range-bound",
    UNCERTAIN: "Uncertain", VALIDATED: "Validated", BOOK_UNAVAILABLE: "Book unavailable",
    CANDLES_UNAVAILABLE: "Candles unavailable", PROVIDER_RATE_LIMITED: "Provider rate limited",
    REPLAY_DATA_REJECTED: "Replay data rejected",
  };

  function line(parent, tag, value) {
    const node = document.createElement(tag);
    node.textContent = value;
    parent.append(node);
    return node;
  }

  function candidateDetails(parent, item, expanded) {
    const details = document.createElement("details");
    const key = item.product + "/" + item.strategy;
    details.dataset.detailKey = key;
    details.open = expanded.has(key);
    line(details, "summary", `${item.strategy} · ${item.direction} · ${item.decision}`);
    line(details, "p", item.reason);
    line(details, "p", `Validation · ${item.validation}`);
    if (item.evidence) {
      line(details, "p", `Out of sample · ${item.evidence.trades} trades · ${item.evidence.positive_folds}/${item.evidence.folds} positive folds`);
    }
    for (const reason of [...item.validation_reasons, ...item.risk_reasons]) {
      line(details, "p", reason);
    }
    line(details, "p", `Invalidation · ${item.invalidation}`);
    if (item.plan) {
      const p = item.plan;
      const plan = document.createElement("div");
      plan.dataset.quoteDependent = "";
      details.append(plan);
      line(plan, "p", `Entry zone USD ${p.entry_zone.join(" to ")}. ${p.entry_trigger}.`);
      line(plan, "p", `Stop USD ${p.stop} · Target USD ${p.target} · Max quantity ${p.max_quantity}`);
      line(plan, "p", `Planned loss USD ${p.max_planned_loss} · Entry expires ${p.entry_expires_utc}`);
      line(plan, "p", `Net reward to risk ${Number(p.reward_to_risk_net).toFixed(2)}`);
      line(plan, "p", `Maximum hold ${p.max_holding_seconds / 3600} hours. ${p.time_exit}.`);
      line(plan, "p", `Round-trip fees USD ${p.estimated_round_trip_fees_at_target} · Slippage USD ${p.estimated_round_trip_slippage_at_target}`);
    }
    const committee = document.createElement("details");
    committee.dataset.detailKey = key + "/committee";
    committee.open = expanded.has(committee.dataset.detailKey);
    line(committee, "summary", "Analyst committee");
    const notes = [
      ["Market intelligence", labels[item.committee.market_intelligence] || item.committee.market_intelligence],
      ["Technical analysis", item.committee.technical_analysis.join(". ")],
      ["Quantitative research", item.committee.quantitative_research.join(". ")],
      ["Bull case", item.committee.bull_case],
      ["Bear case", item.committee.bear_case],
      ["Sceptic", item.committee.sceptic.join(". ")],
      ["Portfolio", item.committee.portfolio.join(". ")],
      ["Decision", item.committee.decision],
      ["Independent risk", item.committee.independent_risk.join(". ")],
    ];
    for (const [role, note] of notes) {
      line(committee, "p", `${role} · ${note}`);
    }
    details.append(committee);
    parent.append(details);
  }

  function render(data, requestStarted) {
    if (data.mode !== "RESEARCH_RECOMMENDATIONS" || data.data_mode !== "LIVE_PUBLIC"
        || data.automated_paper_execution !== false || data.real_money_execution !== false
        || !Array.isArray(data.markets) || data.markets.length !== products.length
        || !products.every((symbol, i) => data.markets[i].product === symbol)
        || !["NO TRADE", "RESEARCH OPPORTUNITY"].includes(data.decision)
        || !Number.isFinite(Date.parse(data.as_of_utc))) {
      throw new Error("Unverified recommendation data");
    }
    const expanded = new Set([...markets.querySelectorAll("details[open]")].map((node) => node.dataset.detailKey));
    const expiry = [];
    const cards = data.markets.map((market) => {
      const article = document.createElement("article");
      article.className = "market";
      const rank = data.ranking.find((item) => item.product === market.product);
      line(article, "h3", `${market.product} · ${market.decision}${rank ? ` · Rank ${rank.rank}` : ""}`);
      line(article, "p", market.regime
        ? `${labels[market.regime.trend]} · ${market.regime.volatility.toLowerCase()} volatility`
        : "Regime unavailable");
      line(article, "p", labels[market.data_quality] || market.data_quality);
      if (market.book_fresh && market.book_age_seconds <= 10) {
        const mark = line(article, "p", `USD ${market.mid} midpoint · ${market.book_source} · ${market.book_event_utc}`);
        expiry.push(() => window.setTimeout(() => {
          if (!mark.isConnected) return;
          mark.textContent = "Quote expired · Awaiting a fresh book";
          article.querySelectorAll("[data-quote-dependent]").forEach((node) => { node.hidden = true; });
          if (market.decision === "LONG") status.textContent = "NO TRADE · Awaiting a fresh book";
        }, Math.max(0, (10 - market.book_age_seconds) * 1000 - (performance.now() - requestStarted))));
      }
      if (market.candle_close_utc) {
        line(article, "p", `Last completed candle · ${market.candle_close_utc} · ${market.candle_source}`);
      }
      market.candidates.forEach((item) => candidateDetails(article, item, expanded));
      return article;
    });
    const openRisk = data.portfolio_risk.open_stop_risk_fraction;
    const limit = data.portfolio_risk.max_aggregate_stop_risk_fraction;
    status.textContent = data.decision;
    updated.textContent = `${data.timeframe} · ${data.as_of_utc}`;
    risk.textContent = openRisk === null
      ? `Portfolio risk · ${data.portfolio_risk.status}`
      : `Open stop-risk · ${(Number(openRisk) * 100).toFixed(3)}% of equity · Limit ${Number(limit) * 100}% · ${data.portfolio_risk.status}`;
    markets.replaceChildren(...cards);
    expiry.forEach((schedule) => schedule());
  }

  function clear() {
    status.textContent = "NO TRADE · Live evidence unavailable";
    updated.textContent = "Research only";
    risk.textContent = "";
    markets.replaceChildren();
  }

  let expires;
  async function refresh() {
    try {
      const requestStarted = performance.now();
      const response = await fetch("/api/v1/paper/recommendations", {
        method: "GET", credentials: "same-origin", cache: "no-store", signal: AbortSignal.timeout(5000),
      });
      if (!response.ok) throw new Error("Recommendations unavailable");
      render(await response.json(), requestStarted);
      window.clearTimeout(expires);
      expires = window.setTimeout(clear, 10000);
    } catch {
      clear();
    }
  }

  if (document.getElementById("intelligence").dataset.enabled === "true") {
    refresh();
    window.setInterval(refresh, 8000);
  } else {
    clear();
  }
})();
