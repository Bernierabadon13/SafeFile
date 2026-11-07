"""AppContext: shared services for the screens (repository, engine, background tasks, Mini Cloud)."""
from __future__ import annotations

import os
import threading
import time
import logging

from PySide6.QtCore import QObject, Qt, QThread, Signal

from safepoint.engine.errors import Cancelled, SafeFileError
from safepoint.engine.minicloud import MiniCloudServer
from safepoint.engine.stores import cloud_store_from_settings
from safepoint.ui import dialogs


class _Worker(QThread):
    progress = Signal(str, object, object, str)
    succeeded = Signal(object)
    failed = Signal(str, bool)

    def __init__(self, fn):
        super().__init__()
        self._fn = fn
        self.cancel_event = threading.Event()
        self._last = 0.0

    def _emit(self, stage, done=0, total=0, detail=""):
        now = time.monotonic()
        if now - self._last >= 0.1 or (total and done >= total):
            self._last = now
            self.progress.emit(str(stage), done, total, str(detail))

    def run(self):
        try:
            result = self._fn(self._emit, self.cancel_event)
        except Cancelled:
            self.failed.emit("Cancelled", True)
            return
        except Exception as err:  # reported to the user; details go to the console
            if not isinstance(err, SafeFileError):
                logging.getLogger("safefile").exception("Background task failed")
            self.failed.emit(str(err) or type(err).__name__, False)
            return
        self.succeeded.emit(result)


