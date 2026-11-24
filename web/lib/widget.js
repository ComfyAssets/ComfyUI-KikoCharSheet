// Pure helper for writing a ComfyUI widget value (no DOM, no ComfyUI imports).

/**
 * Set the widget value so its callback runs exactly once. Current frontends' DOM widget setter
 * already calls `callback`; older plain widgets do not, so call it only when the setter didn't.
 */
export function setValueOnce(widget, value) {
  const ownCallback = Object.prototype.hasOwnProperty.call(widget, "callback");
  const original = widget.callback;
  let fired = false;
  const probe = function (...args) {
    fired = true;
    return original?.apply(this, args);
  };
  widget.callback = probe;
  try {
    widget.value = value;
  } finally {
    if (widget.callback === probe) {
      if (ownCallback) widget.callback = original;
      else delete widget.callback;
    }
  }
  if (!fired) original?.call(widget, value);
}

/**
 * Also call `watcher(value)` whenever the widget's callback runs (after the original, which keeps
 * its `this` and return value). Returns `unwatch`: it puts the original back when our wrapper is
 * still installed; when someone wrapped it later, it only silences the watcher so their chain holds.
 */
export function watchCallback(widget, watcher) {
  const ownCallback = Object.prototype.hasOwnProperty.call(widget, "callback");
  const original = widget.callback;
  let active = true;
  const wrapper = function (...args) {
    const result = original?.apply(this, args);
    if (active) {
      try {
        watcher(...args);
      } catch (err) {
        console.warn("[CharSheet] widget watcher failed:", err);
      }
    }
    return result;
  };
  widget.callback = wrapper;
  return () => {
    if (!active) return;
    active = false;
    if (widget.callback !== wrapper) return;
    if (ownCallback) widget.callback = original;
    else delete widget.callback;
  };
}
