"""Workspace worker, started by app.py or separately alongside Gunicorn."""
import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from datetime import timedelta
from config import Config
from utils.runtime_settings import parallelism, MAX_PARALLELISM
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from utils.db_connection import db_connection
from utils.workspace import Workspace, now
from utils.pdf_processor import PDFProcessor
from utils.gemini_service import GeminiService


def run(stop_event=None):
    logging.basicConfig(level=logging.INFO)
    db = db_connection.get_db()
    workspace = Workspace(db)
    workspace.indexes()
    owner = uuid.uuid4().hex
    shutdown = stop_event if stop_event is not None else threading.Event()
    stopped = threading.Event()

    heartbeat_stopped = threading.Event()

    def heartbeat():
        while not heartbeat_stopped.wait(10):
            try:
                result = db.worker_leases.update_one({'_id': 'inference', 'owner': owner, 'expires': {'$gt': now()}},
                    {'$set': {'expires': now() + timedelta(seconds=90)}})
                workspace.renew(owner)
                if not result.matched_count:
                    stopped.set()
            except Exception:
                stopped.set()

    try:
        db.worker_leases.insert_one({'_id': 'inference', 'owner': '', 'expires': now()})
    except DuplicateKeyError:
        pass
    while not stopped.is_set() and not shutdown.is_set():
        lease = db.worker_leases.find_one_and_update({'_id': 'inference', 'expires': {'$lte': now()}},
            {'$set': {'owner': owner, 'expires': now() + timedelta(seconds=90)}}, return_document=ReturnDocument.AFTER)
        if lease:
            break
        stopped.wait(5)
    if stopped.is_set() or shutdown.is_set():
        db.worker_leases.update_one({'_id': 'inference', 'owner': owner}, {'$set': {'owner': '', 'expires': now()}})
        return
    thread = threading.Thread(target=heartbeat, daemon=True)
    thread.start()
    try:
        workspace.recover_interrupted(owner)
        capacity = parallelism(db)
        logging.getLogger(__name__).info('Evaluation worker ready: up to %s sheets in parallel', capacity)
        db.worker_leases.update_one({'_id': 'inference', 'owner': owner},
            {'$set': {'capacity': capacity}})
        # One coordinator owns recovery; its bounded pool shares that lease.
        # Claim only when a pool slot is free, so queued jobs remain cancellable.
        with ThreadPoolExecutor(max_workers=MAX_PARALLELISM, thread_name_prefix='evaluation') as pool:
            pending = set()
            try:
                while not stopped.is_set() and not shutdown.is_set():
                    capacity = parallelism(db)
                    db.worker_leases.update_one({'_id': 'inference', 'owner': owner},
                        {'$set': {'capacity': capacity}})
                    while len(pending) < capacity and not stopped.is_set() and not shutdown.is_set():
                        preparation = workspace.claim_preparation(owner)
                        if isinstance(preparation, dict):
                            pending.add(pool.submit(workspace.process_preparation, preparation))
                            continue
                        job = workspace.claim(owner)
                        if not job:
                            break
                        pending.add(pool.submit(workspace.process, job, PDFProcessor(), GeminiService(), owner))
                    if pending:
                        finished, pending = wait(pending, timeout=0.5, return_when=FIRST_COMPLETED)
                        for future in finished:
                            future.result()
                    else:
                        stopped.wait(2)
            finally:
                # Keep heartbeating while already-started jobs finish on shutdown.
                # Unexpected failures stop new claims and are recovered on restart.
                stopped.set()

    finally:
        stopped.set()
        heartbeat_stopped.set()
        thread.join(timeout=2)
        db.worker_leases.update_one({'_id': 'inference', 'owner': owner}, {'$set': {'owner': '', 'expires': now()}})


class EmbeddedWorker:
    """Own the worker lifetime without blocking Flask's request handling."""

    def __init__(self):
        self.stopped = threading.Event()
        self.thread = threading.Thread(target=self._run, name='evaluation-worker', daemon=True)

    def _run(self):
        supervise(self.stopped)

    def start(self):
        self.thread.start()
        logging.getLogger(__name__).info('Evaluation worker started automatically')

    def stop(self):
        self.stopped.set()
        self.thread.join(timeout=5)
        if self.thread.is_alive():
            logging.getLogger(__name__).warning(
                'Worker still finishing an operation; interrupted work will be recovered after lease expiry')
        return not self.thread.is_alive()


def supervise(stopped):
    while not stopped.is_set():
        try:
            run(stopped)
        except Exception:
            logging.getLogger(__name__).exception('Worker interrupted; automatically recovering in %s seconds', Config.WORKER_RECOVERY_SECONDS)
        stopped.wait(Config.WORKER_RECOVERY_SECONDS)


if __name__ == '__main__':
    import signal
    shutdown = threading.Event()
    signal.signal(signal.SIGTERM, lambda *args: shutdown.set())
    signal.signal(signal.SIGINT, lambda *args: shutdown.set())
    supervise(shutdown)
