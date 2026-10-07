export function renderMilestones(container, workspace, {esc, json, refresh, toast}) {
  const names = workspace.milestones.map(m => m.milestone);
  const statuses = ['Not started', 'In progress', 'Blocked', 'Complete'];
  container.innerHTML = `<p class="section-title">Development milestones <span>${workspace.milestones.filter(m=>m.status==='Complete').length}/5 complete</span></p>
    <ul class="rows">${workspace.milestones.map(m=>`<li><span>${esc(m.milestone)}</span><span>${esc(m.status)}</span></li>`).join('')}</ul>
    <details><summary>Update milestone</summary><form class="milestone-form">
      <label class="field"><span>Milestone</span><select name="milestone">${names.map(n=>`<option>${esc(n)}</option>`).join('')}</select></label>
      <label class="field"><span>Status</span><select name="status">${statuses.map(n=>`<option>${esc(n)}</option>`).join('')}</select></label>
      <label class="field"><span>Owner</span><input name="owner" maxlength="120"></label>
      <label class="field"><span>Due date</span><input name="due_date" type="date"></label>
      <label class="field"><span>Notes</span><textarea name="notes" rows="2" required maxlength="5000"></textarea></label>
      <button class="btn btn-primary" type="submit">Save milestone</button>
    </form></details>
    <details><summary>Milestone history (${workspace.milestone_history.length})</summary>
      <ul class="drivers">${workspace.milestone_history.map(e=>`<li><b>${esc(e.milestone)} · ${esc(e.status)}</b><p>${esc(e.owner || 'Unassigned')} · ${esc(e.due_date || 'No due date')} · version ${e.version}</p><p>${esc(e.notes)}</p><small>${esc(new Date(e.created_at).toLocaleString())}</small></li>`).join('') || '<li>No updates recorded.</li>'}</ul>
    </details>`;
  const form = container.querySelector('form');
  const populate = () => {
    const entry = workspace.milestones.find(m=>m.milestone===form.elements.milestone.value);
    for (const name of ['status','owner','due_date','notes']) form.elements[name].value = entry[name] || '';
  };
  form.elements.milestone.addEventListener('change', populate);
  populate();
  form.addEventListener('submit', async event=>{
    event.preventDefault();
    const button = form.querySelector('button'); button.disabled = true;
    const data = Object.fromEntries(new FormData(form));
    try {
      await json(`/api/projects/${encodeURIComponent(workspace.id)}/milestones`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({...data, due_date:data.due_date||null, version:workspace.versions[0].number})});
      await refresh(); toast('Milestone saved.');
    } catch(error) { toast(error.message); }
    finally { button.disabled = false; }
  });
}

export async function renderEvidence(container, reportId, {esc, json}) {
  const data = await json(`/api/reports/${encodeURIComponent(reportId)}/evidence`);
  if (!container.isConnected) return;
  container.innerHTML = `<details><summary>Evidence provenance</summary>
    <ul class="drivers">${data.evidence.map(e=>`<li><b>${esc(e.description)}</b><p>${esc(e.source)}${e.dataset_id ? ` · ${esc(e.dataset_id)}` : ''}</p><small>${esc(e.retrieved_at || 'Retrieval date not recorded / not applicable')}</small>${/^https?:\/\//.test(e.url) ? `<p><a href="${esc(e.url)}" target="_blank" rel="noopener">Source</a></p>` : ''}</li>`).join('')}</ul>
    <p class="section-title">Driver support</p><ul class="drivers">${data.decision_drivers.map(d=>`<li>${esc(d.text)}<p><b>${esc(d.status)}</b> · ${esc(d.evidence_ids.join(', ') || 'No evidence link')}</p></li>`).join('')}</ul>
    <ul class="drivers">${data.warnings.map(w=>`<li>${esc(w)}</li>`).join('')}</ul>
  </details>`;
}

export function renderStress(container, reportId, payload, {esc, json, money, toast}) {
  const assumptions = payload?.financial_assumptions || {};
  container.innerHTML = `<details><summary>Financial stress test</summary><form class="stress-form">
    <label class="field"><span>Revenue / subscriber value multiplier <output class="multiplier-value">1.00×</output></span><input name="revenue_multiplier" type="range" min="0" max="3" step="0.05" value="1"></label>
    <label class="field"><span>Production overrun <output class="overrun-value">0%</output></span><input name="overrun_pct" type="range" min="0" max="100" step="5" value="0"></label>
    <label class="field"><span>Marketing spend (USD)</span><input name="marketing_spend" type="number" min="0" step="1" value="${assumptions.marketing_spend === undefined ? '' : Number(assumptions.marketing_spend)||0}" placeholder="Saved model default"></label>
    <button class="btn btn-primary" type="submit">Calculate stress case</button>
  </form><div class="stress-result" aria-live="polite"></div></details>`;
  const form = container.querySelector('form');
  form.elements.revenue_multiplier.addEventListener('input', ()=>{container.querySelector('.multiplier-value').value=`${Number(form.elements.revenue_multiplier.value).toFixed(2)}×`;});
  form.elements.overrun_pct.addEventListener('input', ()=>{container.querySelector('.overrun-value').value=`${form.elements.overrun_pct.value}%`;});
  form.addEventListener('submit', async event=>{
    event.preventDefault();
    const button = form.querySelector('button'); button.disabled = true;
    try {
      const result = await json(`/api/reports/${encodeURIComponent(reportId)}/stress`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({revenue_multiplier:Number(form.elements.revenue_multiplier.value), overrun_pct:Number(form.elements.overrun_pct.value), marketing_spend:form.elements.marketing_spend.value === '' ? null : Number(form.elements.marketing_spend.value)})});
      if (!container.isConnected) return;
      container.querySelector('.stress-result').innerHTML = `<p><b>Stress exposure:</b> ${money(result.total_exposure)}</p><p><b>Break-even ${result.break_even_subscribers === null ? 'gross' : 'subscribers'}:</b> ${result.break_even_subscribers === null ? result.break_even_gross === null ? 'Unavailable at zero net share' : money(result.break_even_gross) : Number(result.break_even_subscribers).toLocaleString()}</p><ul class="rows">${result.scenarios.map(s=>`<li><span>${esc(s.scenario)}</span><span>${s.roi===null ? 'n/a' : `${s.roi}%`}</span><span>${esc(s.financial_signal || 'Unavailable')}</span></li>`).join('')}</ul><p class="sample-note">${esc(result.note)}</p><p>Original AI: ${esc(result.original_recommendation)}</p>`;
    } catch(error) { toast(error.message); }
    finally { button.disabled = false; }
  });
}
