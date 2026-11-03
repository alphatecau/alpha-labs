/* SYNTHETIC INTERFACE FIXTURE. Not observed markets, forecasts or trades. No external requests. */
'use strict';
window.AlphaDemo = Object.freeze({
  provenance: 'SYNTHETIC DEMO',
  asOf: '2026-11-02T10:30:00Z',
  equityAUD: 10125.40,
  changeAUD: 125.40,
  changePct: 1.25,
  realisedAUD: 86.25,
  unrealisedAUD: 39.15,
  costsAUD: 18.40,
  equityCurve: [9991,10004,10014,10002,10024,10011,10029,10041,10028,10052,10037,10061,10075,10068,10084,10072,10093,10080,10098,10091,10112,10102,10119,10110,10125.4],
  exposure: {asset:'BTC/USD', direction:'LONG', notionalAUD:2250, status:'Hypothetical only'},
  markets: [
    {symbol:'BTC',name:'Bitcoin',pair:'BTC/USD',price:97210.40,changePct:1.36,decision:'LONG',regime:'Upward trend',edge:'+0.24%',details:'Hypothetical trend-following candidate. Not a validated or executable forecast.'},
    {symbol:'ETH',name:'Ethereum',pair:'ETH/USD',price:3628.10,changePct:-0.42,decision:'FLAT',regime:'Sideways',edge:'−0.11%',details:'Estimated net advantage does not exceed assumed costs in this fictional test.'},
    {symbol:'SOL',name:'Solana',pair:'SOL/USD',price:192.50,changePct:-2.16,decision:'SHORT',regime:'Downward trend',edge:'+0.31%',details:'Hypothetical short signal. Australian trading account and derivatives eligibility are NOT verified.'}
  ],
  intelligence: {
    asset:'SOL/USD',direction:'SHORT',horizon:'4-hour hypothesis',edge:'+0.31% (illustrative)',model:'SYNTHETIC scenario, no trained model',
    reasons:['Fictional price series shows downward trend persistence.','Illustrative volatility-adjusted signal favours downside.','Hypothetical modelled costs are below the estimated gross signal.'],
    challenges:['The trade could fail if the market reverses abruptly.','A shortable instrument and approved account do not exist in this prototype.','Funding, spread and executable quotes are not verified.']
  },
  activities:[
    {id:'demo-001',type:'decision',title:'SHORT candidate rejected',detail:'SOL/USD — missing broker eligibility and executable cost evidence.',time:'2026-11-02T10:30:00Z',status:'RESEARCH ONLY'},
    {id:'demo-002',type:'research',title:'Trend analysis completed',detail:'Fictional BTC/USD momentum observation. No forecast has been independently validated.',time:'2026-11-02T09:40:00Z',status:'SYNTHETIC'},
    {id:'demo-003',type:'system',title:'Research simulation initialised',detail:'Demonstration does not create positions, orders or actual profit.',time:'2026-11-02T08:15:00Z',status:'SYNTHETIC'}
  ]
});