class AppContext(QObject):
    data_changed = Signal()
    activity = Signal(str)

    def __init__(self, repo, engine):
        super().__init__()
        self.repo = repo
        self.engine = engine
        self.worker = None
        self._run = None
        self.cloud_server = None
        self.cloud_status = "Off"
        self.pending_snapshot = None
        self.pending_project = None
        self.apply_cloud_settings()

    # ------------------------------------------------------------ tasks
    def busy(self) -> bool:
        return self.worker is not None and self.worker.isRunning()

    def run_task(self, parent, heading, fn, on_success=None, on_failure=None, dialog=True, status=None) -> bool:
        """Run `fn(progress, cancel_event)` on a worker thread. Callbacks run on the GUI thread."""
        if self.busy():
            if dialog:
                dialogs.show_message(parent, "Please wait", "Another task is still running. Try again when it finishes.")
            return False
        worker = _Worker(fn)
        self.worker = worker
        progress_dialog = None
        if dialog:
            progress_dialog = dialogs.ProgressDialog(parent, heading, worker.cancel_event)
            worker.progress.connect(progress_dialog.update_progress, Qt.ConnectionType.QueuedConnection)
        self._run = {"dialog": progress_dialog, "ok": on_success, "fail": on_failure, "parent": parent,
                     "show": dialog}
        # Bound QObject slots + QueuedConnection guarantee the callbacks run on the GUI thread.
        worker.succeeded.connect(self._on_succeeded, Qt.ConnectionType.QueuedConnection)
        worker.failed.connect(self._on_failed, Qt.ConnectionType.QueuedConnection)
        if progress_dialog is not None:
            progress_dialog.open()
        self.activity.emit(status or heading)
        worker.start()
        return True

    def _release(self):
        run, worker = self._run, self.worker
        self._run = None
        if worker is not None:
            worker.wait()
        self.worker = None
        if run and run["dialog"] is not None:
            run["dialog"].finish()
        self.activity.emit("Idle")
        return run

    def _on_succeeded(self, result):
        run = self._release()
        self.data_changed.emit()
        if run and run["ok"]:
            run["ok"](result)

    def _on_failed(self, message, cancelled):
        run = self._release()
        self.data_changed.emit()
        if not run:
            return
        if run["fail"]:
            run["fail"](message, cancelled)
        elif run["show"]:
            if cancelled:
                dialogs.show_message(run["parent"], "Cancelled", "The task was cancelled. Nothing was marked as verified.")
            else:
                dialogs.show_message(run["parent"], "Something went wrong", message, "error")

    # ------------------------------------------------------------ high-level actions
    def backup_project(self, project, parent=None, kind="Manual"):
        pid = int(project.id)
        self.run_task(
            parent, f"Backing up {project.name}",
            lambda progress, cancel: self.engine.backup(pid, kind, progress, cancel),
            on_success=lambda r: dialogs.show_backup_result(parent, project.name, r))

    def verify_snapshot(self, snapshot_id, parent=None, on_done=None):
        def done(v):
            dialogs.show_verify_result(parent, snapshot_id, v)
            if on_done:
                on_done()
        self.run_task(parent, f"Verifying {snapshot_id}",
                      lambda progress, cancel: self.engine.verify(snapshot_id, progress, cancel), on_success=done)

    def restore(self, snapshot_id, paths, destination, conflict, parent=None):
        self.run_task(
            parent, "Restoring files",
            lambda progress, cancel: self.engine.restore(snapshot_id, paths, destination, conflict, progress, cancel),
            on_success=lambda r: dialogs.show_restore_result(parent, r))

    def quick_save(self, paths, destination, parent=None, note="", dialog=True, on_done=None) -> bool:
        """Save each path as a new version in its own history. One failing path does not stop the others."""
        paths = [os.path.normpath(p) for p in paths]

        def work(progress, cancel):
            results = []
            for i, path in enumerate(paths):
                name = os.path.basename(path.rstrip("\\/")) or path
                progress(f"Saving {name}", i, len(paths), path)
                try:
                    results.append((path, self.engine.quick_save(path, destination, note, progress, cancel), None))
                except Cancelled:
                    raise
                except SafeFileError as err:
                    results.append((path, None, str(err)))
            return results

        self.repo.save_settings({"quick_destination": destination})
        done = on_done or (lambda results: dialogs.show_quick_results(parent, results))
        return self.run_task(parent, "Saving versions", work, on_success=done, dialog=dialog,
                             status=f"Saving {len(paths)} item(s)…")

    def remove_project(self, project, parent=None, on_done=None):
        def done(_r):
            if on_done:
                on_done()
        self.run_task(parent, f"Removing {project.name}",
                      lambda progress, cancel: self.engine.remove_project(int(project.id), progress), on_success=done)

    # ------------------------------------------------------------ schedule
    def check_schedule(self):
        """Called by a timer: starts at most one due automatic backup while the app is open."""
        if self.busy():
            return
        for project in self.repo.due_projects():
            pid = int(project.id)
            self.run_task(None, f"Backing up {project.name}",
                          lambda progress, cancel, pid=pid: self.engine.backup(pid, "Scheduled", progress, cancel),
                          dialog=False, status=f"Backing up {project.name}…")
            break

    # ------------------------------------------------------------ Mini Cloud (built-in server)
    def apply_cloud_settings(self):
        self.stop_cloud()
        s = self.repo.get_settings()
        if s["cloud_mode"] == "embedded":
            try:
                server = MiniCloudServer(s["cloud_embedded_root"], s["cloud_embedded_token"], "127.0.0.1",
                                         int(s["cloud_embedded_port"]))
                server.start()
                self.cloud_server = server
                self.cloud_status = f"Running on this PC ({server.url})"
            except SafeFileError as err:
                self.cloud_status = f"Not running: {err}"
        elif s["cloud_mode"] == "remote":
            self.cloud_status = "Using another device"
        else:
            self.cloud_status = "Off"

    def stop_cloud(self):
        if self.cloud_server:
            self.cloud_server.stop()
            self.cloud_server = None

    def test_cloud(self, values=None):
        settings = self.repo.get_settings()
        settings.update(values or {})
        try:
            store = cloud_store_from_settings(settings)
            store.check()
        except SafeFileError as err:
            return False, str(err)
        free = store.free_bytes()
        from safepoint.util import human_size
        extra = f" {human_size(free)} free on the server." if free else ""
        return True, f"Connected to the Mini Cloud at {store.url}.{extra}"

    def shutdown(self):
        if self.worker is not None and self.worker.isRunning():
            self.worker.cancel_event.set()
            self.worker.wait(10000)
        self.stop_cloud()
