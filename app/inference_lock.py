"""Serialize local Ollama execution across the policy and vision processes."""
import os
from pathlib import Path
import threading
import time


class InferenceLock:
    def __init__(self, path=None):
        self.path = Path(path) if path else None
        self.thread = threading.Lock()
        self.file = None

    def acquire(self, timeout=-1):
        deadline = None if timeout < 0 else time.monotonic()+timeout
        if not self.thread.acquire(timeout=timeout):
            return False
        if self.path is None:
            return True
        handle = None
        try:
            handle = open(self.path, 'r+b')
            while True:
                try:
                    if os.name == 'nt':
                        import msvcrt
                        handle.seek(0); msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    self.file = handle
                    return True
                except (BlockingIOError, PermissionError):
                    if deadline is not None and time.monotonic() >= deadline:
                        handle.close(); self.thread.release()
                        return False
                    time.sleep(.025)
        except Exception:
            if handle is not None:
                handle.close()
            self.thread.release()
            raise

    def release(self):
        try:
            if self.file is not None:
                try:
                    if os.name == 'nt':
                        import msvcrt
                        self.file.seek(0); msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(self.file.fileno(), fcntl.LOCK_UN)
                finally:
                    self.file.close(); self.file = None
        finally:
            self.thread.release()

    def locked(self):
        return self.thread.locked()
