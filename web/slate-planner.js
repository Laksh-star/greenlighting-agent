const $ = (selector) => document.querySelector(selector);
const esc = (value) => String(value ?? "").replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
const money = (value) => new Intl.NumberFormat('en-US', {style:'currency', currency:'USD', maximumFractionDigits:0}).format(value);
let projects = [], selected = new Set(), plan = null, revision = 0;
async function json(url, options) {
  const response = await fetch(url, options);
  const payload = await response.json();
  if (!response.ok) throw new Error(typeof payload.detail === 'string' ? payload.detail : 'Check the funding cap and selection.');
  return payload;
}
function renderProjects() {
  const filter = $('#filter').value.toLowerCase();
  $('#projects').innerHTML = projects.filter(p => `${p.project_name} ${p.genre} ${p.producer_decision}`.toLowerCase().includes(filter)).map(p => `
    <tr><td><input type="checkbox" data-id="${esc(p.id)}" aria-label="Select ${esc(p.project_name)}" ${selected.has(p.id) ? 'checked' : ''} ${p.eligible ? '' : 'disabled'}></td>
    <td>${esc(p.project_name)}<small>${esc(p.version_label || 'Standalone report')} · ${esc(p.genre)} · ${esc(p.platform)}${p.demo_mode ? ' · Demo sample' : ''}</small>${p.conditions ? `<small>Conditions: ${esc(p.conditions)}</small>` : ''}${p.eligible ? '' : '<small>Missing exposure or base ROI</small>'}</td>
    <td>${p.exposure === null ? 'n/a' : money(p.exposure)}</td><td>${p.rois.Base === null ? 'n/a' : `${p.rois.Base.toFixed(1)}%`}</td>
    <td>${esc(p.overall_risk_score ?? 'n/a')}</td><td>${esc(p.recommendation)}</td><td>${esc(p.producer_decision)}</td></tr>`).join('') || '<tr><td colspan="7">No matching saved projects.</td></tr>';
}
async function update(suggest = false) {
  const current = ++revision;
  $('#download').disabled = true;
  try {
    const cap = Number($('#funding-cap').value);
    if (!Number.isSafeInteger(cap) || cap <= 0) throw new Error('Enter a positive whole-dollar funding cap.');
    const result = await json('/api/slate-planner/plan', {method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({funding_cap:cap, selected_ids:[...selected], suggest})});
    if (current !== revision) return;
    plan = result;
    selected = new Set(plan.selected_ids);
    renderProjects();
    $('#summary').innerHTML = `<div><span>Selected projects</span><strong>${selected.size}</strong></div><div><span>Total exposure</span><strong>${money(plan.total_exposure)}</strong></div><div><span>Funding cap</span><strong>${money(plan.funding_cap)}</strong></div><div class="${plan.over_cap ? 'over-cap' : ''}"><span>${plan.over_cap ? 'Over cap' : 'Remaining'}</span><strong>${money(Math.abs(plan.remaining))}</strong></div>`;
    $('#scenarios').innerHTML = plan.scenarios.map(s => `<div class="scenario">${esc(s.scenario)}<strong>${s.modeled_profit === null ? 'n/a' : money(s.modeled_profit)}</strong>Modeled profit · ${s.weighted_roi === null ? 'ROI n/a' : `${s.weighted_roi}% ROI`}<br>Coverage: ${s.coverage}/${s.total} projects</div>`).join('');
    $('#mix').innerHTML = plan.genre_mix.map(g => `<div class="genre"><span>${esc(g.genre)}</span><span>${g.share}% · ${money(g.exposure)}</span></div>`).join('') || 'No projects selected.';
    $('#warnings').innerHTML = plan.warnings.map(w => `<li>${esc(w)}</li>`).join('') || '<li>No review flags for this selection.</li>';
    $('#status').textContent = plan.method;
    $('#status').className = '';
    $('#download').disabled = !selected.size;
  } catch(error) {
    if (current !== revision) return;
    plan = null;
    $('#status').textContent = error.message;
    $('#status').className = 'error';
    $('#summary').innerHTML = '';
    $('#scenarios').innerHTML = '';
    $('#mix').innerHTML = '';
    $('#warnings').innerHTML = '';
  }
}
$('#projects').addEventListener('change', (event) => {
  if (!event.target.dataset.id) return;
  if (event.target.checked) selected.add(event.target.dataset.id); else selected.delete(event.target.dataset.id);
  update();
});
$('#filter').addEventListener('input', renderProjects);
$('#funding-cap').addEventListener('input', () => update());
$('#suggest').addEventListener('click', () => update(true));
$('#clear').addEventListener('click', () => { selected.clear(); update(); });
$('#download').addEventListener('click', () => {
  if (!plan) return;
  const url = URL.createObjectURL(new Blob([JSON.stringify({...plan, generated_at:new Date().toISOString()}, null, 2)], {type:'application/json'}));
  const a = document.createElement('a'); a.href = url; a.download = 'slate-budget-plan.json'; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
});
try { projects = (await json('/api/slate-planner')).projects; renderProjects(); await update(); }
catch(error) { $('#status').textContent = error.message; $('#status').className = 'error'; }
