from __future__ import annotations

from threading import Lock

try:
    from win10toast import ToastNotifier
except Exception:  # pragma: no cover
    ToastNotifier = None


class Notifier:
    def __init__(self) -> None:
        self._toast = ToastNotifier() if ToastNotifier else None
        self._lock = Lock()

    def show(self, title: str, message: str) -> None:
        if not self._toast:
            return
        with self._lock:
            try:
                self._toast.show_toast(title, message, threaded=True, duration=2)
            except Exception:
                pass
