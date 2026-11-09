"""Step 6: write a self-contained HTML dashboard (output/dashboard.html) from results.json.

Open it in any browser. It loads Chart.js from a CDN, so it needs an internet connection.
"""
from __future__ import annotations
import json
from pathlib import Path

TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RxSignal Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.js"></script>
<style>
:root{--bg:#f6f7f9;--card:#ffffff;--ink:#1d2433;--muted:#5f6b7d;--line:#e3e7ee;
--accent:#2563eb;--accent2:#0f9d8a;--warn:#d9480f;--bad:#c92a2a;--good:#2b8a3e;--soft:#eef3ff}
@media (prefers-color-scheme:dark){:root{--bg:#0f141c;--card:#171e29;--ink:#e6ebf2;--muted:#9aa6b8;
--line:#283244;--accent:#6ea0ff;--accent2:#3fc7b1;--warn:#ff8a4c;--bad:#ff6b6b;--good:#69db7c;--soft:#1d2a40}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:28px 16px 60px}
h1{font-size:26px;margin:0 0 4px;letter-spacing:-.01em}
.sub{color:var(--muted);margin:0 0 22px}
h2{font-size:17px;margin:0 0 4px}
.note{color:var(--muted);font-size:13px;margin:0 0 14px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,300px),1fr));gap:12px;margin-bottom:18px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.kpi .v{font-size:26px;font-weight:700;font-variant-numeric:tabular-nums}
.kpi .l{color:var(--muted);font-size:13px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,520px),1fr));gap:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px;min-width:0}
.card.full{grid-column:1/-1}
.chart{position:relative;height:340px}
table{width:100%;border-collapse:collapse;font-size:14px;font-variant-numeric:tabular-nums}
th,td{text-align:left;padding:8px 6px;border-bottom:1px solid var(--line)}
th{color:var(--muted);font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.03em}
td.num,th.num{text-align:right}
.better{color:var(--good);font-weight:600}.worse{color:var(--warn);font-weight:600}
select{font:inherit;padding:6px 8px;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--ink)}
.tablewrap{overflow-x:auto}
footer{color:var(--muted);font-size:12px;margin-top:22px}
</style>
</head>
<body>
<div class="wrap">
  <h1>RxSignal: FDA Adverse Event Drug Data, Cleaned &amp; Standardized</h1>
  <p class="sub" id="sub"></p>
  <div class="kpis" id="kpis"></div>
  <div class="grid">
    <div class="card full">
      <h2>Data quality scorecard: before vs. after cleaning</h2>
      <p class="note">Same SQL checks run on the raw FDA tables and on the cleaned tables. The biggest issues are inconsistent drug names and missing patient details.</p>
      <div class="tablewrap"><table id="scorecard"></table></div>
    </div>
    <div class="card">
      <h2>How each drug row was normalized</h2>
      <p class="note">Share of drug rows resolved by each layer of the pipeline.</p>
      <div class="chart"><canvas id="methods"></canvas></div>
    </div>
    <div class="card">
      <h2>Top primary-suspect drugs</h2>
      <p class="note">Distinct reports per active ingredient (after normalization).</p>
      <div class="chart"><canvas id="topdrugs"></canvas></div>
    </div>
    <div class="card full">
      <h2>Reports missed without normalization</h2>
      <p class="note">If you counted only the most common spelling of each drug, this share of its reports would be lost.</p>
      <div class="chart"><canvas id="undercount"></canvas></div>
      <div class="tablewrap"><table id="undertable"></table></div>
    </div>
    <div class="card">
      <h2>Serious outcomes by drug</h2>
      <p class="note">% of each drug's reports with hospitalization or death recorded.</p>
      <div class="chart"><canvas id="outcomes"></canvas></div>
    </div>
    <div class="card">
      <h2>Most reported reactions</h2>
      <p class="note">Top 10 reactions for <select id="drugpick"></select></p>
      <div class="chart"><canvas id="reactions"></canvas></div>
    </div>
    <div class="card">
      <h2>Reports by age group and sex</h2>
      <p class="note">After invalid ages were set to Unknown.</p>
      <div class="chart"><canvas id="demo"></canvas></div>
    </div>
    <div class="card">
      <h2>Who submitted the reports</h2>
      <p class="note">Reporter occupation.</p>
      <div class="chart"><canvas id="reporters"></canvas></div>
    </div>
  </div>
  <footer id="foot"></footer>
</div>
<script>
const D = __DATA__;
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const C = {accent:css('--accent'),accent2:css('--accent2'),warn:css('--warn'),bad:css('--bad'),
           good:css('--good'),muted:css('--muted'),line:css('--line'),ink:css('--ink')};
Chart.defaults.color = C.muted; Chart.defaults.borderColor = C.line;
Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
Chart.defaults.maintainAspectRatio = false;
const fmt = n => n == null ? '–' : Number(n).toLocaleString();
const pct = n => n == null ? '–' : Number(n).toFixed(1) + '%';
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const title = s => s ? s.replace(/\b\w/g, c => c.toUpperCase()) : s;

