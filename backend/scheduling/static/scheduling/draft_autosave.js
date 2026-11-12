/* Debounced, ordered saves. Only failures are announced. No source-image upload. */
(() => {
  window.OptispaceDraftAutosave = function ({ snapshot, initialSnapshot, send, accept, warn, timers = window }) {
    let saved = JSON.stringify(initialSnapshot || snapshot()), timer, running = null, retry = null;
    let paused = false, blocked = false, failures = 0, firstChange = 0;
    const dirty = () => JSON.stringify(snapshot()) !== saved || !!retry;
    const clear = () => { timers.clearTimeout(timer); timer = null; };
    function schedule() {
      if (paused || blocked) return;
      clear();
      if (!dirty()) { firstChange = 0; return; }
      firstChange ||= Date.now();
      timer = timers.setTimeout(flush, Math.min(1000, Math.max(0, 5000 - (Date.now() - firstChange))));
    }
    async function flush() {
      clear();
      if (running) return running;
      if (paused || blocked || !dirty()) return;
      const payload = retry || snapshot();
      const encoded = JSON.stringify(payload);
      running = (async () => {
        try {
          const result = await send(payload);
          accept(result); saved = encoded; retry = null; failures = 0; firstChange = 0;
          warn('');
        } catch (error) {
          blocked = !!error.permanent;
          retry = payload;
          failures++;
          warn(blocked ? error.message : 'Changes could not be saved. Keep this page open; autosave will retry.', error);
        } finally {
          running = null;
          if (!paused && !blocked && dirty()) {
            if (failures) timer = timers.setTimeout(flush, Math.min(30000, 2000 * 2 ** Math.min(failures - 1, 4)));
            else schedule();
          }
        }
      })();
      return running;
    }
    return {
      changed: schedule, flush, dirty,
      async beforeSubmit() {
        paused = true; clear();
        if (running) await running;
        if (blocked) return false;
        // Synchronize the latest edits and token before Save/Validate submits.
        // If an earlier response was lost, retry its exact state first, then
        // send any edits made while that request was in flight.
        while (dirty()) {
          paused = false; await flush(); paused = true; clear();
          if (retry || blocked) return false;
        }
        return true;
      },
      resume() { paused = false; schedule(); },
      stop() { paused = true; clear(); },
    };
  };
})();
