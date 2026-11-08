/* Local historical research view. Read-only, same-origin; never a trade signal. */
(() => {
  'use strict';
  const point = document.querySelector('#view-home .snapshot-grid');
  if (!point) return;
  const panel = document.createElement('section');
  panel.className = 'panel';
  panel.style.cssText = 'margin-top:20px;padding:24px';
  panel.setAttribute('aria-label', 'Historical market research');
  const title = document.createElement('h2');
  title.textContent = 'SOL/USD · Historical research';
  title.style.margin = '0 0 8px';
  const message = document.createElement('p');
  message.className = 'fine-note';
  message.textContent = 'Read-only research bridge not connected. Original dashboard remains operational.';
  const metrics = document.createElement('div');
  metrics.className = 'detail-grid';
  const foot = document.createElement('p');
  foot.className = 'fine-note';
  panel.append(title, message, metrics, foot);
  point.insertAdjacentElement('afterend', panel);

  function field(label, value) {
    const cell = document.createElement('div');
    cell.className = 'mini-info';
    const name = document.createElement('span');
    name.textContent = label;
    const amount = document.createElement('strong');
    amount.textContent = value;
    cell.append(name, amount);
    return cell;
  }
  function percent(value) {
    if (!Number.isFinite(value)) throw new Error('Invalid metric');
    return `${value.toFixed(3)}%`;
  }
  function stamp(value) {
    const d = new Date(value);
    if (!Number.isFinite(d.getTime())) throw new Error('Invalid timestamp');
    return d.toLocaleString('en-AU', {timeZone: 'Australia/Brisbane', dateStyle: 'medium', timeStyle: 'short'}) + ' AEST';
  }
  fetch('/api/v1/research/solusd', {cache:'no-store', credentials:'omit'})
    .then(async response => {
      if (!response.ok) throw new Error('Read-only research API unavailable');
      const record = await response.json();
      if (record.schema !== 'alpha-labs.historical-research.v1' || record.trading_enabled !== false || record.promotion_authorised !== false ||
          record.live_trading_authorised !== false ||
          !['historical','stale'].includes(record.status)) throw new Error('Invalid research schema');
      const training = record.periods.training;
      const holdout = record.periods.holdout;
      const cards = [
        ['Training strategy', percent(training.strategy_pct)],
        ['Training passive', percent(training.passive_pct)],
        ['Training ×2 costs', percent(training.double_cost_pct)],
        ['Holdout strategy', percent(holdout.strategy_pct)],
        ['Holdout passive', percent(holdout.passive_pct)],
        ['Holdout ×2 costs', percent(holdout.double_cost_pct)]
      ];
      metrics.replaceChildren(...cards.map(([label,value]) => field(label, value)));
      message.textContent = `${record.complete_candles} completed hourly candles · ${record.status === 'stale' ? 'STALE' : 'HISTORICAL'} · Last candle ${stamp(record.last_candle_utc)}`;
      foot.textContent = `Kraken public OHLC · Retrieved ${stamp(record.fetched_at_utc)}. Snapshot only, not live pricing, authenticated exchange prices, verified alpha or actual portfolio P&L. Trading disabled.`;
      const strip = document.querySelector('#safety-strip');
      const last = strip?.querySelector('.safety-end');
      if (last) last.textContent = record.status === 'stale' ? 'RESEARCH STALE' : 'HISTORICAL DATA';
      for (const span of strip?.querySelectorAll('span') || []) {
        if (span.textContent === 'No backend or trading account connected') span.textContent = 'Local read-only research; no trading account connected';
      }
      const data = document.querySelector('#data-summary');
      if (data) data.textContent = record.status === 'stale' ? 'Historical snapshot stale' : 'SOL/USD historical snapshot';
    })
    .catch(() => {
      message.textContent = 'Read-only research API unavailable or invalid. Start the local research server, then reload.';
      foot.textContent = 'No market feed, trading account or portfolio ledger connected.';
    });
})();


