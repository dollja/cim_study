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
    function fieldReferences(value, humanOutput) {
      if (!Array.isArray(value)) return clone(value);
      const seen = new Map();
      return value.map(item => {
        if (typeof item !== 'string') return clone(item);
        const technical = reverse.get('review').get(item) || item;
        if (seen.has(technical) && seen.get(technical) !== item) throw new Error('Ambiguous field reference aliases: ' + seen.get(technical) + ' / ' + item);
        seen.set(technical, item);
        return humanOutput ? (maps.get('review').get(technical) || technical) : technical;
      });
    }
    function convert(value, context, humanOutput) {
      if (!object(value)) return clone(value);
      const forward = maps.get(context); const back = reverse.get(context);
      if (!forward || !back) throw new Error('Unknown review key context: ' + context);
      const children = (spec.children || {})[context] || {};
      const references = (spec.field_reference_lists || {})[context] || [];
      const seen = new Map(); const entries = [];
      for (const [key, item] of Object.entries(value)) {
        const technical = back.get(key) || key;
        if (seen.has(technical)) throw new Error('Ambiguous review key aliases: ' + seen.get(technical) + ' / ' + key);
        seen.set(technical, key);
        const outputKey = humanOutput ? (forward.get(technical) || technical) : technical;
        let translated;
        if (references.includes(technical)) translated = fieldReferences(item, humanOutput);
        else if (own(children, technical)) {
          const child = children[technical];
          translated = child.array
            ? (Array.isArray(item) ? item.map(entry => convert(entry, child.context, humanOutput)) : clone(item))
            : convert(item, child.context, humanOutput);
        } else translated = clone(item);
        entries.push([outputKey, translated]);
      }
      return Object.fromEntries(entries);
    }
    function reviews(value, humanOutput) {
      if (!object(value)) throw new Error('Expected a case-ID map of reviews.');
      return Object.fromEntries(Object.entries(value).map(([id, record]) => [id, convert(record, 'review', humanOutput)]));
    }
    return {
      toHumanReviews: value => reviews(value, true),
      toTechnicalReviews: value => reviews(value, false),
      toHumanRecord: value => convert(value, 'review', true),
      toTechnicalRecord: value => convert(value, 'review', false)
    };
  }
  return {createCodec};
});