const B = D.quality_before, A = D.quality_after, N = D.normalization;
document.getElementById('sub').textContent =
  `FAERS quarterly extract ${D.quarter.toUpperCase()} · generated ${D.generated} · ` +
  `${fmt(B.duplication.report_rows)} raw report rows, ${fmt(N.drug_rows)} drug rows`;

const maxMiss = D.analysis.undercount.reduce((m,d) => d.pct_missed > m.pct_missed ? d : m,
  {pct_missed: 0, ingredient: ''});
const kpis = [
  [fmt(A.duplication.report_rows), 'adverse event reports analyzed'],
  [pct(N.pct_rows_normalized), `of ${fmt(N.drug_rows)} drug rows mapped to RxNorm`],
  [`${fmt(N.unique_raw_names)} → ${fmt(D.unique_ingredients)}`, 'raw drug spellings → standard ingredients'],
  [D.agreement.pct_agree == null ? '–' : pct(D.agreement.pct_agree), 'agreement with FDA-coded ingredient'],
  [pct(maxMiss.pct_missed), `of ${esc(title(maxMiss.ingredient))} reports missed without normalization`],
  [pct(100 - A.completeness_demo.pct_weight), 'of reports missing patient weight'],
];
document.getElementById('kpis').innerHTML = kpis.map(([v,l]) =>
  `<div class="kpi"><div class="v">${v}</div><div class="l">${l}</div></div>`).join('');

// Scorecard
// Each row: metric, before, after, format, kind. Small source issues are labeled honestly
// instead of being called "improved".
const rows = [
  ['Distinct drug identifiers', B.unique_raw_drug_names, D.unique_ingredients, 'count', 'down'],
  ['Drug rows on a standard vocabulary', 0, N.pct_rows_normalized, 'pct', 'up'],
  ['Age filled in', B.completeness_demo.pct_age, A.completeness_demo.pct_age, 'pct', 'missing'],
  ['Sex reported (F/M)', B.completeness_demo.pct_sex, A.completeness_demo.pct_sex, 'pct', 'missing'],
  ['Event date filled in', B.completeness_demo.pct_event_date, A.completeness_demo.pct_event_date, 'pct', 'missing'],
  ['Weight filled in', B.completeness_demo.pct_weight, A.completeness_demo.pct_weight, 'pct', 'missing'],
  ['Duplicate case versions', B.duplication.superseded_versions, A.duplication.superseded_versions, 'count', 'check'],
  ['Invalid ages / weights / event dates',
   B.validity.invalid_ages + B.validity.invalid_weights + B.validity.invalid_event_dates,
   A.validity.invalid_ages + A.validity.invalid_weights + A.validity.invalid_event_dates, 'count', 'check'],
  ['Uninformative drug names ("UNKNOWN", ...)', B.uninformative_names.uninformative_rows,
   A.uninformative_names.uninformative_rows, 'count', 'flag'],
];
document.getElementById('scorecard').innerHTML =
  '<tr><th>Metric</th><th class="num">Before</th><th class="num">After</th><th>Note</th></tr>' +
  rows.map(([m,b,a,t,kind]) => {
    const f = t === 'pct' ? pct : fmt;
    let cls = '', note = '';
    if (kind === 'down' && a < b) { cls = 'better'; note = `${(100 * (1 - a / b)).toFixed(0)}% fewer`; }
    if (kind === 'up' && a > b)   { cls = 'better'; note = 'standardized'; }
    if (kind === 'missing') note = b < 50 ? 'major gap in the source data' : b < 90 ? 'often missing' : '';
    if (kind === 'check') note = b === 0 ? 'none found' : `few in source; ${fmt(b)} fixed`;
    if (kind === 'flag') note = 'excluded from drug counts';
    return `<tr><td>${m}</td><td class="num">${f(b)}</td><td class="num ${cls}">${f(a)}</td><td>${note}</td></tr>`;
  }).join('');

// Normalization methods
const METHOD_LABELS = {rxnorm_exact:'RxNorm exact', rxnorm_approx:'RxNorm fuzzy (verified)',
  llm_verified:'LLM + RxNorm check', unresolved:'Not matched', uninformative:'Uninformative name',
  not_looked_up:'Rare name (not looked up)'};
const order = Object.keys(METHOD_LABELS).filter(k => N.rows_by_method[k]);
const tot = order.reduce((s,k) => s + N.rows_by_method[k], 0);
new Chart(document.getElementById('methods'), {type:'bar',
  data:{labels:order.map(k=>METHOD_LABELS[k]), datasets:[{data:order.map(k=>100*N.rows_by_method[k]/tot),
  backgroundColor:order.map(k=>['rxnorm_exact','rxnorm_approx','llm_verified'].includes(k)?C.accent2:C.muted)}]},
  options:{indexAxis:'y',plugins:{legend:{display:false},tooltip:{callbacks:{label:c=>
    `${c.parsed.x.toFixed(1)}% (${fmt(N.rows_by_method[order[c.dataIndex]])} rows)`}}},
    scales:{x:{ticks:{callback:v=>v+'%'}}}}});

