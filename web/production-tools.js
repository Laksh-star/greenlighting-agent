const fields = ['production_spend','marketing_spend','gross_revenue','studio_receipts'];
const labels = {production_spend:'Production spend',marketing_spend:'Marketing spend',gross_revenue:'Gross revenue',studio_receipts:'Studio cash receipts'};
const dollars = v => v===null || v===undefined ? 'Unknown' : new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',maximumFractionDigits:2}).format(v);
const today = () => {const d=new Date();return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;};

export async function renderProduction(actuals, constraints, workspace, helpers) {
  const data = await helpers.json(`/api/projects/${encodeURIComponent(workspace.id)}/production`);
  if (!actuals.isConnected || !constraints.isConnected) return;
  renderActuals(actuals, data, workspace, helpers);
  renderConstraints(constraints, data, workspace, helpers);
}

function renderActuals(container, data, workspace, {esc,json,refresh,toast}) {
  const comparison = data.comparison;
  container.innerHTML = `<details><summary>Actuals versus forecast</summary>
    <div class="actuals-comparison" aria-live="polite">${comparison ? `<p><b>${esc(comparison.version_label)}</b> · ${esc(comparison.snapshot.as_of)} · ${esc(comparison.snapshot.phase)} · USD</p>
      <div class="version-table"><table><thead><tr><th>Amount</th><th>Cumulative actual</th><th>Full forecast</th><th>Difference</th></tr></thead><tbody>${comparison.rows.map(r=>`<tr><th scope="row">${esc(labels[r.field])}</th><td data-label="Actual">${dollars(r.actual)}</td><td data-label="Forecast">${dollars(r.forecast)}</td><td data-label="Difference">${dollars(r.variance)}</td></tr>`).join('')}</tbody></table></div>
      <p><b>Cash profit to date:</b> ${dollars(comparison.cash_profit)} · <b>Cash ROI:</b> ${comparison.cash_roi===null ? 'Unknown' : `${comparison.cash_roi}%`}</p>
      <p>${esc(comparison.snapshot.notes)}</p><ul class="drivers">${comparison.warnings.map(w=>`<li>${esc(w)}</li>`).join('')}</ul>` : '<p>No actual snapshots recorded.</p>'}</div>
    ${data.actual_snapshots.length ? `<label class="field"><span>Snapshot history</span><select class="snapshot-history">${data.actual_snapshots.map(s=>`<option value="${s.id}" ${comparison?.snapshot.id===s.id?'selected':''}>${esc(s.as_of)} · ${esc(s.phase)} · version ${s.version} · #${s.id}</option>`).join('')}</select></label>` : ''}
    <details><summary>Record cumulative snapshot</summary><form class="actuals-form">
      <label class="field"><span>Compare with analysis version</span><select name="version">${workspace.versions.map(v=>`<option value="${v.number}">${v.number} · ${esc(v.label)}</option>`).join('')}</select></label>
      <div class="field-row"><label class="field"><span>As-of date</span><input name="as_of" type="date" value="${today()}" required></label><label class="field"><span>Reporting phase</span><select name="phase"><option>Interim</option><option>Final</option></select></label></div>
      ${fields.map(f=>`<label class="field"><span>${labels[f]} (USD, cumulative)</span><input name="${f}" type="number" min="0" step="0.01" placeholder="Unknown"></label>`).join('')}
      <label class="field"><span>Notes</span><textarea name="notes" rows="2" required maxlength="5000"></textarea></label>
      <button class="btn btn-primary" type="submit">Save actuals snapshot</button>
    </form></details>
    <details><summary>Import actuals CSV</summary><a class="btn btn-ghost" href="/api/actuals/template">Download CSV template</a>
      <form class="actuals-import"><label class="field"><span>Cumulative snapshots CSV</span><input type="file" name="csv" accept=".csv,text/csv" required></label><button class="btn btn-primary" type="submit">Import snapshots</button></form>
    </details>
  </details>`;
  const history = container.querySelector('.snapshot-history');
  history?.addEventListener('change', async ()=>{
    try {
      const selected = await json(`/api/projects/${encodeURIComponent(workspace.id)}/production?snapshot_id=${history.value}`);
      if (!container.isConnected) return;
      renderActuals(container, selected, workspace, {esc,json,refresh,toast});
      container.querySelector('details').open=true;
    } catch(error) {toast(error.message);}
  });
  container.querySelector('.actuals-form').addEventListener('submit', async event=>{
    event.preventDefault(); const form=event.currentTarget;const button=form.querySelector('button');button.disabled=true;
    const body=Object.fromEntries(new FormData(form));body.version=Number(body.version);
    for(const f of fields) if(body[f]==='')body[f]=null;
    try {
      const result=await json(`/api/projects/${encodeURIComponent(workspace.id)}/actuals`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
      await refresh();toast(result.imported ? 'Actuals snapshot saved.' : 'Exact duplicate skipped.');
    } catch(error){toast(error.message);}finally{button.disabled=false;}
  });
  container.querySelector('.actuals-import').addEventListener('submit',async event=>{
    event.preventDefault();const form=event.currentTarget;const button=form.querySelector('button');button.disabled=true;
    try {
      const file=form.elements.csv.files[0];if(!file || file.size>200000)throw new Error('Choose a CSV file under 200 KB.');
      const result=await json(`/api/projects/${encodeURIComponent(workspace.id)}/actuals/import`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({csv_text:await file.text()})});
      await refresh();toast(`${result.imported} snapshots imported; ${result.skipped_duplicates} exact duplicates skipped.`);
    }catch(error){toast(error.message);}finally{button.disabled=false;}
  });
}

