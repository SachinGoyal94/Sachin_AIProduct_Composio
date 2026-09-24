"""CSS for the case-study page (imported by render.py)."""

CSS = """
:root{
  --ink:#1c1917; --mut:#6b6f76; --faint:#a8a29e; --line:#e7e5e4;
  --paper:#faf9f7; --card:#ffffff; --acc:#ea580c; --acc-soft:#fde8dd;
  --blue:#2563eb; --green:#16a34a; --amber:#d97706; --red:#dc2626;
  --serif:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,ui-serif,serif;
  --sans:ui-sans-serif,system-ui,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  --mono:ui-monospace,"Cascadia Code",Consolas,Menlo,monospace;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.6 var(--sans);
  -webkit-font-smoothing:antialiased}
a{color:var(--acc);text-decoration:none}
a:hover{text-decoration:underline}
code,.mono{font-family:var(--mono);font-size:.86em}
.wrap{max-width:1140px;margin:0 auto;padding:0 28px}

/* ---------- nav ---------- */
nav{position:sticky;top:0;z-index:50;background:rgba(250,249,247,.88);
  backdrop-filter:blur(10px);border-bottom:1px solid var(--line)}
nav .wrap{display:flex;align-items:center;gap:6px;height:54px}
.brand{font-family:var(--serif);font-weight:700;font-size:17px;margin-right:14px;
  color:var(--ink)}
.brand .dot{color:var(--acc)}
nav a.nl{font-size:13.5px;color:var(--mut);padding:6px 10px;border-radius:8px}
nav a.nl:hover{color:var(--ink);background:#f0eeec;text-decoration:none}
nav .spacer{flex:1}
nav .tag{font-size:11px;letter-spacing:.12em;color:var(--faint);text-transform:uppercase}

/* ---------- hero ---------- */
header.hero{padding:72px 0 46px;border-bottom:1px solid var(--line);
  background:
    radial-gradient(1100px 380px at 15% -8%, #fdeadd 0%, transparent 60%),
    radial-gradient(900px 320px at 90% -12%, #e8efff 0%, transparent 55%)}
.kicker{font-size:12px;letter-spacing:.22em;text-transform:uppercase;
  color:var(--acc);font-weight:600;margin-bottom:18px}
h1{font-family:var(--serif);font-size:clamp(34px,5vw,58px);line-height:1.08;
  margin:0 0 20px;letter-spacing:-.01em}
h1 .accent{color:var(--acc)}
.sub{max-width:780px;font-size:18px;color:#44403c;margin:0 0 34px}
.sub b{color:var(--ink)}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(158px,1fr));
  gap:12px;margin:26px 0 8px}
.tile{background:var(--card);border:1px solid var(--line);border-radius:14px;
  padding:16px 18px}
.tile .big{font-family:var(--serif);font-size:30px;line-height:1.05;
  letter-spacing:-.01em}
.tile .big .to{color:var(--faint);font-size:22px}
.tile .lab{font-size:12.5px;color:var(--mut);margin-top:6px}
.tile.hero-acc{border-color:#f5c9ac;background:linear-gradient(160deg,#fff,#fdf1e7)}
.verdict-strip{margin-top:22px;background:#111827;color:#f9fafb;border-radius:14px;
  padding:16px 22px;font-size:15.5px;display:flex;gap:14px;align-items:baseline}
.verdict-strip .k{color:#fdba74;font-weight:700;font-size:12px;letter-spacing:.14em}
.asof{font-size:12.5px;color:var(--faint);margin-top:14px}
.byline{margin-top:8px;font-size:13.5px;color:var(--mut)}
.byline b{color:var(--ink)}

/* ---------- sections ---------- */
section{padding:64px 0;border-bottom:1px solid var(--line)}
.shead{margin-bottom:30px}
.snum{font-family:var(--mono);font-size:12.5px;color:var(--acc);
  letter-spacing:.18em;margin-bottom:6px}
h2{font-family:var(--serif);font-size:clamp(26px,3.2vw,38px);margin:0 0 10px;
  letter-spacing:-.01em}
.slede{max-width:820px;color:#57534e;font-size:16.5px;margin:0}

/* ---------- patterns ---------- */
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));
  gap:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;
  padding:22px 24px;position:relative}
.card .rank{position:absolute;top:20px;right:22px;font-family:var(--mono);
  font-size:11px;color:var(--faint)}
.card .metric{font-family:var(--serif);font-size:34px;line-height:1;
  color:var(--acc);letter-spacing:-.01em}
.card .metric .mlab{font-size:12.5px;color:var(--mut);font-family:var(--sans);
  letter-spacing:0;display:block;margin-top:4px}
.card h3{font-size:16.5px;margin:12px 0 8px;line-height:1.4}
.card p{margin:0;font-size:14px;color:var(--mut)}
.charts{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));
  gap:16px;margin-top:18px}
.chart{background:var(--card);border:1px solid var(--line);border-radius:16px;
  padding:20px 22px}
.chart h4{margin:0 0 4px;font-size:15px}
.chart .csub{font-size:12.5px;color:var(--mut);margin-bottom:10px}
.legend{font-size:12px;fill:var(--mut)}
svg .bar-lab{font:12.5px var(--sans);fill:#44403c}
svg .bar-val{font:600 12.5px var(--sans);fill:var(--ink)}
svg .bar-sub{fill:var(--faint);font-weight:400}
svg .donut-big{font:600 30px var(--serif);fill:var(--ink)}
svg .donut-sub{font:12px var(--sans);fill:var(--mut)}
.legend-list{display:flex;flex-wrap:wrap;gap:6px 14px;margin-top:10px;
  font-size:12.5px;color:var(--mut)}
.legend-list .sw{display:inline-block;width:10px;height:10px;border-radius:3px;
  margin-right:6px;vertical-align:-1px}
.donut-wrap{display:flex;align-items:center;gap:18px}
.donut{width:180px;height:180px;flex:none}
.two-col{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:18px}
@media (max-width:820px){.two-col{grid-template-columns:1fr}}
.winlist,.outlist{list-style:none;margin:10px 0 0;padding:0;max-height:300px;
  overflow:auto}
.winlist li,.outlist li{padding:7px 10px;border-radius:8px;font-size:13.5px;
  display:flex;gap:8px;align-items:baseline}
.winlist li:nth-child(odd){background:#f6f5f3}
.outlist li:nth-child(odd){background:#f6f5f3}
.winlist .nm,.outlist .nm{font-weight:600;min-width:130px}
.winlist .ct,.outlist .ct{color:var(--faint);font-size:12px}
.pill{display:inline-block;font-size:10.5px;font-weight:700;letter-spacing:.06em;
  padding:2px 8px;border-radius:999px;text-transform:uppercase}
.pill.g{background:#dcfce7;color:#166534}.pill.r{background:#fee2e2;color:#991b1b}

/* ---------- matrix ---------- */
.controls{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:14px;align-items:center}
.controls input[type=search]{flex:1;min-width:200px;padding:9px 14px;font:14px var(--sans);
  border:1px solid var(--line);border-radius:10px;background:#fff;outline:none}
.controls input[type=search]:focus{border-color:var(--acc)}
select{padding:8px 10px;font:13.5px var(--sans);border:1px solid var(--line);
  border-radius:10px;background:#fff;color:var(--ink)}
.chipset{display:flex;flex-wrap:wrap;gap:6px}
.chip{font-size:12px;padding:5px 11px;border-radius:999px;border:1px solid var(--line);
  background:#fff;color:var(--mut);cursor:pointer;user-select:none}
.chip.on{background:var(--ink);color:#fff;border-color:var(--ink)}
.chip:hover{border-color:var(--faint)}
.count{font-size:12.5px;color:var(--mut)}
.table-scroll{overflow-x:auto;border:1px solid var(--line);border-radius:14px;
  background:var(--card)}
table{border-collapse:collapse;width:100%;min-width:1080px;font-size:13.5px}
thead th{position:sticky;top:0;background:#f7f6f4;text-align:left;font-size:11px;
  letter-spacing:.08em;text-transform:uppercase;color:var(--mut);padding:11px 12px;
  border-bottom:1px solid var(--line);cursor:pointer;white-space:nowrap;z-index:2}
thead th:hover{color:var(--ink)}
tbody td{padding:10px 12px;border-bottom:1px solid #f1f0ee;vertical-align:top}
tbody tr.row:hover{background:#fbf5ef;cursor:pointer}
tbody tr:last-child td{border-bottom:none}
td.num{font-family:var(--mono);color:var(--faint);font-size:12px}
.app-nm{font-weight:600;white-space:nowrap}
.app-ct{font-size:11px;color:var(--faint)}
.does{color:#57534e;max-width:230px;font-size:12.5px}
.breadth{color:var(--faint);font-size:11.5px;margin-top:2px}
.b{display:inline-block;font-size:11.5px;font-weight:600;padding:2.5px 9px;
  border-radius:999px;color:#fff;white-space:nowrap}
.b.ghost{background:transparent!important;border:1px solid var(--line);color:var(--mut)}
.ev a{font-size:12.5px;white-space:nowrap}
.ev .st{font-size:10px;margin-left:4px}
.conf{letter-spacing:2px;font-size:10px;color:var(--acc)}
.conf .off{color:#e7e5e4}
tr.detail td{background:#fbfaf8;padding:14px 18px 16px;border-bottom:1px solid var(--line)}
.detail .dgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));
  gap:10px 22px;font-size:12.5px;color:#57534e}
.detail b{display:block;font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;
  color:var(--faint);margin-bottom:3px}
.detail .evlinks a{display:block;font-size:12px;overflow:hidden;text-overflow:ellipsis}
.detail .note{font-style:italic;color:var(--mut)}
.btn{display:inline-block;font:600 13px var(--sans);padding:9px 16px;border-radius:10px;
  border:1px solid var(--line);background:#fff;color:var(--ink);cursor:pointer}
.btn:hover{border-color:var(--acc);color:var(--acc);text-decoration:none}

/* ---------- agent ---------- */
.pipe{width:100%;max-width:840px;display:block;margin:0 auto}
svg .pn{font:700 12.5px var(--sans)}
svg .ps{font:11px var(--sans)}
.stages{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));
  gap:14px;margin-top:26px}
.stage{background:var(--card);border:1px solid var(--line);border-radius:14px;
  padding:18px 20px}
.stage .sn{font-family:var(--mono);font-size:11px;color:var(--acc)}
.stage h4{margin:6px 0 6px;font-size:15.5px}
.stage p{margin:0;font-size:13px;color:var(--mut)}
.stage .tool{margin-top:10px;font-size:11.5px;color:var(--faint);font-family:var(--mono)}
.callout{border-radius:14px;padding:20px 24px;margin-top:22px;font-size:14.5px}
.callout.amber{background:#fef7e8;border:1px solid #f5d9a8}
.callout.amber h4{margin:0 0 8px;color:#92400e;font-size:15px}
.callout.amber ul{margin:0;padding-left:20px}
.callout.amber li{margin:5px 0;color:#78350f}

/* ---------- verification ---------- */
.acc-wrap{display:grid;grid-template-columns:1.1fr .9fr;gap:18px;align-items:start}
@media (max-width:900px){.acc-wrap{grid-template-columns:1fr}}
.miss-table{width:100%;min-width:0;border:1px solid var(--line);border-radius:14px;
  overflow:hidden;font-size:13px;background:var(--card);border-collapse:collapse}
.miss-table th{background:#f7f6f4;font-size:11px;text-transform:uppercase;
  letter-spacing:.08em;color:var(--mut);text-align:left;padding:9px 12px}
.miss-table td{padding:9px 12px;border-top:1px solid #f1f0ee;vertical-align:top}
.miss-table .was{color:var(--red)}
.miss-table .now{color:var(--green)}
.fixed{display:inline-block;font-size:10.5px;font-weight:700;padding:2px 8px;
  border-radius:999px}
.fixed.y{background:#dcfce7;color:#166534}.fixed.n{background:#fee2e2;color:#991b1b}
.steps{counter-reset:st;display:grid;
  grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:14px;margin:20px 0}
.step{background:var(--card);border:1px solid var(--line);border-radius:14px;
  padding:18px 20px;font-size:13.5px;color:var(--mut)}
.step::before{counter-increment:st;content:"0" counter(st);font-family:var(--serif);
  font-size:26px;color:var(--acc);display:block;margin-bottom:6px}
.step b{display:block;color:var(--ink);font-size:14.5px;margin-bottom:4px}
.honesty{background:#111827;color:#e5e7eb;border-radius:16px;padding:26px 30px;
  margin-top:26px}
.honesty h4{margin:0 0 12px;color:#fdba74;font-family:var(--serif);font-size:20px}
.honesty ul{margin:0;padding-left:20px}
.honesty li{margin:7px 0;font-size:14px;color:#d1d5db}
.honesty b{color:#f9fafb}

/* ---------- run ---------- */
.codeblock{background:#141417;color:#d4d4d8;border-radius:14px;padding:20px 24px;
  font:13px/1.7 var(--mono);overflow-x:auto;position:relative;margin:14px 0}
.codeblock .cm{color:#71717a}
.codeblock .k{color:#fdba74}
.tree{font:13px/1.8 var(--mono);color:#57534e;background:var(--card);
  border:1px solid var(--line);border-radius:14px;padding:18px 24px;margin:0;
  white-space:pre;overflow-x:auto}
.tree .d{color:var(--acc);font-weight:600}
.tree .c{color:var(--faint)}
.artifacts{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));
  gap:10px;margin-top:14px}
.art{display:flex;gap:10px;align-items:baseline;background:var(--card);
  border:1px solid var(--line);border-radius:12px;padding:12px 16px;font-size:12.5px}
.art code{color:var(--ink);font-weight:600}
.art span{color:var(--mut)}

footer{padding:44px 0 60px;color:var(--faint);font-size:13px}
footer .wrap{display:flex;flex-wrap:wrap;gap:10px 26px;justify-content:space-between}
@media print{
  nav{display:none} section{padding:30px 0}
  .winlist,.outlist{max-height:none;overflow:visible}
  body{background:#fff}
}
"""
