from __future__ import annotations


class ActionContext:
    """Lightweight adapter so action handlers don't depend on Sequencer internals."""

    def __init__(self, sequencer):
        self._seq = sequencer

    @property
    def inst_mgr(self):
        return self._seq.inst_mgr

    @property
    def can_mgr(self):
        return self._seq.can_mgr

    @property
    def running(self):
        return self._seq.running

    @property
    def stop_event(self):
        return self._seq.stop_event

    @property
    def current_index(self):
        return getattr(self._seq, "_current_index", None)

    def log(self, level, message):
        try:
            self._seq._log(level, message)
        except Exception:
            pass

    def log_cmd(self, message):
        try:
            self._seq._log_cmd(message)
        except Exception:
            pass

    def emit_info(self, message, index=None):
        idx = self.current_index if index is None else index
        if idx is None:
            idx = 0
        try:
            self._seq.action_info.emit(idx, message)
        except Exception:
            pass

    def set_current_step(self, step_index):
        try:
            self._seq.current_step = step_index
        except Exception:
            pass