// Top drugs
new Chart(document.getElementById('topdrugs'), {type:'bar',
  data:{labels:D.analysis.top_drugs.map(d=>title(d.ingredient)),
        datasets:[{data:D.analysis.top_drugs.map(d=>d.reports), backgroundColor:C.accent}]},
  options:{indexAxis:'y',plugins:{legend:{display:false}},scales:{y:{ticks:{autoSkip:false,font:{size:11}}}}}});

// Undercount
const U = D.analysis.undercount.slice().sort((a,b)=>b.pct_missed-a.pct_missed);
new Chart(document.getElementById('undercount'), {type:'bar',
  data:{labels:U.map(d=>title(d.ingredient)), datasets:[{data:U.map(d=>d.pct_missed), backgroundColor:C.warn}]},
  options:{plugins:{legend:{display:false},tooltip:{callbacks:{label:c=>
    `${c.parsed.y}% missed (${fmt(U[c.dataIndex].reports_missed)} of ${fmt(U[c.dataIndex].reports)} reports)`}}},
    scales:{y:{ticks:{callback:v=>v+'%'}},x:{ticks:{autoSkip:false,maxRotation:60,font:{size:11}}}}}});
document.getElementById('undertable').innerHTML =
  '<tr><th>Ingredient</th><th>Most common spelling</th><th class="num">Spellings</th><th class="num">Reports (normalized)</th><th class="num">Reports (top spelling only)</th><th class="num">Missed</th></tr>' +
  U.slice(0,10).map(d=>`<tr><td>${esc(title(d.ingredient))}</td><td>${esc(d.top_spelling)}</td><td class="num">${fmt(d.spellings)}</td><td class="num">${fmt(d.reports)}</td><td class="num">${fmt(d.reports_top_spelling)}</td><td class="num worse">${pct(d.pct_missed)}</td></tr>`).join('');

// Outcomes
const O = D.analysis.outcomes.slice(0,10);
new Chart(document.getElementById('outcomes'), {type:'bar',
  data:{labels:O.map(d=>title(d.ingredient)), datasets:[
    {label:'Hospitalization', data:O.map(d=>d.pct_hospitalization), backgroundColor:C.accent},
    {label:'Death', data:O.map(d=>d.pct_death), backgroundColor:C.bad}]},
  options:{plugins:{legend:{position:'bottom'}},scales:{y:{ticks:{callback:v=>v+'%'}},
    x:{ticks:{autoSkip:false,maxRotation:60,font:{size:11}}}}}});

// Reactions with a picker
const R = D.analysis.reactions, picks = [...new Set(R.map(r=>r.ingredient))];
const sel = document.getElementById('drugpick');
sel.innerHTML = picks.map(p=>`<option value="${esc(p)}">${esc(title(p))}</option>`).join('');
let rchart;
function drawReactions(){
  const rows = R.filter(r=>r.ingredient===sel.value);
  if (rchart) rchart.destroy();
  rchart = new Chart(document.getElementById('reactions'), {type:'bar',
    data:{labels:rows.map(r=>title(r.reaction.toLowerCase())), datasets:[{data:rows.map(r=>r.pct_of_drug_reports), backgroundColor:C.accent2}]},
    options:{indexAxis:'y',plugins:{legend:{display:false},tooltip:{callbacks:{label:c=>
      `${c.parsed.x}% of reports (${fmt(rows[c.dataIndex].reports)})`}}},scales:{x:{ticks:{callback:v=>v+'%'}},
      y:{ticks:{autoSkip:false,font:{size:11}}}}}});
}
sel.addEventListener('change', drawReactions); if (picks.length) drawReactions();

// Demographics
const ages = ['0-17','18-44','45-64','65-74','75+','Unknown'];
const sexes = [['F','Female',C.accent],['M','Male',C.accent2],['Unknown','Unknown',C.muted]];
new Chart(document.getElementById('demo'), {type:'bar',
  data:{labels:ages, datasets:sexes.map(([k,l,c])=>({label:l, backgroundColor:c,
    data:ages.map(a=>(D.analysis.demographics.find(d=>d.sex===k&&d.age_group===a)||{}).reports||0)}))},
  options:{plugins:{legend:{position:'bottom'}},scales:{x:{stacked:true},y:{stacked:true}}}});

// Reporters
const RP = D.analysis.reporters;
new Chart(document.getElementById('reporters'), {type:'bar',
  data:{labels:RP.map(r=>r.reporter), datasets:[{data:RP.map(r=>r.reports), backgroundColor:C.accent}]},
  options:{indexAxis:'y',plugins:{legend:{display:false}}}});

document.getElementById('foot').textContent =
  'Source: U.S. FDA Adverse Event Reporting System (FAERS) public quarterly data; drug vocabulary: NLM RxNorm. ' +
  'FAERS reports do not prove a drug caused a reaction, and report counts do not measure how common a reaction is.';
</script>
</body>
</html>
"""


def write_dashboard(results: dict, path: Path) -> None:
    html = TEMPLATE.replace("__DATA__", json.dumps(results, default=str).replace("</", "<\\/"))
    path.write_text(html, encoding="utf-8")
