/* Behavioral integration test using a minimal DOM stub, not a browser.
   Run: node tests/test_review_ui.js [--output-directory PATH]
   No browser launch, network, npm dependencies or visual rendering are used. */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const {webcrypto, createHash} = require('node:crypto');
const root = path.resolve(__dirname, '..');
const {createCodec} = require(path.join(root, 'web/review_keys.js'));
const keySpec = JSON.parse(fs.readFileSync(path.join(root, 'schemas/review_key_map.json'), 'utf8'));
const codec = createCodec(keySpec);
const args = process.argv.slice(2);
const outputIndex = args.indexOf('--output-directory');
const outputDirectory = outputIndex >= 0 ? path.resolve(args[outputIndex + 1]) : null;
const records = [];
let lastBlob = null;
const blobs = new Map();
let blobNumber = 0;

class DomNode {
  constructor(tag = '', text = '') { this.tagName = tag.toUpperCase(); this._text = text; this.children = []; this.attrs = {}; this.listeners = {}; this.value = ''; this.checked = false; this.disabled = false; this.scrollTop = 0; this.files = []; }
  get textContent() { return this._text + this.children.map(x => x.textContent).join(''); }
  set textContent(x) { this._text = String(x); this.children = []; }
  get className() { return this.attrs.class || ''; }
  set className(x) { this.attrs.class = x; }
  get id() { return this.attrs.id; }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  getAttribute(k) { return this.attrs[k]; }
  append(...items) { for (const x of items) this.children.push(x instanceof DomNode ? x : new DomNode('', String(x))); }
  replaceChildren(...items) { this._text = ''; this.children = []; this.append(...items); }
  addEventListener(name, fn) { (this.listeners[name] ||= []).push(fn); }
  async fire(name, extra = {}) { const e = {target: this, preventDefault() {}, ...extra}; for (const f of this.listeners[name] || []) await f(e); await new Promise(resolve => setImmediate(resolve)); }
  async click() { if (this.tagName === 'A') lastBlob = blobs.get(this.href); else await this.fire('click'); }
}
const app = new DomNode('div'); app.attrs.id = 'app';
const data = new DomNode('script'); data.attrs.id = 'observer-data';
const mappingData = new DomNode('script'); mappingData.attrs.id = 'review-key-map-data';
mappingData.textContent = JSON.stringify(keySpec);
const cases = fs.readdirSync(path.join(root, 'prospective/observer_inputs')).filter(x => x.endsWith('.json')).sort().map(filename => {
  const raw = fs.readFileSync(path.join(root, 'prospective/observer_inputs', filename));
  return {case_id: filename.slice(0, -5), observer_input_sha256: createHash('sha256').update(raw).digest('hex'), observer_input: JSON.parse(raw)};
});
data.textContent = JSON.stringify({schema_version: '1.0', evidence_tier: 'S', cases});
const walk = node => [node, ...node.children.flatMap(walk)];
const find = predicate => walk(app).find(predicate);
const document = {
  createElement: tag => new DomNode(tag), createTextNode: text => new DomNode('', text),
  getElementById: id => id === 'observer-data' ? data : id === 'review-key-map-data' ? mappingData : id === 'app' ? app : find(n => n.attrs.id === id),
  querySelector: selector => selector.startsWith('.') ? find(n => n.className.split(' ').includes(selector.slice(1))) : null
};
const browserWindow = {scrollY: 0, scrollTo(_x, y) { this.scrollY = y; }, addEventListener() {}};
const context = {document, window: browserWindow, Node: DomNode, TextEncoder, crypto: webcrypto, Blob,
  URL: {createObjectURL(blob) { const id = 'blob:' + (++blobNumber); blobs.set(id, blob); return id; }, revokeObjectURL(id) { blobs.delete(id); }},
  setTimeout, clearTimeout, console};
vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(root, 'web/review_keys.js'), 'utf8'), context, {filename: 'review_keys.js'});
vm.runInContext(fs.readFileSync(path.join(root, 'web/review_app.js'), 'utf8'), context, {filename: 'review_app.js'});
const button = text => { const b = find(n => n.tagName === 'BUTTON' && n.textContent === text); assert.ok(b, 'Button exists: ' + text); return b; };
const label = title => { const l = find(n => n.tagName === 'LABEL' && n.children[0] && n.children[0].textContent === title); assert.ok(l, 'Field exists: ' + title); return l; };
const control = title => { const l = label(title); const c = walk(l).find(n => ['INPUT', 'SELECT', 'TEXTAREA'].includes(n.tagName)); assert.ok(c, title + ' has control'); return c; };
async function fill(title, value) { const c = control(title); c.value = value; await c.fire(c.tagName === 'SELECT' ? 'change' : 'input'); }
async function checkbox(title, value) { const l = find(n => n.tagName === 'LABEL' && n.className === 'checkline' && n.textContent === title); assert.ok(l, 'Checkbox exists: ' + title); const c = l.children.find(n => n.tagName === 'INPUT'); c.checked = value; await c.fire('change'); }
async function fileImport(title, name, object) { const l = find(n => n.tagName === 'LABEL' && n.textContent === title); assert.ok(l, title); const f = l.children.find(n => n.tagName === 'INPUT'); f.files = [{name, async text() { return JSON.stringify(object); }}]; await f.fire('change'); await new Promise(resolve => setImmediate(resolve)); }
async function exportedReference() { await button('Download REVIEWS.json').click(); assert.ok(lastBlob, 'Download Blob exists'); return JSON.parse(await lastBlob.text()); }
async function exportedHuman() { return codec.toHumanReviews(await exportedReference()); }
async function exported() { return codec.toTechnicalReviews(await exportedReference()); }
function record(name) { records.push({name, status: 'passed'}); }
function sorted(value) { return Array.isArray(value) ? value.map(sorted) : value && typeof value === 'object' ? Object.fromEntries(Object.keys(value).sort().map(key => [key, sorted(value[key])])) : value; }
const read = relative => JSON.parse(fs.readFileSync(path.join(root, relative), 'utf8'));
const fieldInventory = () => walk(app).filter(n => n.tagName === 'LABEL' && ['field', 'checkline'].includes(n.className)).map(n => {
  const element = walk(n).find(child => ['INPUT', 'SELECT', 'TEXTAREA'].includes(child.tagName));
  return [n.className === 'field' ? n.children[0].textContent : n.textContent, element.tagName, element.attrs.type || ''];
});
const originalBlankInventory = [
  ['Reviewer', 'INPUT', 'text'], ['Review status', 'SELECT', ''],
  ['Assistant drafts', 'SELECT', ''], ['System predictions', 'SELECT', ''],
  ['Released / other labels', 'SELECT', ''], ['Later dialogue or outcomes', 'SELECT', ''],
  ['Exposure notes', 'TEXTAREA', ''], ['First prefix review completed', 'INPUT', 'checkbox'],
  ['Separate later-evidence review completed', 'INPUT', 'checkbox'], ['Local task question', 'TEXTAREA', ''],
  ['First participant', 'SELECT', ''], ['Second participant', 'SELECT', ''],
  ['Same task / event scope', 'TEXTAREA', ''], ['Comparison in words', 'TEXTAREA', ''],
  ['What is still unknown? One reason per line', 'TEXTAREA', ''],
  ['Could uncertainty change the conclusion?', 'SELECT', ''], ['Review judgment', 'SELECT', ''],
  ['Why this judgment? Prefix evidence only', 'TEXTAREA', ''],
  ['Evidence checked?', 'SELECT', ''], ['Include in pilot?', 'SELECT', ''],
  ['Selection / exclusion reason', 'TEXTAREA', ''],
  ['I checked the content now entered against the available evidence.', 'INPUT', 'checkbox']
];
function assertNoAddedFields() {
  assert.ok(!fieldInventory().some(([caption]) => ['Evidence note', 'Support note', 'Focus source', 'Focus speaker', 'Source speaker'].includes(caption)));
  assert.ok(!find(n => n.tagName === 'SUMMARY' && n.textContent === 'Form labels and JSON fields'));
  assert.ok(!find(n => n.attrs['aria-label'] === 'Form labels and JSON paths'));
}

