import test from 'node:test';
import assert from 'node:assert/strict';
import { waitForModel } from './modelGeneration.js';

test('a build lasting more than the old 80 attempts completes without a false timeout', async () => {
  let reads = 0;
  const result = await waitForModel({ isCurrent: () => true, sleep: async () => {},
    fetchVersion: async () => ({version: ++reads <= 85 ? {generation_3d:{status:'running'}} : {glb_url:'new.glb',generation_3d:{status:'completed'}}}) });
  assert.equal(result.status, 'completed');
  assert.equal(result.url, 'new.glb');
  assert.equal(reads, 86);
});

test('previous preview is not mistaken for the replacement model', async () => {
  let reads = 0;
  const result = await waitForModel({ isCurrent: () => true, sleep: async () => {}, maxAttempts:3,
    fetchVersion: async () => ({version: {glb_url:++reads === 1 ? 'old.glb' : 'new.glb',generation_3d:{status:reads===1?'running':'completed'}}}) });
  assert.equal(result.url, 'new.glb');
  assert.equal(reads, 2);
});

test('worker failure is reported immediately even when an old model exists', async () => {
  const error = 'Blender worker error (500): Blender generation process failed';
  let sleeps = 0;
  const result = await waitForModel({ isCurrent: () => true, sleep: async () => { sleeps++; },
    fetchVersion: async () => ({version:{glb_url:'old.glb',generation_3d:{status:'failed',error}}}) });
  assert.equal(result.status, 'failed');
  assert.equal(result.error, error);
  assert.equal(sleeps, 0);
});

test('switching versions during an in-flight read never applies the previous result', async () => {
  let current = true, statuses = 0;
  const result = await waitForModel({ isCurrent: () => current, onStatus: () => { statuses++; },
    fetchVersion: async () => { current=false; return {version:{glb_url:'wrong-version.glb'}}; } });
  assert.equal(result.status, 'cancelled');
  assert.equal(statuses, 0);
});

test('connection problems stop with a status error rather than a claimed Blender timeout', async () => {
  let reads = 0;
  const result = await waitForModel({ isCurrent: () => true, sleep: async () => {},
    fetchVersion: async () => { reads++; throw new Error('Network unavailable'); } });
  assert.equal(result.status, 'unavailable');
  assert.match(result.error, /check the 3D build status/);
  assert.equal(reads, 3);
});

test('legacy completed versions work and exhausted polling does not claim generation failure', async () => {
  const completed = await waitForModel({ isCurrent: () => true, fetchVersion: async () => ({version:{design:{glb_url:'legacy.glb'}}}) });
  assert.equal(completed.url, 'legacy.glb');
  const pending = await waitForModel({ isCurrent: () => true, maxAttempts:2, sleep: async () => {},
    fetchVersion: async () => ({version:{generation_3d:{status:'running'}}}) });
  assert.equal(pending.status, 'waiting');
  assert.doesNotMatch(pending.error, /failed|timed out/i);
});
