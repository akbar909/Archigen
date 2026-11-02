// A model URL may be the previous preview while its replacement is building.
export async function waitForModel({ fetchVersion, isCurrent, onStatus = () => {},
  maxAttempts = 300, intervalMs = 2500, sleep = ms => new Promise(resolve => setTimeout(resolve, ms)) }) {
  let failures = 0;
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    if (!isCurrent()) return { status: 'cancelled' };
    let version;
    try {
      const data = await fetchVersion();
      if (!isCurrent()) return { status: 'cancelled' };
      version = data?.version;
      if (!version) throw new Error('Missing version');
      failures = 0;
    } catch (error) {
      if (!isCurrent()) return { status: 'cancelled' };
      if ([401, 403, 404].includes(error.response?.status) || ++failures >= 3) {
        return { status: 'unavailable', error: 'Could not check the 3D build status. Reopen this version to check again.' };
      }
    }
    if (version) {
      const job = version.generation_3d;
      onStatus(job || null);
      if (['failed', 'timed_out'].includes(job?.status)) {
        return { status: 'failed', error: job.error || 'The 3D build failed. Check the worker logs before retrying.', version };
      }
      const url = version.glb_url || version.design?.glb_url;
      if (url && job?.status !== 'running') return { status: 'completed', url, version };
    }
    if (attempt + 1 < maxAttempts) await sleep(intervalMs);
  }
  return { status: 'waiting', error: 'No completed 3D model has been returned yet. Check the worker before retrying Build 3D.' };
}