(async () => {
  const blank = await exported();
  assert.equal(Object.keys(blank).length, 20);
  for (const c of cases) { assert.equal(blank[c.case_id].focal_pair, null); assert.equal(blank[c.case_id].provisional_label, null); assert.equal(blank[c.case_id].review_metadata.observer_input_sha256, c.observer_input_sha256); assert.deepEqual(Object.keys(c.observer_input).sort(), ['context_sources', 'dialogue_prefix', 'overall_task', 'participants']); }
  const blankHuman = await exportedHuman();
  const blankReference = await exportedReference();
  for (const c of cases) {
    assert.ok(Object.hasOwn(blankHuman[c.case_id], 'Review judgment'));
    assert.ok(!Object.hasOwn(blankHuman[c.case_id], 'provisional_label'));
    assert.deepEqual(blankReference[c.case_id].subtask_hypotheses, [{description: null}]);
    assert.deepEqual(blankReference[c.case_id].focus, {utterance_id: null, quote: null, why_selected: null, additional_quotes: [], selected_utterance_ids: []});
    assert.ok(Object.hasOwn(blankReference[c.case_id], 'participant_interpretations'));
    assert.ok(Object.hasOwn(blankReference[c.case_id], 'consequence_analysis'));
    assert.ok(Object.hasOwn(blankReference[c.case_id], 'rationale'));
    assert.ok(Object.hasOwn(blankReference[c.case_id], 'selection_reason'));
    assert.ok(!Object.hasOwn(blankReference[c.case_id], 'Local task question'));
  }
  assert.deepEqual(codec.toTechnicalReviews(blankHuman), blank);
  assert.deepEqual(codec.toTechnicalReviews(blankReference), blank);
  record('Default download uses reference keys and lossless empty focus objects for 20 neutral records with exact observer hashes');
  assert.deepEqual(fieldInventory(), originalBlankInventory);
  assert.ok(find(n => n.tagName === 'TEXTAREA' && n.attrs['aria-label'] === 'Supported consequences JSON'));
  assertNoAddedFields();
  record('Original blank-form captions, control types and order are unchanged; no added note or mapping fields');
  const r2 = codec.toTechnicalReviews(read('reviews/reader_2/REVIEWS.json'));
  const firstId = cases[0].case_id;
  r2[firstId].review_metadata.extra_provenance = {kept: ['unknown', 'metadata']};
  await fileImport('Import REVIEWS.json', 'reader2.json', r2);
  let result = await exported();
  assert.deepEqual(result, r2);
  record('Reader 2 imports and exports without losing null pairs or unknown metadata');
  const r1 = codec.toTechnicalReviews(read('REVIEWS.json'));
  await fileImport('Import REVIEWS.json', 'reader1.json', r1);
  result = await exported(); assert.deepEqual(result, r1);
  assert.equal(result.MT03_q1ec4_r019.provisional_label, r1.MT03_q1ec4_r019.provisional_label);
  assert.ok(!app.textContent.includes('Assistant wording used in:'));
  record('Reader 1 current judgments and all provenance survive import/export without a repetitive completion banner');
  const r1Human = await exportedHuman();
  await fileImport('Import REVIEWS.json', 'human-reader1.json', r1Human);
  result = await exported(); assert.deepEqual(result, r1);
  for (const [id, record] of Object.entries(r1)) {
    const human = r1Human[id];
    assert.deepEqual(human['Participants being compared'], record.focal_pair);
    assert.deepEqual(human['Each participant’s reading'].map(reading => reading['Support note']), record.participant_meanings_with_source_quotes.map(reading => reading.support_note));
    assert.equal(human['Reviewer and exposure']['Saved first judgment SHA-256'], record.review_metadata.first_pass_judgment_sha256);
  }
  assertNoAddedFields();
  record('Human-key review imports losslessly; existing JSON-only support notes, pair arrays and snapshot digests are preserved');
  const r1Reference = await exportedReference();
  await fileImport('Import REVIEWS.json', 'reference-reader1.json', r1Reference);
  assert.deepEqual(await exported(), r1);
  for (const [id, record] of Object.entries(r1)) {
    assert.deepEqual(r1Reference[id].subtask_hypotheses, [{description: record.local_question}]);
    assert.deepEqual(r1Reference[id].focus.selected_utterance_ids, record.focus_source_ids);
    assert.equal(r1Reference[id].focus.utterance_id, record.focus_quotes.length ? record.focus_quotes[0].source_id : null);
    assert.equal(r1Reference[id].focus.quote, record.focus_quotes.length ? record.focus_quotes[0].quote : null);
    assert.equal(r1Reference[id].focus.additional_quotes.length, Math.max(0, record.focus_quotes.length - 1));
  }
  const withWhy = structuredClone(r1Reference);
  withWhy[firstId].focus.why_selected = 'Fixture note: these selected turns make the local comparison explicit.';
  const expectedWithWhy = structuredClone(r1);
  expectedWithWhy[firstId].review_metadata.focus_selection_reason = withWhy[firstId].focus.why_selected;
  await fileImport('Import REVIEWS.json', 'reference-with-why.json', withWhy);
  assert.deepEqual(await exported(), expectedWithWhy);
  assert.equal((await exportedReference())[firstId].focus.why_selected, withWhy[firstId].focus.why_selected);
  assertNoAddedFields();
  assert.ok(!fieldInventory().some(([caption]) => caption === 'why_selected' || caption === 'Why selected'));
  record('Reference-key reviews import unchanged and JSON-only why_selected is retained without adding a form field');
  await fileImport('Import REVIEWS.json', 'reader1.json', r1);
  const mt10Id = Object.keys(r1).find(id => id.startsWith('MT10_'));
  assert.ok(mt10Id, 'Actual MT10 review exists');
  assert.equal(r1[mt10Id].blocking_uncertainty, false);
  assert.equal(r1[mt10Id].provisional_label, 'ALIGNED');
  assert.equal(r1[mt10Id].review_status, 'reviewed');
  const mt10KnownConsequence = ['Route', 'current_below_start_segment', 'below', 'm3_start'];
  for (const participant of r1[mt10Id].focal_pair) {
    assert.deepEqual(r1[mt10Id].task_outputs.supported_consequences[participant], [mt10KnownConsequence]);
  }
  assert.equal(r1Human[mt10Id]['Could uncertainty change the conclusion?'], false);
  assert.equal(r1Human[mt10Id]['Review judgment'], 'ALIGNED');
  await find(n => n.tagName === 'BUTTON' && n.attrs['aria-label'] === 'Review ' + mt10Id).click();
  await button('Check this draft').click();
  assert.ok(!app.textContent.includes('F7 requires'));
  assert.ok(!app.textContent.includes('A required consequence value is null or UNKNOWN.'));
  assert.ok(app.textContent.includes('Local identity, code, quotation and available typed F7 checks passed.'));
  result = await exported(); assert.deepEqual(result[mt10Id], r1[mt10Id]);
  record('Reviewed MT10 preserves ALIGNED, blocker=false and the checked m3_start anchor; local F7 checks pass without changing the review');
  await find(n => n.tagName === 'BUTTON' && n.attrs['aria-label'] === 'Review ' + firstId).click();
  await fileImport('Import REVIEWS.json', 'reader2.json', r2);
  await fill('First participant', 'giver');
  result = await exported(); assert.equal(result[firstId].focal_pair, null);
  await fill('Second participant', 'follower');
  result = await exported(); assert.deepEqual(result[firstId].focal_pair, ['giver', 'follower']);
  await button('Use as focus').click();
  result = await exported();
  assert.deepEqual(result[firstId].focus_source_ids, [cases[0].observer_input.dialogue_prefix[0].utterance_id]);
  assert.equal(result[firstId].focus_quotes[0].quote, cases[0].observer_input.dialogue_prefix[0].text);
  record('Pair stays null until complete; choosing a source copies the exact prefix quotation');
  await button('Add a reading').click();
  await fill('Participant', 'giver');
  await button('Add evidence quote').click();
  const richInventory = originalBlankInventory.slice();
  const taskIndex = richInventory.findIndex(([caption]) => caption === 'Same task / event scope');
  richInventory.splice(taskIndex, 0, ['Exact expression', 'TEXTAREA', ''], ['Participant', 'SELECT', ''], ['Evidence support', 'SELECT', ''], ['Interpretation', 'TEXTAREA', ''], ['Evidence source', 'SELECT', ''], ['Exact evidence', 'TEXTAREA', '']);
  const comparisonIndex = richInventory.findIndex(([caption]) => caption === 'Comparison in words');
  richInventory.splice(comparisonIndex, 0, ['giver · consequence', 'TEXTAREA', ''], ['follower · consequence', 'TEXTAREA', '']);
  assert.deepEqual(fieldInventory(), richInventory);
  assertNoAddedFields();
  const readingSourceOptions = control('Evidence source').children.map(n => n.value || n.attrs.value);
  for (const source of cases[0].observer_input.context_sources) assert.ok(!readingSourceOptions.includes(source.source_id), 'Context sources cannot be selected as adoption evidence');
  const otherTurn = cases[0].observer_input.dialogue_prefix.find(t => t.speaker !== 'giver');
  const ownTurn = cases[0].observer_input.dialogue_prefix.find(t => t.speaker === 'giver');
  assert.ok(otherTurn && ownTurn);
  await fill('Evidence source', otherTurn.utterance_id);
  result = await exported();
  assert.equal(result[firstId].participant_meanings_with_source_quotes[0].source_quotes[0].speaker, otherTurn.speaker);
  await fill('Evidence support', 'supported');
  await button('Check this draft').click();
  assert.ok(app.textContent.includes('A supported reading requires an exact own-speaker prefix quotation'));
  await fill('Evidence source', ownTurn.utterance_id);
  result = await exported();
  assert.equal(result[firstId].participant_meanings_with_source_quotes[0].source_quotes[0].speaker, ownTurn.speaker);
  assert.equal(result[firstId].participant_meanings_with_source_quotes[0].source_quotes[0].quote, ownTurn.text);
  await button('Check this draft').click();
  assert.ok(!app.textContent.includes('A supported reading requires an exact own-speaker prefix quotation'));
  await fill('Evidence source', '');
  result = await exported();
  assert.ok(!Object.hasOwn(result[firstId].participant_meanings_with_source_quotes[0].source_quotes[0], 'speaker'));
  await fill('Evidence source', ownTurn.utterance_id);
  await button('Remove reading').click();
  record('Original reading/focus/consequence controls are unchanged; source changes update speaker and quotes require exact own-speaker prefix evidence');
  const route = ['Route', 'current_below_start_segment', 'below', 'start'];
  const anotherRoute = ['Route', 'other_segment', 'below', 'start'];
  const thirdRoute = ['Route', 'third_segment', 'below', 'start'];
  const ruleCases = [
    {name: 'same known singleton', a: [route], b: [route], blocked: false, label: 'ALIGNED', expected: 'ALIGNED'},
    {name: 'disjoint known outputs', a: [route], b: [anotherRoute], blocked: false, label: 'POTENTIAL_MISMATCH', expected: 'POTENTIAL_MISMATCH'},
    {name: 'overlapping alternatives', a: [route, anotherRoute], b: [anotherRoute, thirdRoute], blocked: false, label: 'ALIGNED', expected: 'UNRESOLVED'},
    {name: 'equal multiple alternatives', a: [route, anotherRoute], b: [anotherRoute, route], blocked: false, label: 'ALIGNED', expected: 'UNRESOLVED'},
    {name: 'empty support set', a: [], b: [route], blocked: false, label: 'POTENTIAL_MISMATCH', expected: 'UNRESOLVED'},
    {name: 'MT10-style null required anchor', a: [['Route', 'current_below_start_segment', 'below', null]], b: [['Route', 'current_below_start_segment', 'below', null]], blocked: false, label: 'ALIGNED', expected: 'UNRESOLVED'},
    {name: 'nested unknown argument', a: [{route: {anchor: 'unknown'}}], b: [route], blocked: false, label: 'POTENTIAL_MISMATCH', expected: 'UNRESOLVED'},
    {name: 'explicit blocker', a: [route], b: [route], blocked: true, label: 'ALIGNED', expected: 'UNRESOLVED'},
    {name: 'pending blocker', a: [route], b: [route], blocked: null, label: 'ALIGNED', expected: 'UNRESOLVED'},
    {name: 'canonical object ordering and duplicate outputs', a: [{x: 1, y: 2}, {y: 2, x: 1}], b: [{y: 2, x: 1}], blocked: false, label: 'ALIGNED', expected: 'ALIGNED'},
  ];
  for (const test of ruleCases) {
    const draft = structuredClone(r2);
    const rr = draft[firstId];
    rr.focal_pair = [ownTurn.speaker, otherTurn.speaker];
    rr.participant_meanings_with_source_quotes = [ownTurn, otherTurn].map(turn => ({participant_id: turn.speaker, meaning: 'Software test fixture only.', support: 'supported', source_quotes: [{source_id: turn.utterance_id, speaker: turn.speaker, quote: turn.text}]}));
    rr.task_outputs = {supported_consequences: {[ownTurn.speaker]: test.a, [otherTurn.speaker]: test.b}};
    rr.blocking_uncertainty = test.blocked; rr.provisional_label = test.label;
    await fileImport('Import REVIEWS.json', 'rule-fixture.json', draft);
    await button('Check this draft').click();
    assert.equal(app.textContent.includes('F7 requires ' + test.expected), test.label !== test.expected, test.name);
    if (test.name.includes('null required')) assert.ok(app.textContent.includes('A required consequence value is null or UNKNOWN.'));
    result = await exported();
    assert.equal(result[firstId].provisional_label, test.label, 'Validation must not assign a label: ' + test.name);
    assert.equal(result[firstId].blocking_uncertainty, test.blocked);
  }
  record('Ten F7 fixtures check singleton/disjoint/overlap/empty/unknown/blocker rules without changing saved judgments');
  const missingSupport = structuredClone(r2);
  missingSupport[firstId].focal_pair = [ownTurn.speaker, otherTurn.speaker];
  missingSupport[firstId].task_outputs = {supported_consequences: {[ownTurn.speaker]: [route], [otherTurn.speaker]: [route]}};
  missingSupport[firstId].provisional_label = 'ALIGNED'; missingSupport[firstId].blocking_uncertainty = false;
  await fileImport('Import REVIEWS.json', 'missing-support.json', missingSupport);
  await button('Check this draft').click();
  assert.ok(app.textContent.includes('A definite judgment needs a supported reading for each focal participant.'));
  record('Known typed outputs do not substitute for participant-supported readings');
  await fileImport('Import REVIEWS.json', 'reader2.json', r2);
  const wording = read('wording/Tier_S_Wording_Alternatives.json');
  await fileImport('Import Tier S wording', 'Tier_S_Wording_Alternatives.json', wording);
  result = await exported();
  assert.equal(result[firstId].review_metadata.prior_exposure.assistant_draft, null);
  assert.ok(!app.textContent.includes(wording.cases[firstId].question_options[0]));
  await button('Open suggestions for this case').click();
  result = await exported();
  assert.equal(result[firstId].review_metadata.prior_exposure.assistant_draft, true);
  assert.equal(result[firstId].review_metadata.wording_exposure_events[0].before_prefix_first_review, true);
  await button('Use this wording').click();
  result = await exported();
  assert.equal(result[firstId].local_question, wording.cases[firstId].question_options[0]);
  for (const key of ['provisional_label', 'evidence_verified', 'include_in_pilot']) assert.equal(result[firstId][key], null);
  assert.equal(result[firstId].review_metadata.human_content_confirmed, false);
  assert.equal(result[firstId].review_status, r2[firstId].review_status);
  assert.equal(result[firstId].review_metadata.prefix_first_review_completed, false);
  assert.deepEqual(result[firstId].review_metadata.assistant_wording_fields, ['local_question']);
  const wordingHuman = await exportedHuman();
  assert.deepEqual(wordingHuman[firstId]['Reviewer and exposure']['Draft wording fields'], ['Local task question']);
  assert.deepEqual((await exportedReference())[firstId]['Reviewer and exposure']['Draft wording fields'], ['subtask_hypotheses[0].description']);
  assert.deepEqual(result[firstId].review_metadata.extra_provenance, r2[firstId].review_metadata.extra_provenance);
  record('Wording is hidden until opened; copying changes prose and exposure without judgment/verification/selection/completion');
  await fileImport('Import REVIEWS.json', 'reader2.json', r2);
  await fill('Reviewer', 'ui_test_reader');
  await fill('Local task question', 'Which task relation is supported at this prefix?');
  await fill('First participant', 'giver'); await fill('Second participant', 'follower');
  await fill('Review judgment', 'UNRESOLVED'); await fill('Why this judgment? Prefix evidence only', 'Test snapshot only: available support has not been established.');
  for (const key of ['Assistant drafts', 'System predictions', 'Released / other labels', 'Later dialogue or outcomes']) await fill(key, 'no');
  await checkbox('First prefix review completed', true);
  result = await exported();
  const firstSnapshot = result[firstId].review_metadata.first_pass_judgment_snapshot;
  assert.ok(firstSnapshot); assert.equal(result[firstId].review_metadata.first_pass_judgment_sha256, createHash('sha256').update(JSON.stringify(sorted(firstSnapshot))).digest('hex'));
  assert.ok(!Object.hasOwn(firstSnapshot, 'focus_selection_reason'));
  const snapshotHuman = await exportedHuman();
  assert.ok(Object.hasOwn(snapshotHuman[firstId]['Reviewer and exposure']['Saved first judgment'], 'Reviewer'));
  assert.ok(!Object.hasOwn(snapshotHuman[firstId]['Reviewer and exposure']['Saved first judgment'], 'reviewer_id'));
  assert.equal(snapshotHuman[firstId]['Reviewer and exposure']['Saved first judgment SHA-256'], result[firstId].review_metadata.first_pass_judgment_sha256);
  await button('Open suggestions for this case').click();
  result = await exported();
  assert.equal(result[firstId].review_metadata.prior_exposure.assistant_draft, false);
  assert.equal(result[firstId].review_metadata.wording_exposure_events[0].before_prefix_first_review, false);
  await button('Use this wording').click();
  result = await exported();
  assert.deepEqual(result[firstId].review_metadata.first_pass_judgment_snapshot, firstSnapshot);
  assert.equal(result[firstId].provisional_label, 'UNRESOLVED');
  assert.notEqual(result[firstId].local_question, firstSnapshot.local_question);
  record('First-pass snapshot and SHA256 freeze once; later consultation preserves prior exposure and copied text cannot overwrite snapshot');
  const notedPass = structuredClone(r2);
  Object.assign(notedPass[firstId], {reviewer_id: 'ui_note_fixture', local_question: 'Fixture local question.',
    focal_pair: [ownTurn.speaker, otherTurn.speaker], provisional_label: 'UNRESOLVED', prefix_only_rationale: 'Fixture only.',
    focus_source_ids: [ownTurn.utterance_id], focus_quotes: [{source_id: ownTurn.utterance_id, speaker: ownTurn.speaker, quote: ownTurn.text}]});
  notedPass[firstId].review_metadata.focus_selection_reason = '  Exact note retained in the first-pass snapshot.  ';
  await fileImport('Import REVIEWS.json', 'noted-first-pass.json', codec.toReferenceReviews(notedPass));
  await checkbox('First prefix review completed', true);
  result = await exported();
  const notedSnapshot = result[firstId].review_metadata.first_pass_judgment_snapshot;
  assert.equal(notedSnapshot.focus_selection_reason, notedPass[firstId].review_metadata.focus_selection_reason);
  const notedHash = createHash('sha256').update(JSON.stringify(sorted(notedSnapshot))).digest('hex');
  assert.equal(result[firstId].review_metadata.first_pass_judgment_sha256, notedHash);
  const strippedSnapshot = structuredClone(notedSnapshot); delete strippedSnapshot.focus_selection_reason;
  assert.notEqual(createHash('sha256').update(JSON.stringify(sorted(strippedSnapshot))).digest('hex'), notedHash);
  const notedReference = await exportedReference();
  assert.equal(notedReference[firstId]['Reviewer and exposure']['Saved first judgment'].focus.why_selected, notedSnapshot.focus_selection_reason);
  assert.ok(!Object.hasOwn(notedReference[firstId]['Reviewer and exposure'], 'focus_selection_reason'));
  assert.ok(!Object.hasOwn(notedReference[firstId]['Reviewer and exposure']['Saved first judgment'], 'focus_selection_reason'));
  await fileImport('Import REVIEWS.json', 'saved-noted-pass.json', notedReference);
  assert.deepEqual(await exported(), result);
  record('A nonempty JSON-only selection reason is captured in the canonical snapshot and hash, then roundtrips through reference focus without duplication');
  const invalid = structuredClone(r2); invalid[firstId].review_metadata.observer_input_sha256 = '0'.repeat(64);
  await fileImport('Import REVIEWS.json', 'wrong.json', invalid);
  assert.ok(document.getElementById('notice').textContent.includes('mismatched observer-input hash'));
  let afterRejected = await exported(); assert.deepEqual(afterRejected, result);
  await fileImport('Import REVIEWS.json', 'unknown.json', {UNKNOWN_CASE: r2[firstId]});
  assert.ok(document.getElementById('notice').textContent.includes('Unknown case ID'));
  record('Mismatched frozen hashes and unknown case IDs reject imports without overwriting current work');
  const collision = structuredClone(r2);
  collision[firstId]['Reviewer'] = collision[firstId].reviewer_id;
  await fileImport('Import REVIEWS.json', 'ambiguous.json', collision);
  assert.ok(document.getElementById('notice').textContent.includes('Ambiguous review key aliases'));
  assert.deepEqual(await exported(), result);
  const referenceCollision = structuredClone(r2);
  referenceCollision[firstId].review_metadata.assistant_wording_fields = ['local_question', 'Local task question'];
  await fileImport('Import REVIEWS.json', 'ambiguous-fields.json', referenceCollision);
  assert.ok(document.getElementById('notice').textContent.includes('Ambiguous field reference aliases'));
  assert.deepEqual(await exported(), result);
  const malformedReferences = [
    {...codec.toReferenceRecord(r2[firstId]), local_question: null},
    {...codec.toReferenceRecord(r2[firstId]), focus_quotes: []},
    {...codec.toReferenceRecord(r2[firstId]), subtask_hypotheses: [{description: 'One'}, {description: 'Two'}]},
    {...codec.toReferenceRecord(r2[firstId]), subtask_hypotheses: [{description: 'One', unsupported_property: true}]}
  ];
  const doubledWhy = codec.toReferenceRecord(r2[firstId]);
  doubledWhy.focus.why_selected = 'Duplicate note';
  doubledWhy['Reviewer and exposure'].focus_selection_reason = 'Duplicate note';
  malformedReferences.push(doubledWhy);
  for (const malformed of malformedReferences) {
    await fileImport('Import REVIEWS.json', 'unsupported-reference.json', {[firstId]: malformed});
    assert.ok(document.getElementById('notice').textContent.startsWith('Review import stopped:'));
    assert.deepEqual(await exported(), result);
  }
  record('Reference/legacy alias collisions, multiple hypotheses, unsupported hypothesis properties and duplicate why holders reject without losing work');
  const unrepresentableDraft = structuredClone(r2);
  unrepresentableDraft[firstId].local_question = {unsupported_legacy_shape: true};
  await fileImport('Import REVIEWS.json', 'unsupported-legacy-question.json', unrepresentableDraft);
  const priorDownload = lastBlob;
  await button('Download REVIEWS.json').click();
  assert.ok(document.getElementById('notice').textContent.startsWith('Review export stopped:'));
  assert.strictEqual(lastBlob, priorDownload);
  await fill('Local task question', 'Repaired fixture question.');
  assert.equal((await exported())[firstId].local_question, 'Repaired fixture question.');
  await fileImport('Import REVIEWS.json', 'restore-checked-fixture.json', result);
  assert.deepEqual(await exported(), result);
  record('Unrepresentable legacy content stops export with an explanation, retains the editable draft and downloads after correction');
  const opaque = structuredClone(r2);
  opaque[firstId].review_metadata.extra_provenance = {local_question: 'Unchanged nested history', 'Review judgment': ['provisional_label', 'Review judgment']};
  opaque[firstId].task_outputs = {participant_outputs: {'Review judgment': 'Unchanged dynamic key'}, supported_consequences: {giver: [{meaning: 'Unchanged typed payload key'}], follower: []}};
  assert.deepEqual(codec.toTechnicalReviews(codec.toHumanReviews(opaque)), opaque);
  assert.deepEqual(codec.toHumanReviews(opaque)[firstId]['Reviewer and exposure'].extra_provenance, opaque[firstId].review_metadata.extra_provenance);
  assert.deepEqual(codec.toHumanReviews(opaque)[firstId]['Task consequences']['Consequences by participant'], opaque[firstId].task_outputs.participant_outputs);
  opaque[firstId].focus_source_ids = ['fixture-turn-1', 'fixture-turn-2'];
  opaque[firstId].focus_quotes = [
    {source_id: 'fixture-turn-1', quote: 'Primary fixture text', speaker: 'giver', why_selected: {preserve: 'quote property'}, utterance_id: 'arbitrary legacy extra'},
    {source_id: 'fixture-turn-2', quote: 'Other fixture text', speaker: 'follower', custom: {keep: ['opaque']}}
  ];
  const opaqueReference = codec.toReferenceReviews(opaque);
  assert.deepEqual(opaqueReference[firstId].focus.quote_metadata, {why_selected: {preserve: 'quote property'}, utterance_id: 'arbitrary legacy extra'});
  assert.deepEqual(opaqueReference[firstId].focus.additional_quotes[0].custom, {keep: ['opaque']});
  assert.deepEqual(codec.toTechnicalReviews(opaqueReference), opaque);
  record('Ambiguous aliases reject without overwriting work; unknown history and opaque consequence/participant keys remain unchanged');
  const wwButton = find(n => n.tagName === 'BUTTON' && n.attrs['aria-label'] === 'Review WW02_WW02_r040'); await wwButton.click();
  const options = control('First participant').children.map(n => n.value || n.attrs.value);
  assert.ok(!options.includes('Audio'));
  record('Public Audio source is not offered as a focal game participant');
  if (outputDirectory) {
    fs.mkdirSync(outputDirectory, {recursive: true});
    fs.writeFileSync(path.join(outputDirectory, 'ui_blank_export.json'), JSON.stringify(blankReference, null, 2) + '\n');
    fs.writeFileSync(path.join(outputDirectory, 'ui_blank_export_human.json'), JSON.stringify(blankHuman, null, 2) + '\n');
    fs.writeFileSync(path.join(outputDirectory, 'ui_blank_export_technical.json'), JSON.stringify(blank, null, 2) + '\n');
    fs.writeFileSync(path.join(outputDirectory, 'ui_behavior_result.json'), JSON.stringify({record_type: 'dom_stub_behavior_validation_not_browser_or_research_results', checked_at_utc: new Date().toISOString(), checks: records.length, passed: records.length, visual_rendering_verified: false, checks_detail: records}, null, 2) + '\n');
  }
  console.log(JSON.stringify({checks: records.length, passed: records.length, visual_rendering_verified: false, checks_detail: records}, null, 2));
})().catch(error => { console.error(error.stack); process.exitCode = 1; });