/* Alpha Labs three-market historical research bridge: read only. */
(() => {
  'use strict';
  const watchlist = document.querySelector('#view-markets .market-panel');
  if (!watchlist) return;
  const panel = document.createElement('section');
  panel.className = 'panel';
  panel.style.marginTop = '18px';
  panel.setAttribute('aria-label', 'Three-market historical research');
  const title = document.createElement('h2');
  title.textContent = 'BTC · ETH · SOL — Historical research';
  const warning = document.createElement('p');
  warning.className = 'fine-note';
  warning.textContent = 'Read-only historical EMA hypothesis screening. These are not live prices, verified alpha, investment recommendations or actionable signals. No trading permissions.';
  const grid = document.createElement('div');
  grid.className = 'detail-grid';
  panel.append(title, warning, grid);
  watchlist.insertAdjacentElement('afterend', panel);
  // Never mix historical imported results with the fictional demo screen.
  const demoToggle = document.getElementById('demo-toggle');
  const syncDemoVisibility = () => {panel.hidden = Boolean(demoToggle && demoToggle.checked);};
  if (demoToggle) demoToggle.addEventListener('change', syncDemoVisibility);
  syncDemoVisibility();

  const sources = [
    ['xbtusd', 'Bitcoin · BTC/USD', 'BTC/USD'],
    ['ethusd', 'Ethereum · ETH/USD', 'ETH/USD'],
    ['solusd', 'Solana · SOL/USD', 'SOL/USD']
  ];
  const add = (tag, contents, cls) => {
    const element = document.createElement(tag);
    if (cls) element.className = cls;
    element.textContent = contents;
    return element;
  };
  const fmt = number => {
    if (typeof number !== 'number' || !Number.isFinite(number)) throw Error('Invalid metric');
    return `${number.toFixed(3)}%`;
  };
  const validate = (data, market) => {
    if (!data || data.schema !== 'alpha-labs.historical-research.v1' ||
        data.trading_enabled !== false || data.promotion_authorised !== false ||
        data.live_trading_authorised !== false || data.market !== market ||
        !['historical', 'stale'].includes(data.status) ||
        !Number.isSafeInteger(data.complete_candles) || data.complete_candles < 80 ||
        data.complete_candles > 720 || data.interval_minutes !== 60 ||
        !Number.isFinite(Date.parse(data.last_candle_utc)) ||
        !Number.isFinite(Date.parse(data.fetched_at_utc))) throw Error('Invalid research contract');
    for (const period of ['training', 'holdout']) {
      if (!data.periods || !data.periods[period]) throw Error('Invalid periods');
      for (const k of ['strategy_pct', 'passive_pct', 'double_cost_pct']) fmt(data.periods[period][k]);
    }
    return data;
  };
  for (const [slug, name, market] of sources) {
    const card = document.createElement('div');
    card.append(add('strong', name), add('p', 'Loading local historical research…', 'fine-note'));
    grid.append(card);
    fetch(`/api/v1/research/${slug}`, {cache: 'no-store', credentials: 'omit'})
      .then(response => {if (!response.ok) throw Error('Unavailable'); return response.json();})
      .then(data => {
        const result = validate(data, market);
        const h = result.periods.holdout;
        const t = result.periods.training;
        const stamp = new Date(result.last_candle_utc).toLocaleString('en-AU', {
          timeZone: 'Australia/Brisbane', dateStyle: 'medium', timeStyle: 'short'
        });
        card.replaceChildren(
          add('strong', name),
          add('p', `${result.status === 'stale' ? 'STALE' : 'HISTORICAL'} · ${result.complete_candles} completed hourly candles`, 'fine-note'),
          add('p', `Training strategy: ${fmt(t.strategy_pct)} · passive: ${fmt(t.passive_pct)}`, 'fine-note'),
          add('p', `Holdout strategy: ${fmt(h.strategy_pct)} · passive: ${fmt(h.passive_pct)}`, 'fine-note'),
          add('p', `Holdout ×2 costs: ${fmt(h.double_cost_pct)}`, 'fine-note'),
          add('p', `Last candle: ${stamp} AEST. Imported Kraken public data; not executable pricing.`, 'fine-note')
        );
      })
      .catch(() => card.replaceChildren(
        add('strong', name),
        add('p', 'Historical research unavailable or invalid. No market assessment.', 'fine-note')
      ));
  }
})();
