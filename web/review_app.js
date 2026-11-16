/* Offline CIM review editor. No network requests, storage synchronization, or automatic judgments. */
(() => {
  'use strict';
  const DATA = JSON.parse(document.getElementById('observer-data').textContent);
  const reviewKeys = globalThis.CimReviewKeys.createCodec(JSON.parse(document.getElementById('review-key-map-data').textContent));
  const LABELS = ['ALIGNED', 'POTENTIAL_MISMATCH', 'UNRESOLVED'];
  const SUPPORT = ['supported', 'possible', 'unsupported'];
  const REVIEW_STATUSES = ['unreviewed', 'in_progress', 'reviewed', 'completed'];
  const SNAPSHOT_FIELDS = ['reviewer_id', 'focal_pair', 'local_question', 'focus_source_ids', 'focus_quotes', 'participant_meanings_with_source_quotes', 'task_outputs', 'blocking_uncertainty', 'provisional_label', 'prefix_only_rationale', 'evidence_verified'];
  const CASES = DATA.cases;
  const byId = new Map(CASES.map(c => [c.case_id, c]));
  const copy = x => JSON.parse(JSON.stringify(x));
  const own = (o, k) => Object.prototype.hasOwnProperty.call(o, k);
  const isObject = x => x !== null && typeof x === 'object' && !Array.isArray(x);
  const blank = c => ({
    review_status: 'unreviewed', reviewer_id: '',
    review_metadata: {schema_version: '1.0', evidence_tier: 'S', observer_input_sha256: c.observer_input_sha256,
      prior_exposure: {assistant_draft: null, system_outputs: null, released_labels: null, later_evidence: null, notes: ''},
      prefix_first_review_completed: false, later_evidence_review_completed: false,
      assistant_wording_fields: [], human_content_confirmed: false},
    focal_pair: null, local_question: null, focus_source_ids: [], focus_quotes: [],
    participant_meanings_with_source_quotes: [], task_outputs: null, blocking_uncertainty: null,
    provisional_label: null, prefix_only_rationale: null, evidence_verified: null,
    include_in_pilot: null, inclusion_or_exclusion_reason: null
  });
  const state = {reviews: Object.fromEntries(CASES.map(c => [c.case_id, blank(c)])), current: 0,
    dirty: false, notice: 'Begin with the visible prefix. Import an existing review file to continue it.', noticeType: '',
    filename: '', pairDraft: {}, wording: null, wordingName: '', visibleWording: new Set(), issues: null};
  const current = () => CASES[state.current];
  const review = () => state.reviews[current().case_id];
  const players = c => c.observer_input.participants.filter(p => p.participant_id !== 'Audio' && p.known_role !== 'recorded_audio_not_player').map(p => p.participant_id);
  const sourceRows = c => c.observer_input.dialogue_prefix.map(t => ({source_id: t.utterance_id || t.source_id, speaker: t.speaker, text: t.text, kind: 'dialogue'}))
    .concat(c.observer_input.context_sources.map(t => ({source_id: t.source_id, speaker: null, text: t.text, kind: 'context'})));
  const rowFor = (c, id) => sourceRows(c).find(t => t.source_id === id);
  const prefixFor = (c, id) => c.observer_input.dialogue_prefix.find(t => (t.utterance_id || t.source_id) === id);
  function el(tag, attrs = {}, ...children) {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (k.startsWith('on') && typeof v === 'function') e.addEventListener(k.slice(2), v);
      else if (k === 'className') e.className = v;
      else if (k === 'value') e.value = v == null ? '' : v;
      else if (k === 'checked') e.checked = !!v;
      else if (k === 'disabled') e.disabled = !!v;
      else if (v !== null && v !== undefined) e.setAttribute(k, String(v));
    }
    const append = item => {
      if (Array.isArray(item)) item.forEach(append);
      else if (item !== null && item !== undefined) e.append(item instanceof Node ? item : document.createTextNode(String(item)));
    };
    children.forEach(append);
    return e;
  }
  const p = (text, cls = '') => el('p', {className: cls}, text);
  const button = (text, fn, cls = '', attrs = {}) => el('button', {type: 'button', className: cls, onclick: fn, ...attrs}, text);
  function field(title, control, hint) {
    return el('label', {className: 'field'}, el('span', {}, title), control, hint ? el('small', {className: 'hint'}, hint) : null);
  }
  function textarea(value, change, attrs = {}) {
    return el('textarea', {value: value == null ? '' : value, oninput: e => change(e.target.value), ...attrs});
  }
  function input(value, change, attrs = {}) {
    return el('input', {type: 'text', value: value == null ? '' : value, oninput: e => change(e.target.value), ...attrs});
  }
  function select(value, options, change, attrs = {}) {
    const s = el('select', {onchange: e => change(e.target.value), ...attrs});
    options.forEach(x => s.append(el('option', {value: x[0]}, x[1])));
    s.value = value == null ? '' : String(value);
    return s;
  }
  const tri = (value, change) => select(value === true ? 'yes' : value === false ? 'no' : '', [['', 'Pending / not checked'], ['yes', 'Yes'], ['no', 'No']], v => change(v === '' ? null : v === 'yes'));
  function details(title, body, opened = false) { const d = el('details', {}, el('summary', {}, title), el('div', {className: 'details-body'}, body)); d.open = opened; return d; }
  function stage(code, title, ...body) { return el('section', {className: 'stage'}, el('div', {className: 'stage-heading'}, el('span', {className: 'stage-pill'}, code), el('h3', {}, title)), ...body); }
  function markDirty(contentField) {
    state.dirty = true;
    state.issues = null;
    if (contentField) { review().review_metadata.human_content_confirmed = false; const confirmation = document.getElementById('human-content-confirmed'); if (confirmation) confirmation.checked = false; }
    const note = document.getElementById('save-note');
    if (note) note.textContent = 'Unsaved changes · Download REVIEWS.json before closing.';
  }
  function set(fieldName, value) { review()[fieldName] = value; markDirty(fieldName); }
  function message(text, kind = '') { state.notice = text; state.noticeType = kind; const node = document.getElementById('notice'); if (node) { node.textContent = text; node.className = 'notice ' + kind; } }
  function refresh() {
    const y = window.scrollY;
    const evidence = document.querySelector('.evidence-panel');
    const sy = evidence ? evidence.scrollTop : 0;
    render();
    const next = document.querySelector('.evidence-panel'); if (next) next.scrollTop = sy;
    window.scrollTo(0, y);
  }
  function switchCase(index) { state.current = Math.max(0, Math.min(CASES.length - 1, index)); state.issues = null; render(); window.scrollTo(0, 0); }
  function checkedQuote(c, q, prefixOnly = true) {
    const row = prefixOnly ? prefixFor(c, q.source_id) : rowFor(c, q.source_id);
    return !!row && typeof q.quote === 'string' && q.quote.length > 0 && row.text.includes(q.quote);
  }
  function hasUnknown(value) {
    if (value === null || (typeof value === 'string' && value.toUpperCase() === 'UNKNOWN')) return true;
    if (Array.isArray(value)) return value.some(hasUnknown);
    if (isObject(value)) return Object.values(value).some(hasUnknown);
    return false;
  }
  function consequenceRule(a, b, blocked) {
    if (blocked || !a.length || !b.length || [...a, ...b].some(hasUnknown)) return 'UNRESOLVED';
    const aa = new Set(a.map(x => JSON.stringify(sortedValue(x))));
    const bb = new Set(b.map(x => JSON.stringify(sortedValue(x))));
    if (aa.size === 1 && bb.size === 1 && [...aa][0] === [...bb][0]) return 'ALIGNED';
    if (![...aa].some(x => bb.has(x))) return 'POTENTIAL_MISMATCH';
    return 'UNRESOLVED';
  }
  function validation(c, r) {
    const problems = [];
    const supportedPeople = new Set();
    if (!isObject(r.review_metadata)) return ['review_metadata must be an object.'];
    if (r.review_metadata.observer_input_sha256 !== c.observer_input_sha256) problems.push('Observer input hash does not match this frozen case.');
    for (const key of Object.keys(r)) if (!own(blank(c), key)) problems.push('Preserved legacy field requires migration or reconciliation: ' + key);
    if (r.review_metadata.evidence_tier !== 'S') problems.push('The evidence tier must remain S.');
    if (r.provisional_label !== null && !LABELS.includes(r.provisional_label)) problems.push('Use a controlled judgment code, or leave the judgment pending.');
    if (r.focal_pair !== null && (!Array.isArray(r.focal_pair) || r.focal_pair.some(x => !players(c).includes(x)) || new Set(r.focal_pair).size !== r.focal_pair.length || r.focal_pair.length !== 2)) problems.push('Choose two distinct actual participants; Audio is a public source, not a player.');
    for (const id of r.focus_source_ids || []) if (!prefixFor(c, id)) problems.push('Unknown focus source: ' + id);
    for (const q of r.focus_quotes || []) {
      if (!checkedQuote(c, q, true)) problems.push('Focus quote is missing or not an exact substring: ' + q.source_id);
      const row = prefixFor(c, q.source_id); if (row && q.speaker !== row.speaker) problems.push('Focus quote speaker differs from the source: ' + q.source_id);
      if (!(r.focus_source_ids || []).includes(q.source_id)) problems.push('Focus quote source is not in focus_source_ids: ' + q.source_id);
    }
    for (const id of r.focus_source_ids || []) if (!(r.focus_quotes || []).some(q => q.source_id === id)) problems.push('Focus source has no exact quote: ' + id);
    for (const [i, m] of (r.participant_meanings_with_source_quotes || []).entries()) {
      if (!players(c).includes(m.participant_id)) problems.push('Reading ' + (i + 1) + ' needs an actual participant.');
      if (m.support !== null && !SUPPORT.includes(m.support)) problems.push('Reading ' + (i + 1) + ' has an invalid support code.');
      if (m.support === 'supported') supportedPeople.add(m.participant_id);
      if (m.support === 'supported' && !(m.source_quotes || []).some(q => { const source = prefixFor(c, q.source_id); return source && source.speaker === m.participant_id && checkedQuote(c, q, true); })) problems.push('A supported reading requires an exact own-speaker prefix quotation: reading ' + (i + 1));
      for (const q of m.source_quotes || []) {
        if (!checkedQuote(c, q)) problems.push('Reading quote is missing or not exact: ' + q.source_id);
        const source = prefixFor(c, q.source_id);
        if (source && own(q, 'speaker') && q.speaker !== source.speaker) problems.push('Reading quote speaker differs from the source: ' + q.source_id);
      }
    }
    if (r.review_metadata.prefix_first_review_completed) {
      if (!r.reviewer_id || !r.reviewer_id.trim()) problems.push('A completed first pass needs a reviewer identifier.');
      if (!r.local_question || !r.local_question.trim()) problems.push('A completed first pass needs the local task question.');
      if (!Array.isArray(r.focal_pair) || r.focal_pair.length !== 2) problems.push('A completed first pass needs two focal participants.');
      if (!r.provisional_label) problems.push('A completed first pass needs an explicit judgment; pending is not UNRESOLVED.');
      if (!r.prefix_only_rationale || !r.prefix_only_rationale.trim()) problems.push('A completed first pass needs its prefix-only reason.');
    }
    if (r.provisional_label && r.provisional_label !== 'UNRESOLVED') {
      if (r.blocking_uncertainty !== false) problems.push('A definite judgment requires an explicit no-blocking-uncertainty decision.');
      if (!Array.isArray(r.focal_pair) || r.focal_pair.length !== 2 || !r.focal_pair.every(person => supportedPeople.has(person))) problems.push('A definite judgment needs a supported reading for each focal participant.');
    }
    if (isObject(r.task_outputs) && own(r.task_outputs, 'supported_consequences') && r.task_outputs.supported_consequences !== null) {
      const x = r.task_outputs.supported_consequences;
      if (!isObject(x)) problems.push('supported_consequences must be an object keyed by participant.');
      else {
        const pair = r.focal_pair;
        const validPair = Array.isArray(pair) && pair.length === 2 && new Set(pair).size === 2 && pair.every(person => players(c).includes(person));
        const matchingKeys = validPair && Object.keys(x).length === 2 && pair.every(person => own(x, person));
        const validArrays = Object.entries(x).every(([key, value]) => players(c).includes(key) && Array.isArray(value));
        if (!matchingKeys) problems.push('supported_consequences must name exactly the two focal participants.');
        if (!validArrays) problems.push('Each supported_consequences entry needs an actual participant and an array of typed outputs.');
        if (matchingKeys && validArrays) {
          for (const person of pair) if (x[person].length && !supportedPeople.has(person)) problems.push('Nonempty supported consequences need a supported reading for ' + person + '.');
          const expected = consequenceRule(x[pair[0]], x[pair[1]], r.blocking_uncertainty !== false);
          if (r.provisional_label !== null && r.provisional_label !== expected) {
            const unknown = [...x[pair[0]], ...x[pair[1]]].some(hasUnknown);
            problems.push('F7 requires ' + expected + ' for these typed consequences and uncertainty settings; the saved judgment is ' + r.provisional_label + '.' + (unknown ? ' A required consequence value is null or UNKNOWN.' : ''));
          }
        }
      }
    }
    return problems;
  }
  function sortedValue(value) {
    if (Array.isArray(value)) return value.map(sortedValue);
    if (isObject(value)) return Object.fromEntries(Object.keys(value).sort().map(key => [key, sortedValue(value[key])]));
    return value;
  }
  async function recordFirstPass(checked) {
    const c = current(); const r = review(); const meta = r.review_metadata;
    if (!checked) { meta.prefix_first_review_completed = false; markDirty(); refresh(); return; }
    try {
      if (!r.provisional_label || !r.reviewer_id || !r.local_question || !r.prefix_only_rationale || !Array.isArray(r.focal_pair) || r.focal_pair.length !== 2)
        throw new Error('Enter the reviewer, question, pair, judgment and reason before completing a first pass.');
      if (!own(meta, 'first_pass_judgment_snapshot') && !own(meta, 'first_pass_judgment_sha256')) {
        if (!globalThis.crypto || !globalThis.crypto.subtle) throw new Error('This browser cannot create the first-pass hash. Keep the draft and use the package review tools.');
        const snapshot = Object.fromEntries(SNAPSHOT_FIELDS.map(key => [key, copy(r[key])]));
        if (typeof meta.focus_selection_reason === 'string' && meta.focus_selection_reason.trim().length > 0) snapshot.focus_selection_reason = meta.focus_selection_reason;
        const encoded = new TextEncoder().encode(JSON.stringify(sortedValue(snapshot)));
        const digest = await globalThis.crypto.subtle.digest('SHA-256', encoded);
        meta.first_pass_judgment_snapshot = snapshot;
        meta.first_pass_judgment_sha256 = Array.from(new Uint8Array(digest), x => x.toString(16).padStart(2, '0')).join('');
        meta.first_pass_recorded_at_utc = new Date().toISOString();
      }
      meta.prefix_first_review_completed = true;
      state.dirty = true;
      message('First pass recorded for ' + c.case_id + '. Its initial judgment snapshot is retained and will not be overwritten.', 'success');
    } catch (error) { message('First pass remains pending: ' + error.message, 'error'); }
    refresh();
  }
  function importShape(c, r) {
    if (!isObject(r)) throw new Error(c.case_id + ': review must be an object.');
    const expected = Object.keys(blank(c));
    for (const k of expected) if (!own(r, k)) throw new Error(c.case_id + ': missing canonical field ' + k + '. Migrate older files with the package review tools first.');
    if (!isObject(r.review_metadata) || r.review_metadata.observer_input_sha256 !== c.observer_input_sha256) throw new Error(c.case_id + ': missing or mismatched observer-input hash. Use the matching frozen inputs.');
    if (r.review_metadata.evidence_tier !== 'S') throw new Error(c.case_id + ': evidence tier must be S.');
    if (!isObject(r.review_metadata.prior_exposure) || !Array.isArray(r.review_metadata.assistant_wording_fields)) throw new Error(c.case_id + ': incomplete canonical review metadata.');
    if (r.focal_pair !== null && !Array.isArray(r.focal_pair)) throw new Error(c.case_id + ': focal_pair must be null or an array of two participants.');
    if (!REVIEW_STATUSES.includes(r.review_status)) throw new Error(c.case_id + ': use a canonical review_status code.');
    for (const key of ['focus_source_ids', 'focus_quotes', 'participant_meanings_with_source_quotes']) if (!Array.isArray(r[key])) throw new Error(c.case_id + ': ' + key + ' must be an array.');
    if (r.provisional_label !== null && !LABELS.includes(r.provisional_label)) throw new Error(c.case_id + ': unknown judgment code.');
    for (const key of ['blocking_uncertainty', 'evidence_verified', 'include_in_pilot']) if (r[key] !== null && typeof r[key] !== 'boolean') throw new Error(c.case_id + ': ' + key + ' must be true, false or null.');
    if (r.task_outputs !== null && !isObject(r.task_outputs)) throw new Error(c.case_id + ': task_outputs must be an object or null; migrate a legacy string before importing.');
    for (const m of r.participant_meanings_with_source_quotes) if (!isObject(m) || !Array.isArray(m.source_quotes) || (m.support !== null && !SUPPORT.includes(m.support))) throw new Error(c.case_id + ': migrate participant reading records to the canonical format first.');
    for (const q of r.focus_quotes) if (!isObject(q)) throw new Error(c.case_id + ': malformed focus quote.');
    // Exact quote errors are retained as editable draft issues; identity and controlled-code failures reject import.
    return copy(r);
  }
  async function importReviews(file) {
    if (!file) return;
    try {
      const parsed = reviewKeys.toTechnicalReviews(JSON.parse(await file.text()));
      if (!isObject(parsed) || !Object.keys(parsed).length) throw new Error('Expected a case-ID map of canonical reviews.');
      const pending = {};
      for (const [id, r] of Object.entries(parsed)) { if (!byId.has(id)) throw new Error('Unknown case ID: ' + id); pending[id] = importShape(byId.get(id), r); }
      Object.assign(state.reviews, pending);
      state.filename = file.name; state.pairDraft = {}; state.dirty = true; state.visibleWording.clear(); state.issues = null;
      message('Imported ' + Object.keys(pending).length + ' case reviews. Unknown legacy fields were preserved. Check drafts before export.', 'success');
      refresh();
    } catch (error) { message('Review import stopped: ' + error.message, 'error'); }
  }
  async function importWording(file) {
    if (!file) return;
    try {
      const x = JSON.parse(await file.text());
      if (!isObject(x.cases) || x.evidence_tier !== 'S') throw new Error('Choose Tier_S_Wording_Alternatives.json, with a Tier S cases map.');
      for (const [id, c] of Object.entries(x.cases)) if (!byId.has(id) || !isObject(c)) throw new Error('Unknown or malformed wording case: ' + id);
      state.wording = x; state.wordingName = file.name; state.visibleWording.clear();
      message('Wording file loaded. Suggestions remain hidden until you open them for a case.', 'success'); refresh();
    } catch (error) { message('Wording import stopped: ' + error.message, 'error'); }
  }
  function exportReviews() {
    let content;
    try { content = JSON.stringify(reviewKeys.toReferenceReviews(state.reviews), null, 2) + '\n'; }
    catch (error) { message('Review export stopped: ' + error.message + ' Your current draft remains in this page.', 'error'); return; }
    const url = URL.createObjectURL(new Blob([content], {type: 'application/json'}));
    const a = document.createElement('a'); a.href = url; a.download = 'REVIEWS.json'; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    state.dirty = false;
    message('Download requested. Keep the downloaded REVIEWS.json to continue later; this page does not save automatically.', 'success'); refresh();
  }
  function fileButton(title, accept, callback) {
    const f = el('input', {type: 'file', accept, onchange: e => { callback(e.target.files[0]); e.target.value = ''; }});
    return el('label', {className: 'filebutton', tabindex: '0', role: 'button', onkeydown: e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); f.click(); } }}, title, f);
  }
  function exposure(action, fields = []) {
    const meta = review().review_metadata;
    const before = !meta.prefix_first_review_completed;
    if (before) meta.prior_exposure.assistant_draft = true;
    if (!Array.isArray(meta.wording_exposure_events)) meta.wording_exposure_events = [];
    meta.wording_exposure_events.push({at_utc: new Date().toISOString(), source_filename: state.wordingName,
      action, before_prefix_first_review: before, fields: fields.slice()});
    markDirty();
  }
  function useWording(fieldName, apply) {
    apply();
    const meta = review().review_metadata;
    if (!meta.assistant_wording_fields.includes(fieldName)) meta.assistant_wording_fields.push(fieldName);
    meta.human_content_confirmed = false;
    exposure('copy_prose', [fieldName]);
    message('Wording copied. Quotations, support codes, judgment, verification, selection and completion decisions were not set.', 'success'); refresh();
  }
  function ensureTask() {
    const r = review();
    if (typeof r.task_outputs === 'string') r.task_outputs = {scope: '', participant_outputs: {}, comparison: r.task_outputs, blocking_reasons: []};
    else if (!isObject(r.task_outputs)) r.task_outputs = {scope: '', participant_outputs: {}, comparison: '', blocking_reasons: []};
    if (!isObject(r.task_outputs.participant_outputs)) r.task_outputs.participant_outputs = {};
    return r.task_outputs;
  }
  function focusToggle(row) {
    const r = review(); const id = row.utterance_id || row.source_id;
    if (r.focus_source_ids.includes(id)) { r.focus_source_ids = r.focus_source_ids.filter(x => x !== id); r.focus_quotes = r.focus_quotes.filter(x => x.source_id !== id); }
    else { r.focus_source_ids.push(id); r.focus_quotes.push({source_id: id, speaker: row.speaker, quote: row.text}); }
    markDirty('focus_quotes'); refresh();
  }
  function evidencePanel(c) {
    const o = c.observer_input;
    const context = o.context_sources.map(s => el('section', {className: 'context-source'},
      el('h3', {className: 'mono'}, s.source_id),
      p('Accessible to: ' + (s.accessible_to_participants || []).join(', '), 'hint'),
      p('Context inventory status: ' + ((s.adapter || {}).review_status || 'not stated'), 'hint'),
      el('pre', {}, s.text),
      s.adapter ? details('Structured task facts', el('pre', {}, JSON.stringify(s.adapter, null, 2))) : null));
    return el('section', {className: 'panel evidence-panel', 'aria-label': 'Observer evidence'},
      el('div', {className: 'panel-head'}, el('div', {className: 'eyebrow'}, 'Frozen observer input'), el('h2', {}, 'Read the available evidence'),
        p('Full prefix and permitted context. No later turns, selected focus, reference labels or wording are embedded.', 'hint')),
      el('div', {className: 'panel-body'}, p(o.overall_task),
        details('Participants and accessible context', [p(o.participants.map(x => x.participant_id + (x.known_role ? ' · ' + x.known_role : '')).join('; '), 'hint'), ...context]),
        el('div', {className: 'rulebox'}, p('Tier S: map presence and a bare “okay” do not establish an adopted referent. Look for each participant’s expressed reading and its grounding.')),
        el('h3', {}, 'Dialogue prefix · ' + o.dialogue_prefix.length + ' turns'),
        el('div', {className: 'transcript-wrap'}, el('ol', {className: 'transcript'}, o.dialogue_prefix.map(t => {
          const id = t.utterance_id || t.source_id; const selected = review().focus_source_ids.includes(id);
          return el('li', {className: 'turn' + (selected ? ' focused' : ''), id: 'turn-' + id},
            el('div', {className: 'turn-meta'}, el('span', {}, el('span', {className: 'speaker'}, t.speaker), ' · ', el('code', {}, id)),
              button(selected ? 'Remove focus' : 'Use as focus', () => focusToggle(t), 'small', {'aria-pressed': String(selected)})),
            p(t.text, 'turn-text'));
        }))), details('Input identity', p(c.observer_input_sha256, 'saved-hash'))));
  }
  function metadataSection() {
    const r = review(); const m = r.review_metadata; const prior = m.prior_exposure;
    const check = (text, key) => el('label', {className: 'checkline'}, el('input', {type: 'checkbox', checked: m[key], onchange: async e => { if (key === 'prefix_first_review_completed') await recordFirstPass(e.target.checked); else { m[key] = e.target.checked; markDirty(); refresh(); } }}), text);
    return stage('Record', 'Reviewer and exposure',
      el('div', {className: 'row'}, field('Reviewer', input(r.reviewer_id, v => { r.reviewer_id = v; markDirty(); })),
        field('Review status', select(r.review_status, REVIEW_STATUSES.map(x => [x, x.replaceAll('_', ' ')]), v => { r.review_status = v; markDirty(); }), 'Choose this explicitly; it is never upgraded automatically.')),
      details('What had you seen before your first judgment?', [
        p('Record what actually preceded the first prefix judgment. Later wording consultation is recorded separately and does not rewrite this history.', 'hint'),
        el('div', {className: 'row'}, field('Assistant drafts', tri(prior.assistant_draft, v => { prior.assistant_draft = v; markDirty(); })), field('System predictions', tri(prior.system_outputs, v => { prior.system_outputs = v; markDirty(); }))),
        el('div', {className: 'row'}, field('Released / other labels', tri(prior.released_labels, v => { prior.released_labels = v; markDirty(); })), field('Later dialogue or outcomes', tri(prior.later_evidence, v => { prior.later_evidence = v; markDirty(); }))),
        field('Exposure notes', textarea(prior.notes, v => { prior.notes = v; markDirty(); })),
        check('First prefix review completed', 'prefix_first_review_completed'),
        check('Separate later-evidence review completed', 'later_evidence_review_completed'),
        Array.isArray(m.wording_exposure_events) && m.wording_exposure_events.length ? p(m.wording_exposure_events.length + ' wording consultation event(s) recorded for this case.', 'assist-note') : null
      ]),
      p('No fields are filled from a presumed case interpretation. Prior exposure is part of review provenance.', 'hint'));
  }
  function focusSection(c) {
    const r = review(); const opts = [['', 'Choose participant'], ...players(c).map(x => [x, x])];
    const displayedPair = state.pairDraft[c.case_id] || r.focal_pair || [];
    const pairChange = (index, value) => { const pair = displayedPair.slice(); pair[index] = value; state.pairDraft[c.case_id] = pair; r.focal_pair = pair.length === 2 && pair.every(Boolean) && pair[0] !== pair[1] ? pair.slice() : null; markDirty('focal_pair'); refresh(); };
    const quotes = r.focus_quotes.map((q, i) => {
      const valid = checkedQuote(c, q, true);
      const hint = p(valid ? 'Exact substring in the frozen prefix.' : 'Check the source and exact wording.', 'quote-check' + (valid ? '' : ' invalid'));
      return el('div', {className: 'quote-card'}, el('div', {className: 'card-heading'}, el('code', {}, q.source_id + ' · ' + q.speaker),
        button('Remove', () => { r.focus_quotes.splice(i, 1); r.focus_source_ids = r.focus_source_ids.filter(x => x !== q.source_id); markDirty('focus_quotes'); refresh(); }, 'small')),
        field('Exact expression', textarea(q.quote, v => { q.quote = v; markDirty('focus_quotes'); const ok = checkedQuote(c, q, true); hint.textContent = ok ? 'Exact substring in the frozen prefix.' : 'Check the source and exact wording.'; hint.className = 'quote-check' + (ok ? '' : ' invalid'); })), hint);
    });
    return stage('F1–F2', 'Question, participants and expression',
      field('Local task question', textarea(r.local_question, v => set('local_question', v)), 'What concrete choice are the participants trying to settle here?'),
      el('div', {className: 'row'}, field('First participant', select(displayedPair[0], opts, v => pairChange(0, v))), field('Second participant', select(displayedPair[1], opts, v => pairChange(1, v)))),
      p('Use “Use as focus” beside a transcript turn, then shorten the quote to the exact expression if needed. Selecting a turn creates only your review annotation.', 'hint'),
      quotes.length ? quotes : el('div', {className: 'empty'}, 'No focus selected. Read the prefix before choosing the expression.'));
  }
  function quoteEditor(c, reading, q, index) {
    const sources = sourceRows(c).filter(source => source.kind === 'dialogue');
    const opts = [['', 'Choose a source'], ...sources.map(s => [s.source_id, s.source_id + ' · ' + (s.speaker || 'context')])];
    const check = p(checkedQuote(c, q) ? 'Exact source substring.' : 'Choose a source and quote it exactly.', 'quote-check' + (checkedQuote(c, q) ? '' : ' invalid'));
    return el('div', {className: 'quote-card'},
      el('div', {className: 'row'}, field('Evidence source', select(q.source_id, opts, value => { q.source_id = value; const source = prefixFor(c, value); q.quote = source ? source.text : ''; if (source) q.speaker = source.speaker; else delete q.speaker; markDirty('participant_meanings_with_source_quotes'); refresh(); })),
        el('div', {}, button('Remove quote', () => { reading.source_quotes.splice(index, 1); markDirty('participant_meanings_with_source_quotes'); refresh(); }, 'small'))),
      field('Exact evidence', textarea(q.quote, value => { q.quote = value; markDirty('participant_meanings_with_source_quotes'); const ok = checkedQuote(c, q); check.textContent = ok ? 'Exact source substring.' : 'Choose a source and quote it exactly.'; check.className = 'quote-check' + (ok ? '' : ' invalid'); })), check);
  }
  function readingsSection(c) {
    const r = review();
    const cards = r.participant_meanings_with_source_quotes.map((m, i) => el('div', {className: 'reading-card'},
      el('div', {className: 'card-heading'}, el('h3', {}, 'Reading ' + (i + 1)), button('Remove reading', () => { r.participant_meanings_with_source_quotes.splice(i, 1); markDirty('participant_meanings_with_source_quotes'); refresh(); }, 'small danger')),
      el('div', {className: 'row'}, field('Participant', select(m.participant_id, [['', 'Choose participant'], ...players(c).map(x => [x, x])], v => { m.participant_id = v; markDirty('participant_meanings_with_source_quotes'); })),
        field('Evidence support', select(m.support, [['', 'Pending'], ['supported', 'Supported'], ['possible', 'Possible'], ['unsupported', 'Unsupported']], v => { m.support = v || null; markDirty('participant_meanings_with_source_quotes'); }))),
      field('Interpretation', textarea(m.meaning, v => { m.meaning = v; markDirty('participant_meanings_with_source_quotes'); }), 'Describe what this participant’s language supports; separate merely possible readings.'),
      (m.source_quotes || []).map((q, j) => quoteEditor(c, m, q, j)),
      button('Add evidence quote', () => { m.source_quotes.push({source_id: '', quote: ''}); markDirty('participant_meanings_with_source_quotes'); refresh(); }, 'small')));
    return stage('F3–F5', 'Each participant’s reading',
      p('Support is an evidence judgment. A supported reading needs an exact quotation from that participant in the prefix. Context facts remain visible but are not selectable as adoption evidence; explain their task role under consequences. An acknowledgment alone does not supply adoption.', 'hint'),
      cards.length ? cards : el('div', {className: 'empty'}, 'No interpretation entered.'),
      button('Add a reading', () => { r.participant_meanings_with_source_quotes.push({participant_id: '', meaning: '', source_quotes: [], support: null}); markDirty('participant_meanings_with_source_quotes'); refresh(); }, 'small'));
  }
  function tasksSection(c) {
    const r = review(); const t = isObject(r.task_outputs) ? r.task_outputs : {};
    const outputKeys = [...new Set([...(r.focal_pair || []), ...Object.keys(isObject(t.participant_outputs) ? t.participant_outputs : {})])];
    const consequenceText = own(t, 'supported_consequences') ? JSON.stringify(t.supported_consequences, null, 2) : '';
    const jsonStatus = p('Optional typed records for deterministic validation. Prose never becomes a typed consequence automatically.', 'hint');
    const typedEditor = textarea(consequenceText, () => {}, {className: 'advanced', spellcheck: 'false', 'aria-label': 'Supported consequences JSON'});
    const applyTyped = () => {
      try {
        const raw = typedEditor.value.trim();
        if (!raw) { if (isObject(r.task_outputs)) delete r.task_outputs.supported_consequences; }
        else {
          const parsed = JSON.parse(raw);
          if (!isObject(parsed)) throw new Error('Use an object keyed by participant, each with an array of canonical consequences.');
          for (const [key, value] of Object.entries(parsed)) if (!players(c).includes(key) || !Array.isArray(value)) throw new Error('Every key must be an actual participant, and every value an array.');
          ensureTask().supported_consequences = parsed;
        }
        markDirty('task_outputs'); jsonStatus.textContent = 'Typed consequence records saved to this review. No judgment was assigned.'; jsonStatus.className = 'hint';
      } catch (e) { jsonStatus.textContent = 'Not applied: ' + e.message; jsonStatus.className = 'quote-check invalid'; }
    };
    return stage('F6', 'Task consequences',
      field('Same task / event scope', textarea(t.scope || '', v => { ensureTask().scope = v; markDirty('task_outputs'); }), 'Fix the question, event, phase, premise and consequence representation before comparing.'),
      outputKeys.map(id => field(id + ' · consequence', textarea((t.participant_outputs || {})[id] || '', v => { ensureTask().participant_outputs[id] = v; markDirty('task_outputs'); }))),
      !outputKeys.length ? p('Choose the two participants above to enter their consequences.', 'hint') : null,
      field('Comparison in words', textarea(typeof r.task_outputs === 'string' ? r.task_outputs : (t.comparison || ''), v => { ensureTask().comparison = v; markDirty('task_outputs'); })),
      field('What is still unknown? One reason per line', textarea(Array.isArray(t.blocking_reasons) ? t.blocking_reasons.join('\n') : '', v => { ensureTask().blocking_reasons = v.split('\n').filter(x => x.trim()); markDirty('task_outputs'); })),
      details('Optional typed consequences', [p('Only record outputs actually supported under the declared task function. Unknown output values and missing support must remain visible.', 'hint'), typedEditor, button('Apply typed JSON', applyTyped, 'small'), jsonStatus]));
  }
  function decisionSection() {
    const r = review();
    return stage('F7', 'Judgment and reason',
      el('div', {className: 'rulebox'},
        p('ALIGNED · Same single known consequence, with no blocking uncertainty.'),
        p('POTENTIAL_MISMATCH · Nonempty known consequence sets with no common outcome, and no blocking uncertainty.'),
        p('UNRESOLVED · Missing support or facts, consequential alternatives, or overlapping sets prevent either conclusion.')),
      field('Could uncertainty change the conclusion?', tri(r.blocking_uncertainty, v => { set('blocking_uncertainty', v); }), 'A possible reading demonstrably yielding the same known consequence need not block.'),
      field('Review judgment', select(r.provisional_label, [['', 'Pending · no judgment yet'], ...LABELS.map(x => [x, x])], v => { set('provisional_label', v || null); refresh(); })),
      field('Why this judgment? Prefix evidence only', textarea(r.prefix_only_rationale, v => set('prefix_only_rationale', v))),
      p('Pending is not UNRESOLVED. Processing failures are not human reference labels. This page does not assign a judgment.', 'hint'));
  }
  function completionSection() {
    const r = review(); const m = r.review_metadata;
    return stage('Review', 'Evidence and selection decisions',
      el('div', {className: 'row'}, field('Evidence checked?', tri(r.evidence_verified, v => set('evidence_verified', v))), field('Include in pilot?', tri(r.include_in_pilot, v => set('include_in_pilot', v)))),
      p('These are your explicit review decisions. Context-release checks, adjudication and final selection records remain separate steps.', 'hint'),
      field('Selection / exclusion reason', textarea(r.inclusion_or_exclusion_reason, v => set('inclusion_or_exclusion_reason', v))),
      el('label', {className: 'checkline'}, el('input', {id: 'human-content-confirmed', type: 'checkbox', checked: m.human_content_confirmed, onchange: e => { m.human_content_confirmed = e.target.checked; markDirty(); }}), 'I checked the content now entered against the available evidence.'),
      button('Check this draft', () => { state.issues = validation(current(), review()); refresh(); }, 'small'),
      state.issues ? (state.issues.length ? el('div', {}, p('Draft checks to resolve:', 'quote-check invalid'), el('ul', {className: 'validation-list'}, state.issues.map(x => el('li', {}, x)))) : p('Local identity, code, quotation and available typed F7 checks passed. Without typed consequences, F7 cannot be checked from prose. Semantic support, map facts and research eligibility still require human review.', 'hint')) : null);
  }
  function optionCards(title, values, fieldName, apply) {
    if (!Array.isArray(values) || !values.length) return null;
    return el('section', {}, el('h3', {}, title), values.slice(0, 2).map((text, index) => el('div', {className: 'wording-choice'},
      p('Version ' + (index ? 'B' : 'A'), 'option-label'), p(text), button('Use this wording', () => useWording(fieldName, () => apply(text)), 'small'))));
  }
  function wordingSection(c) {
    const wc = state.wording && state.wording.cases[c.case_id];
    const head = el('div', {className: 'panel-head'}, el('h2', {}, 'Optional wording reference'),
      p('Case-specific suggestions are assistant drafts. Opening them records exposure; copying changes prose only.', 'wording-warning'));
    if (!state.wording) return el('section', {className: 'panel wording-panel'}, head, el('div', {className: 'wording-content'},
      p('For an independent first pass, complete your prefix judgment before consulting wording. No suggestions are bundled into this page.', 'hint'),
      fileButton('Import Tier S wording', '.json,application/json', importWording)));
    if (!wc) return el('section', {className: 'panel wording-panel'}, head, p('No suggestions are present for this case.', 'wording-content'));
    if (!state.visibleWording.has(c.case_id)) return el('section', {className: 'panel wording-panel'}, head, el('div', {className: 'wording-content'},
      p('Loaded: ' + state.wordingName + '. Content is still hidden.', 'hint'),
      button('Open suggestions for this case', () => { exposure('view_suggestions'); state.visibleWording.add(c.case_id); refresh(); }, 'small')));
    const content = [];
    content.push(optionCards('Local task question', wc.question_options, 'local_question', text => { review().local_question = text; }));
    for (const person of wc.participants || []) {
      content.push(optionCards(person.participant_id + ' · interpretation', person.meaning_options, 'participant_meanings_with_source_quotes', text => {
        let m = review().participant_meanings_with_source_quotes.find(x => x.participant_id === person.participant_id);
        if (!m) { m = {participant_id: person.participant_id, meaning: '', source_quotes: [], support: null}; review().participant_meanings_with_source_quotes.push(m); }
        m.meaning = text;
      }));
      content.push(optionCards(person.participant_id + ' · consequence', person.task_output_options, 'task_outputs', text => { ensureTask().participant_outputs[person.participant_id] = text; }));
      if (Array.isArray(person.source_quotes) && person.source_quotes.length) content.push(details(person.participant_id + ' · suggested source references (not copied)', person.source_quotes.map(q => p(q.source_id + ' · “' + q.quote + '”', 'hint'))));
    }
    content.push(optionCards('Consequence comparison', wc.task_output_options, 'task_outputs', text => { ensureTask().comparison = text; }));
    content.push(optionCards('Selection reason wording', wc.reason_options, 'inclusion_or_exclusion_reason', text => { review().inclusion_or_exclusion_reason = text; }));
    if (Array.isArray(wc.blocking_reasons)) content.push(details('Uncertainty questions to check', el('ul', {className: 'validation-list'}, wc.blocking_reasons.map(x => el('li', {}, x)))));
    if (Array.isArray(wc.label_guidance)) content.push(details('Conditional label guidance · no label is assigned', wc.label_guidance.map(x => p(x.code + ': ' + x.use_when, 'hint'))));
    if (Array.isArray(wc.cautions)) content.push(details('Evidence cautions', el('ul', {className: 'validation-list'}, wc.cautions.map(x => el('li', {}, x)))));
    return el('section', {className: 'panel wording-panel'}, head, el('div', {className: 'wording-content'},
      p('Choose A or B separately for each field. The first existing reading for the named participant is the destination; quotations and support remain yours to review.', 'wording-warning'),
      button('Hide suggestions', () => { state.visibleWording.delete(c.case_id); refresh(); }, 'small'), content));
  }
  function render() {
    const c = current(); const r = review(); const o = c.observer_input;
    const completed = CASES.filter(x => state.reviews[x.case_id].review_metadata.prefix_first_review_completed).length;
    const app = document.getElementById('app'); app.replaceChildren();
    app.append(el('header', {className: 'masthead'}, el('div', {}, el('div', {className: 'eyebrow'}, 'CIM / Tier S'),
      el('h1', {}, 'Consequential Interpretation Mismatch'), p('Read the same frozen prefix, record each participant’s supported interpretation, and compare task consequences.', 'subhead')),
      el('div', {className: 'toolbar'}, fileButton('Import REVIEWS.json', '.json,application/json', importReviews), button('Download REVIEWS.json', exportReviews, 'primary'),
        el('span', {id: 'save-note', className: 'save-note'}, state.dirty ? 'Unsaved changes · Download before closing.' : 'Local, in-memory editing · No automatic saving'))));
    app.append(el('div', {className: 'statusline'}, el('span', {id: 'notice', className: 'notice ' + state.noticeType}, state.notice),
      el('span', {className: 'badge'}, completed + ' / ' + CASES.length + ' first passes recorded')));
    const nav = el('nav', {className: 'case-nav', 'aria-label': 'Candidate episodes'}, CASES.map((x, index) => {
      const label = x.case_id.split('_')[0]; const rr = state.reviews[x.case_id];
      return button('', () => switchCase(index), 'case-button', {'aria-current': String(index === state.current), 'aria-label': 'Review ' + x.case_id});
    }));
    [...nav.children].forEach((btn, index) => { const x = CASES[index]; const rr = state.reviews[x.case_id]; btn.append(el('span', {}, x.case_id.split('_')[0]), el('span', {className: 'dot'}, rr.review_metadata.prefix_first_review_completed ? '✓' : rr.provisional_label ? 'draft' : '—')); });
    const sidebar = el('aside', {className: 'sidebar'}, el('h2', {}, CASES.length + ' candidates'), nav, p('Candidates are not confirmed selections. Keep each reader’s file separate.', 'footer-note'));
    const titlebar = el('div', {className: 'casebar'}, el('div', {}, el('h2', {}, c.case_id.split('_')[0]),
      el('div', {className: 'case-detail'}, c.case_id + ' · ' + o.dialogue_prefix.length + ' prefix turns')),
      el('div', {className: 'case-actions'}, button('← Previous', () => switchCase(state.current - 1), 'small', {disabled: state.current === 0}), button('Next →', () => switchCase(state.current + 1), 'small', {disabled: state.current === CASES.length - 1})));
    const form = el('section', {className: 'panel', 'aria-label': 'Human review fields'},
      el('div', {className: 'panel-head'}, el('div', {className: 'eyebrow'}, 'Your research annotation'), el('h2', {}, 'Make the evidence explicit'),
        p('Downloaded JSON uses the reference-key format. Controlled codes stay unchanged.', 'hint')),
      metadataSection(), focusSection(c), readingsSection(c), tasksSection(c), decisionSection(), completionSection());
    const workspace = el('main', {className: 'workspace'}, titlebar, el('div', {className: 'columns'}, evidencePanel(c), el('div', {}, form, wordingSection(c))),
      p('JSON import preserves unknown fields. This editor makes no network requests and stores no browser copy. Download your review before leaving; use the package validator for the complete schema and eligibility checks.', 'footer-note'));
    app.append(el('div', {className: 'layout'}, sidebar, workspace));
  }
  window.addEventListener('beforeunload', e => { if (state.dirty) { e.preventDefault(); e.returnValue = ''; } });
  render();
})();
