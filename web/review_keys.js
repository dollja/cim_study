/* Lossless review-key translation. Only the declared key contexts are renamed. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.CimReviewKeys = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
  const own = (value, key) => Object.prototype.hasOwnProperty.call(value, key);
  const clone = value => Array.isArray(value) ? value.map(clone) : object(value)
    ? Object.fromEntries(Object.entries(value).map(([key, item]) => [key, clone(item)])) : value;
  const REFERENCE_ALIASES = {
    subtask_hypotheses: 'local_question',
    participant_interpretations: 'participant_meanings_with_source_quotes',
    consequence_analysis: 'task_outputs',
    rationale: 'prefix_only_rationale',
    selection_reason: 'inclusion_or_exclusion_reason'
  };
  const REFERENCE_FIELD_PATHS = {
    local_question: 'subtask_hypotheses[0].description',
    focus_source_ids: 'focus.selected_utterance_ids',
    focus_quotes: 'focus',
    participant_meanings_with_source_quotes: 'participant_interpretations',
    task_outputs: 'consequence_analysis',
    prefix_only_rationale: 'rationale',
    inclusion_or_exclusion_reason: 'selection_reason'
  };

  function createCodec(spec) {
    if (!object(spec) || !object(spec.maps) || !object(spec.maps.review)) throw new Error('Review key mapping is missing its review context.');
    const maps = new Map(); const reverse = new Map();
    for (const [context, entries] of Object.entries(spec.maps)) {
      if (!object(entries)) throw new Error('Invalid review key context: ' + context);
      const forward = new Map(); const back = new Map();
      for (const [technical, human] of Object.entries(entries)) {
        if (typeof human !== 'string' || !human) throw new Error('Invalid human review key: ' + technical);
        if (back.has(human)) throw new Error('Ambiguous human review key: ' + human);
        if (own(entries, human) && human !== technical) throw new Error('Ambiguous technical/human review alias: ' + human);
        forward.set(technical, human); back.set(human, technical);
      }
      maps.set(context, forward); reverse.set(context, back);
    }
    const referenceFieldsBack = new Map(Object.entries(REFERENCE_FIELD_PATHS).map(([technical, reference]) => [reference, technical]));
    for (const [reference, technical] of Object.entries(REFERENCE_ALIASES)) referenceFieldsBack.set(reference, technical);
    const humanKey = technical => maps.get('review').get(technical) || technical;
    function fieldReferences(value, outputMode) {
      if (!Array.isArray(value)) return clone(value);
      const seen = new Map();
      return value.map(item => {
        if (typeof item !== 'string') return clone(item);
        const technical = referenceFieldsBack.get(item) || reverse.get('review').get(item) || item;
        if (seen.has(technical) && seen.get(technical) !== item) throw new Error('Ambiguous field reference aliases: ' + seen.get(technical) + ' / ' + item);
        seen.set(technical, item);
        if (outputMode === 'reference') return own(REFERENCE_FIELD_PATHS, technical) ? REFERENCE_FIELD_PATHS[technical] : humanKey(technical);
        return outputMode === 'human' ? humanKey(technical) : technical;
      });
    }
    function quoteShape(value) {
      if (!object(value) || typeof value.source_id !== 'string' || typeof value.quote !== 'string') throw new Error('Focus quotes need string source_id and quote values.');
      if (own(value, 'speaker') && typeof value.speaker !== 'string') throw new Error('Focus quote speaker must be a string when present.');
      return value;
    }
    function unpackFocus(focus) {
      if (!object(focus)) throw new Error('focus must be an object.');
      const allowed = new Set(['utterance_id', 'quote', 'speaker', 'why_selected', 'additional_quotes', 'selected_utterance_ids', 'quote_metadata']);
      for (const key of Object.keys(focus)) if (!allowed.has(key)) throw new Error('Unsupported focus property: ' + key);
      for (const key of ['utterance_id', 'quote', 'additional_quotes', 'selected_utterance_ids']) if (!own(focus, key)) throw new Error('focus is missing ' + key + '.');
      if (!Array.isArray(focus.selected_utterance_ids) || focus.selected_utterance_ids.some(id => typeof id !== 'string')) throw new Error('focus.selected_utterance_ids must be an array of strings.');
      if (!Array.isArray(focus.additional_quotes)) throw new Error('focus.additional_quotes must be an array.');
      if (own(focus, 'why_selected') && focus.why_selected !== null && typeof focus.why_selected !== 'string') throw new Error('focus.why_selected must be text or null.');
      const quotes = [];
      const empty = focus.utterance_id === null && focus.quote === null;
      if (empty) {
        if (own(focus, 'speaker') || own(focus, 'quote_metadata') || focus.additional_quotes.length) throw new Error('An empty primary focus cannot have a speaker, quote metadata or additional quotes.');
      } else {
        const primary = {source_id: focus.utterance_id, quote: focus.quote};
        if (own(focus, 'speaker')) primary.speaker = focus.speaker;
        quoteShape(primary);
        if (own(focus, 'quote_metadata')) {
          if (!object(focus.quote_metadata)) throw new Error('focus.quote_metadata must be an object.');
          const reserved = new Set(['source_id', 'quote', 'speaker', 'Source turn', 'Exact expression', 'Speaker']);
          for (const key of Object.keys(focus.quote_metadata)) if (reserved.has(key)) throw new Error('Ambiguous primary quote metadata key: ' + key);
          for (const [key, item] of Object.entries(focus.quote_metadata)) Object.defineProperty(primary, key, {value: clone(item), enumerable: true, writable: true, configurable: true});
        }
        quotes.push(primary);
      }
      for (const additional of focus.additional_quotes) {
        if (!object(additional) || !own(additional, 'utterance_id')) throw new Error('Each additional focus quote needs utterance_id.');
        if (['source_id', 'Source turn', 'Speaker', 'Exact expression'].some(key => own(additional, key))) throw new Error('Ambiguous additional quote aliases.');
        const quote = Object.fromEntries(Object.entries(additional).map(([key, item]) => [key === 'utterance_id' ? 'source_id' : key, clone(item)]));
        quotes.push(quoteShape(convert(quote, 'focus_quote', 'technical')));
      }
      return {ids: clone(focus.selected_utterance_ids), quotes,
        hasReason: own(focus, 'why_selected'), reason: own(focus, 'why_selected') ? focus.why_selected : null};
    }
    function normalizeReview(value, snapshotContext) {
      const entries = []; const seen = new Map(); let focus = null; let hasFocus = false;
      for (const [key, item] of Object.entries(value)) {
        if (key === 'focus') {
          for (const technical of ['focus_source_ids', 'focus_quotes']) {
            if (seen.has(technical)) throw new Error('Ambiguous review key aliases: ' + seen.get(technical) + ' / focus');
            seen.set(technical, key);
          }
          focus = unpackFocus(item); hasFocus = true; continue;
        }
        const technical = (own(REFERENCE_ALIASES, key) ? REFERENCE_ALIASES[key] : null) || reverse.get('review').get(key) || key;
        if (seen.has(technical)) throw new Error('Ambiguous review key aliases: ' + seen.get(technical) + ' / ' + key);
        seen.set(technical, key);
        if (key === 'subtask_hypotheses') {
          if (!Array.isArray(item) || item.length !== 1 || !object(item[0]) || Object.keys(item[0]).length !== 1 || !own(item[0], 'description') || (item[0].description !== null && typeof item[0].description !== 'string')) throw new Error('subtask_hypotheses must contain exactly one object with only a text-or-null description.');
          entries.push([technical, clone(item[0].description)]);
        } else entries.push([technical, clone(item)]);
      }
      const normalized = Object.fromEntries(entries);
      const snapshot = snapshotContext === true || (!own(normalized, 'review_status') && !own(normalized, 'review_metadata'));
      if (hasFocus) {
        normalized.focus_source_ids = focus.ids; normalized.focus_quotes = focus.quotes;
        const metadata = own(normalized, 'review_metadata') ? normalized.review_metadata : null;
        const hasStoredReason = own(normalized, 'focus_selection_reason') || (object(metadata) && own(metadata, 'focus_selection_reason'));
        if (focus.hasReason && hasStoredReason) throw new Error('Ambiguous focus-selection reason: both why_selected and an internal reason are present.');
        if (focus.reason !== null) {
          if (snapshot) normalized.focus_selection_reason = focus.reason;
          else {
            if (own(normalized, 'review_metadata') && !object(metadata)) throw new Error('A focus-selection reason needs an object review_metadata container.');
            if (!own(normalized, 'review_metadata')) normalized.review_metadata = {};
            normalized.review_metadata.focus_selection_reason = focus.reason;
          }
        }
      }
      return {value: normalized, snapshot};
    }
    function packFocus(ids, rawQuotes, reason) {
      if (!Array.isArray(ids) || ids.some(id => typeof id !== 'string')) throw new Error('focus_source_ids must be an array of strings for reference export.');
      if (!Array.isArray(rawQuotes)) throw new Error('focus_quotes must be an array for reference export.');
      const quotes = rawQuotes.map(value => quoteShape(convert(value, 'focus_quote', 'technical')));
      const first = quotes[0];
      const focus = {utterance_id: first ? first.source_id : null, quote: first ? first.quote : null};
      if (first && own(first, 'speaker')) focus.speaker = first.speaker;
      focus.why_selected = reason;
      focus.additional_quotes = quotes.slice(1).map(quote => {
        if (own(quote, 'utterance_id')) throw new Error('Ambiguous additional quote source aliases.');
        return Object.fromEntries(Object.entries(quote).map(([key, item]) => [key === 'source_id' ? 'utterance_id' : key, clone(item)]));
      });
      focus.selected_utterance_ids = clone(ids);
      if (first) {
        const metadata = Object.fromEntries(Object.entries(first).filter(([key]) => !['source_id', 'quote', 'speaker'].includes(key)).map(([key, item]) => [key, clone(item)]));
        if (Object.keys(metadata).length) focus.quote_metadata = metadata;
      }
      return focus;
    }
    function referenceReview(value, snapshot) {
      const idsKey = humanKey('focus_source_ids'); const quotesKey = humanKey('focus_quotes');
      const hasIds = own(value, idsKey); const hasQuotes = own(value, quotesKey);
      if (hasIds !== hasQuotes) throw new Error('Reference export requires both focus_source_ids and focus_quotes; missing fields cannot be inferred.');
      const metadataKey = humanKey('review_metadata');
      const metadata = value[metadataKey];
      const metaReason = object(metadata) && own(metadata, 'focus_selection_reason');
      const topReason = own(value, 'focus_selection_reason');
      if (metaReason && topReason) throw new Error('Ambiguous focus-selection reason: both top-level and metadata reasons are present.');
      if (topReason && !snapshot) throw new Error('A full review stores focus_selection_reason in review metadata.');
      const hasReason = metaReason || topReason;
      const reason = topReason ? value.focus_selection_reason : metaReason ? metadata.focus_selection_reason : null;
      if (hasReason && typeof reason !== 'string') throw new Error('Stored focus_selection_reason must be text for reference export.');
      if (hasReason && !hasIds) throw new Error('A focus-selection reason needs both focus fields for reference export.');
      const focus = hasIds ? packFocus(value[idsKey], value[quotesKey], reason) : null;
      const output = []; let focusWritten = false;
      for (const [key, item] of Object.entries(value)) {
        if (key === idsKey || key === quotesKey) {
          if (!focusWritten) { output.push(['focus', focus]); focusWritten = true; }
        } else if (key === humanKey('local_question')) {
          if (item !== null && typeof item !== 'string') throw new Error('local_question must be text or null for reference export.');
          output.push(['subtask_hypotheses', [{description: clone(item)}]]);
        } else if (snapshot && key === 'focus_selection_reason') {
          // Its complete value is represented by focus.why_selected.
        } else if (key === metadataKey && metaReason) {
          output.push([key, Object.fromEntries(Object.entries(item).filter(([name]) => name !== 'focus_selection_reason'))]);
        } else {
          const technical = reverse.get('review').get(key) || key;
          const replacement = Object.entries(REFERENCE_ALIASES).find(([reference, original]) => original === technical && reference !== 'subtask_hypotheses');
          output.push([replacement ? replacement[0] : key, clone(item)]);
        }
      }
      return Object.fromEntries(output);
    }
    function convert(value, context, outputMode, snapshotContext = null) {
      if (!object(value)) return clone(value);
      let snapshot = false;
      if (context === 'review') {
        const normalized = normalizeReview(value, snapshotContext);
        value = normalized.value; snapshot = normalized.snapshot;
      }
      const forward = maps.get(context); const back = reverse.get(context);
      if (!forward || !back) throw new Error('Unknown review key context: ' + context);
      const children = (spec.children || {})[context] || {};
      const references = (spec.field_reference_lists || {})[context] || [];
      const seen = new Map(); const entries = [];
      for (const [key, item] of Object.entries(value)) {
        const technical = back.get(key) || key;
        if (seen.has(technical)) throw new Error('Ambiguous review key aliases: ' + seen.get(technical) + ' / ' + key);
        seen.set(technical, key);
        const outputKey = outputMode !== 'technical' ? (forward.get(technical) || technical) : technical;
        let translated;
        if (references.includes(technical)) translated = fieldReferences(item, outputMode);
        else if (own(children, technical)) {
          const child = children[technical];
          translated = child.array
            ? (Array.isArray(item) ? item.map(entry => convert(entry, child.context, outputMode)) : clone(item))
            : convert(item, child.context, outputMode, technical === 'first_pass_judgment_snapshot' ? true : null);
        } else translated = clone(item);
        entries.push([outputKey, translated]);
      }
      const converted = Object.fromEntries(entries);
      return context === 'review' && outputMode === 'reference' ? referenceReview(converted, snapshot) : converted;
    }
    function reviews(value, outputMode) {
      if (!object(value)) return clone(value);
      return Object.fromEntries(Object.entries(value).map(([id, record]) => [id, convert(record, 'review', outputMode, false)]));
    }
    return {
      toHumanReviews: value => reviews(value, 'human'),
      toTechnicalReviews: value => reviews(value, 'technical'),
      toReferenceReviews: value => reviews(value, 'reference'),
      toHumanRecord: value => convert(value, 'review', 'human'),
      toTechnicalRecord: value => convert(value, 'review', 'technical'),
      toReferenceRecord: value => convert(value, 'review', 'reference')
    };
  }
  return {createCodec};
});
