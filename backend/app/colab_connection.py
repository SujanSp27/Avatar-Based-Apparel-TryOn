"""Automatic connection lifecycle, independent of health requests and inference."""
import logging
import time
from threading import Event, Lock, Thread

from backend.app.config import ROOT, settings
from scripts.auto_connect_colab import ColabRecovery

logger = logging.getLogger(__name__)
REASONS = {
    'connecting': 'Preparing your online try-on service automatically.',
    'loading': 'The online model is loading. The app will become ready automatically.',
    'setting_up': 'Restoring the online model after a Colab restart. This first setup can take several minutes; the app will resume automatically.',
    'setup_failed': 'Colab model setup failed repeatedly. Check the worker setup log in the existing notebook.',
    'worker_failed': 'The Colab worker could not start after three attempts. Check its worker log in the existing notebook.',
    'notebook_busy': 'Waiting for the existing Colab task. Your running work will not be restarted.',
    'browser_required': 'Waiting for the existing Colab tab. Keep it open and complete any Google sign-in or permission prompt; the app resumes automatically.',
    'runtime_expired': 'The saved Colab runtime has expired and its worker files are gone. The online worker needs to be restored.',
    'runtime_identified': 'Checking the existing Colab runtime before recovering its worker.',
    'runtime_changed': 'Verifying the replacement Colab GPU before safely restoring the worker. Recovery continues automatically.',
    'recovery_delayed': 'Colab has not answered its runtime check. The existing request is preserved; keep the notebook connected. Retry checks that request without starting another task.',
    'stale': 'The last model check has expired. Checking the connection again automatically.',
    'recovering_tunnel': 'The Colab worker connection failed. Verifying it before safely restarting the idle worker; files and completed results are retained.',
    'gpu_unavailable': 'The existing Colab runtime has no GPU. Enable its GPU runtime; the app will detect it automatically.',
    'not_configured': 'The existing Colab notebook has not been configured on this installation.',
    'bridge_unavailable': 'The Colab connection helper is unavailable on this installation.',
}


class ColabConnection:
    def __init__(self, worker, recovery=None):
        self.worker = worker
        self.recovery = recovery or ColabRecovery(ROOT, settings.online_connection_path)
        self._stop = Event()
        self._wake = Event()
        self._lock = Lock()
        self._check_lock = Lock()
        self._retry_requested = False
        self._last_retry = -float('inf')
        self._updated_at = time.monotonic()
        self._unavailable_since = time.monotonic()
        self._thread = None
        self._snapshot = {**worker.availability(), 'available': False,
                          'connectionState': 'connecting', 'reason': REASONS['connecting'],
                          'automaticConnection': True}

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = Thread(target=self._run, name='colab-connection', daemon=True)
        self._thread.start()

    def close(self):
        self._stop.set()
        self._wake.set()
        if self._thread:
            self._thread.join(timeout=5)

    def snapshot(self):
        with self._lock:
            snapshot = dict(self._snapshot)
            if time.monotonic() - self._updated_at > 30:
                snapshot.update(available=False, connectionState='stale', reason=REASONS['stale'])
            state = snapshot['connectionState']
            unavailable = (time.monotonic() - self._unavailable_since > 180 or state in {
                'stale', 'recovery_delayed', 'setup_failed', 'worker_failed', 'gpu_unavailable',
                'browser_required', 'not_configured', 'bridge_unavailable'})
            snapshot['displayState'] = ('Ready' if snapshot['available'] else
                'Temporarily unavailable' if unavailable else
                'Recovering' if state in {'runtime_changed', 'setting_up', 'loading', 'recovering_tunnel'} else 'Preparing')
            return snapshot

    def retry(self):
        """Wake the single monitor; never execute notebook work in an HTTP request."""
        with self._lock:
            now = time.monotonic()
            if now - self._last_retry >= 5:
                self._last_retry = now
                self._retry_requested = True
                self._wake.set()
        return self.snapshot()

    def check(self):
        if not self._check_lock.acquire(blocking=False):
            return
        try:
            self._check()
        finally:
            self._check_lock.release()

    def _check(self):
        with self._lock:
            retry = self._retry_requested
            self._retry_requested = False
        if retry:
            self.recovery.next_attempt = 0
        availability = self.worker.availability(check_connection=True)
        state = 'ready'
        if not availability['available']:
            state = self.recovery.tick() if settings.online_auto_connect else 'connecting'
            state = state or self.snapshot()['connectionState']
            if state == 'ready':
                # A URL in a notebook output is not proof the tunnel is reachable.
                availability = self.worker.availability(check_connection=True)
                if not availability['available']:
                    state = 'connecting'
            availability['reason'] = None if availability['available'] else REASONS.get(state, REASONS['connecting'])
        with self._lock:
            self._updated_at = time.monotonic()
            if availability['available'] or self._snapshot.get('available'):
                self._unavailable_since = self._updated_at
            self._snapshot = {**availability, 'connectionState': state,
                              'automaticConnection': settings.online_auto_connect}

    def _run(self):
        while not self._stop.is_set():
            try:
                self.check()
            except Exception as exc:
                # Never log notebook outputs or private worker credentials.
                logger.warning('Automatic Colab check failed (%s); retrying', type(exc).__name__)
                with self._lock:
                    self._updated_at = time.monotonic()
                    self._snapshot.update(available=False, connectionState='recovery_delayed',
                                          reason=REASONS['recovery_delayed'])
            self._wake.wait(10)
            self._wake.clear()
