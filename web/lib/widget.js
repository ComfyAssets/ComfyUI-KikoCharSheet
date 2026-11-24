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
