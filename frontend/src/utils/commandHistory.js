import { clone } from './cadGeometry.js';
const escape = key => String(key).replaceAll('~', '~0').replaceAll('/', '~1');
const equal = (a, b) => JSON.stringify(a) === JSON.stringify(b);
// Arrays are replaced atomically: deletion/reordering cannot shift later patch paths.
export function diffJson(before, after, path = '') {
  if (equal(before, after)) return [];
  if (!before || !after || typeof before !== 'object' || typeof after !== 'object' || Array.isArray(before) || Array.isArray(after)) {
    return [{
      op: 'replace',
      path,
      value: clone(after)
    }];
  }
  const result = [];
  for (const key of Object.keys(before)) if (!(key in after)) result.push({
    op: 'remove',
    path: `${path}/${escape(key)}`
  });
  for (const key of Object.keys(after)) {
    const next = `${path}/${escape(key)}`;
    if (!Object.hasOwn(before, key)) result.push({
      op: 'add',
      path: next,
      value: clone(after[key])
    });else result.push(...diffJson(before[key], after[key], next));
  }
  return result;
}
export function applyPatches(document, patches) {
  let result = clone(document);
  for (const patch of patches) {
    if (!['add', 'replace', 'remove'].includes(patch.op)) throw new Error('Unsupported patch operation');
    if (!patch.path) {
      result = clone(patch.value);
      continue;
    }
    const keys = patch.path.slice(1).split('/').map(k => k.replaceAll('~1', '/').replaceAll('~0', '~'));
    if (keys.some(k => ['__proto__', 'prototype', 'constructor'].includes(k))) throw new Error('Unsafe patch path');
    let target = result;
    for (const key of keys.slice(0, -1)) {
      if (!target || !Object.hasOwn(target, key)) throw new Error('Patch path does not exist');
      target = target[key];
    }
    const key = keys.at(-1);
    if (patch.op === 'remove') {
      if (Array.isArray(target)) target.splice(Number(key), 1);else delete target[key];
    } else if (Array.isArray(target) && patch.op === 'add') target.splice(key === '-' ? target.length : Number(key), 0, clone(patch.value));else target[key] = clone(patch.value);
  }
  return result;
}
export function createCommand(before, after, description) {
  return {
    description,
    timestamp: Date.now(),
    patches: diffJson(before, after),
    inversePatches: diffJson(after, before)
  };
}
