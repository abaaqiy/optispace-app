import { useCallback, useEffect, useState } from 'react';

export const LIVE_REFRESH_MS = 5000;

// Wait for each response before scheduling another request. Slow connections
// must not cause overlapping polls or repeatedly abort a response in progress.
export default function useLiveData(key, load) {
  const [revision, setRevision] = useState(0);
  const [result, setResult] = useState(null);
  const refresh = useCallback(() => setRevision(value => value + 1), []);

  useEffect(() => {
    let active = true;
    let timer;
    const controller = new AbortController();
    async function update() {
      try {
        const data = await load({ signal: controller.signal });
        if (active) setResult({ key, revision, data, error: '', receivedAt: performance.now(), updatedAt: Date.now() });
      } catch (error) {
        if (active) setResult({ key, revision, data: null, error: error.message });
      } finally {
        if (active) timer = setTimeout(update, LIVE_REFRESH_MS);
      }
    }
    update();
    return () => {
      active = false;
      clearTimeout(timer);
      controller.abort();
    };
  }, [key, load, revision]);

  useEffect(() => {
    const onVisible = () => { if (!document.hidden) refresh(); };
    window.addEventListener('focus', refresh);
    window.addEventListener('online', refresh);
    window.addEventListener('optispace:reservations-changed', refresh);
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      window.removeEventListener('focus', refresh);
      window.removeEventListener('online', refresh);
      window.removeEventListener('optispace:reservations-changed', refresh);
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, [refresh]);

  const loading = result?.key !== key;
  return {
    data: loading ? null : result.data,
    error: loading ? '' : result.error,
    receivedAt: result?.receivedAt,
    updatedAt: result?.updatedAt,
    loading,
    refreshing: loading || result.revision !== revision,
    refresh,
  };
}
