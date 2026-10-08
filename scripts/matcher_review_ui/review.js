'use strict';
const $ = id => document.getElementById(id);
const fields = ['reviewer', 'review_notes', 'failure_cause', 'wrong_family', 'prepared_food_false_positive', 'structurally_correct'];
let rows = [], revision = 0, current = 0, saving = false, failed = false, labels = [], queue = Promise.resolve(), pending = 0;
function node(tag, text) { const el = document.createElement(tag); el.textContent = text; return el; }
function json(value) { try { return JSON.parse(value); } catch { return value; } }
function visible() { return rows.map((r, i) => i).filter(i => (!$('group').value || rows[i].sample_group === $('group').value) && (!$('unreviewed').checked || !rows[i].review_label)); }
function progress() {
 const done = rows.filter(r => r.review_label).length;
 $('progress').textContent = `${done} / ${rows.length} reviewed · ${rows.length - done} remaining · ${(100 * done / rows.length).toFixed(1)}% complete`;
 $('bar').max = rows.length; $('bar').value = done;
}
function detail(parent, title, value) { const section = node('section', ''); section.append(node('h2', title), node('pre', typeof value === 'string' ? value : JSON.stringify(value, null, 2))); parent.append(section); }
function render() {
 progress(); const allowed = visible();
 if (!allowed.includes(current)) current = allowed[0] ?? -1;
 $('case').replaceChildren(); $('decisionToolbar').hidden = current < 0; $('reviewFields').disabled = failed || current < 0;
 $('prev').disabled = $('next').disabled = saving || failed || current < 0;
 if (current < 0) { $('case').append(node('p', 'No cases in this filter. Clear “Unreviewed only” or change group to inspect completed reviews.')); return; }
 const r = rows[current]; localStorage.setItem('matcher-review-last-case', r.case_id);
 $('case').append(node('p', `Original case ${current + 1} of ${rows.length} · ${r.case_id} · ${r.sample_group}`), node('h2', r.ingredient_query));
 const dl = node('dl', '');
 for (const [title, key] of [['Decision', 'current_matcher_decision'], ['Selected product', 'selected_product'], ['Match type', 'match_type'], ['Confidence', 'confidence'], ['Food family', 'food_family'], ['Subfamily', 'subfamily']]) dl.append(node('dt', title), node('dd', r[key] || 'None returned'));
 $('case').append(dl);
 const attrs = node('div', ''); attrs.className = 'attributes';
 detail(attrs, 'Ingredient identity / all attributes', json(r.key_attributes)); detail(attrs, 'Selected product identity / all attributes', json(r.selected_product_ontology)); $('case').append(attrs);
 detail($('case'), 'Score breakdown', json(r.score_breakdown)); detail($('case'), 'Matcher reason codes', json(r.reason_codes));
 $('case').append(node('h2', 'Top alternatives'));
 const alternatives = json(r.top_3_alternatives);
 if (!alternatives.length) $('case').append(node('p', 'No alternatives returned. This does not prove there is no suitable inventory product.'));
 for (const alternative of alternatives) { const div = node('section', ''); div.className = 'alternative'; div.append(node('h3', alternative.product_name || alternative.product_id)); detail(div, 'Candidate status and attributes', {status:alternative.candidate_status, match_type:alternative.match_type || alternative.structural_decision, confidence:alternative.confidence || 'Not assigned to diagnostic candidate', score:alternative.final_score, ontology:alternative.ontology, score_breakdown:alternative.score_breakdown, note:alternative.note}); const extra = node('details',''); extra.append(node('summary','Complete candidate record'), node('pre',JSON.stringify(alternative,null,2))); div.append(extra); $('case').append(div); }
 $('interpretation').textContent = r.current_matcher_decision === 'accepted' ? 'ACCEPTED: normally CORRECT, ACCEPTABLE_SUBSTITUTE, WRONG or AMBIGUOUS. WRONG means an incorrect accepted product. SHOULD_HAVE_MATCHED is normally reserved for rejections.' : 'REJECTED / NO MATCH: CORRECT means the rejection was correct; SHOULD_HAVE_MATCHED means a suitable match was missed; AMBIGUOUS means uncertain. WRONG and ACCEPTABLE_SUBSTITUTE normally describe accepted products.';
 for (const field of fields) $(field).value = r[field] || (field === 'reviewer' ? localStorage.getItem('matcher-reviewer') || '' : '');
 for (const button of $('labels').children) { button.setAttribute('aria-pressed', String(button.dataset.label === r.review_label)); button.disabled = failed; }
}
function save(label) {
 if (failed || current < 0) return;
 const r = rows[current], values = Object.fromEntries(fields.map(f => [f, $(f).value]));
 values.review_label = label ?? r.review_label;
 // Draft values are exclusively manual input. Queue snapshots so rapid label
 // and field changes cannot race or overwrite a later click with an old label.
 Object.assign(r, values); pending++; saving = true;
 $('status').textContent = 'Saving…';
 for (const id of ['prev','next','group','unreviewed','go','jump']) $(id).disabled = true;
 localStorage.setItem('matcher-reviewer', values.reviewer);
 queue = queue.then(async () => {
  if (failed) return;
  try {
   const response = await fetch('/api/label', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({case_id:r.case_id, values, revision}), keepalive:true});
   const result = await response.json(); if (!response.ok) throw new Error(result.error);
   revision = result.revision;
  } catch (error) {
   failed = true; $('status').className = 'error';
   $('status').textContent = `SAVE FAILED: ${error.message}. Keep this page open. Copy your notes before reloading; unsaved edits have not been committed.`;
  }
 }).finally(() => {
  pending--; saving = pending > 0;
  if (!saving && !failed) {
   $('status').textContent = 'Saved to review_labels.json and review_labeled.csv';
   for (const id of ['prev','next','group','unreviewed','go','jump']) $(id).disabled = false;
  }
  progress();
  for (const button of $('labels').children) button.setAttribute('aria-pressed', String(button.dataset.label === rows[current]?.review_label));
  if (failed) $('reviewFields').disabled = true;
 });
 return queue;
}
function navigate(step) { if (saving || failed) return; const list = visible(), pos = list.indexOf(current); if (list.length) current = list[Math.max(0, Math.min(list.length - 1, pos + step))]; render(); window.scrollTo(0,0); }
$('prev').onclick = () => navigate(-1); $('next').onclick = () => navigate(1);
for (const id of ['group', 'unreviewed']) $(id).onchange = () => { if (!saving && !failed) render(); };
$('go').onclick = () => { if (saving || failed) return; const value = $('jump').value.trim(); const i = /^\d+$/.test(value) ? Number(value) - 1 : rows.findIndex(r => r.case_id === value); if (i < 0 || i >= rows.length) { $('status').textContent = 'Case not found'; return; } $('group').value = ''; $('unreviewed').checked = false; current = i; render(); };
for (const field of fields) $(field).onchange = () => save();
document.addEventListener('keydown', event => {
 if (event.target.closest('input, textarea, select') || event.ctrlKey || event.altKey || event.metaKey || event.repeat) return;
 if (/^[1-5]$/.test(event.key)) { event.preventDefault(); save(labels[Number(event.key) - 1]); }
 if (event.key === 'ArrowRight') { event.preventDefault(); navigate(1); }
 if (event.key === 'ArrowLeft') { event.preventDefault(); navigate(-1); }
});
fetch('/api/cases').then(r => { if (!r.ok) throw new Error('Cannot load sample'); return r.json(); }).then(data => {
 rows = data.cases; revision = data.revision; labels = data.labels;
 for (const group of [...new Set(rows.map(r => r.sample_group))]) { const opt = node('option', group); opt.value = group; $('group').append(opt); }
 for (const cause of data.causes) $('failure_cause').append(node('option', cause));
 labels.forEach((label, i) => { const button = node('button', `${i + 1} · ${label}`); button.dataset.label = label; button.onclick = () => save(label); $('labels').append(button); });
 const last = localStorage.getItem('matcher-review-last-case'); current = Math.max(0, rows.findIndex(r => r.case_id === last)); $('status').textContent = 'Ready · no answers are prefilled'; render();
}).catch(error => { $('status').className = 'error'; $('status').textContent = error.message; });