function renderConstraints(container, data, workspace, {esc,json,refresh,toast}) {
  const categories=['Cast/Talent','Location','Availability','VFX','Schedule'];
  const statuses=['Proposed','Pending','Confirmed','Blocked','Released'];
  container.innerHTML=`<details><summary>Production constraints · ${data.blocker_count} ${data.blocker_count===1?'blocker':'blockers'}</summary>
    <ul class="drivers">${data.constraints.map(c=>`<li><b>${esc(c.title)} · ${esc(c.status)}</b><p>${esc(c.category)} · ${esc(c.owner||'Unassigned')} · ${esc(c.start_date||'No start date')} / ${esc(c.end_date||'No end date')}</p><p>${esc(c.notes)}</p></li>`).join('') || '<li>No constraints recorded.</li>'}</ul>
    <details><summary>Add or update constraint</summary><form class="constraint-form">
      <label class="field"><span>Constraint record</span><select name="constraint_id"><option value="">New constraint</option>${data.constraints.map(c=>`<option value="${esc(c.constraint_id)}">${esc(c.title)}</option>`).join('')}</select></label>
      <label class="field"><span>Category</span><select name="category">${categories.map(v=>`<option>${v}</option>`).join('')}</select></label>
      <label class="field"><span>Title</span><input name="title" required maxlength="160"></label>
      <label class="field"><span>Status</span><select name="status">${statuses.map(v=>`<option>${v}</option>`).join('')}</select></label>
      <label class="field"><span>Owner / contact</span><input name="owner" maxlength="120"></label>
      <div class="field-row"><label class="field"><span>Window starts</span><input name="start_date" type="date"></label><label class="field"><span>Window ends</span><input name="end_date" type="date"></label></div>
      <label class="field"><span>Notes</span><textarea name="notes" rows="2" required maxlength="5000"></textarea></label>
      <button class="btn btn-primary" type="submit">Save constraint</button>
    </form></details>
    <details><summary>Constraint history (${data.constraint_history.length})</summary><ul class="drivers">${data.constraint_history.map(c=>`<li><b>${esc(c.title)} · ${esc(c.status)}</b><p>Version ${c.version} · ${esc(new Date(c.created_at).toLocaleString())}</p><p>${esc(c.notes)}</p></li>`).join('') || '<li>No updates recorded.</li>'}</ul></details>
  </details>`;
  const form=container.querySelector('form');
  form.elements.constraint_id.addEventListener('change',()=>{
    const current=data.constraints.find(c=>c.constraint_id===form.elements.constraint_id.value);
    for(const name of ['category','title','status','owner','start_date','end_date','notes']) form.elements[name].value=current?.[name]||({category:'Cast/Talent',status:'Proposed'}[name]||'');
  });
  form.addEventListener('submit',async event=>{
    event.preventDefault();const button=form.querySelector('button');button.disabled=true;
    const body=Object.fromEntries(new FormData(form));body.version=workspace.versions[0].number;
    body.start_date=body.start_date||null;body.end_date=body.end_date||null;
    try {
      await json(`/api/projects/${encodeURIComponent(workspace.id)}/constraints`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
      await refresh();toast('Production constraint saved.');
    }catch(error){toast(error.message);}finally{button.disabled=false;}
  });
}
