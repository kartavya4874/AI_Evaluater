"""A shared bounded lease prevents nested/web workers from overloading vLLM."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import time
import threading
import logging
import uuid
from utils.runtime_settings import parallelism, MAX_PARALLELISM
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from utils.db_connection import db_connection


@contextmanager
def inference_slot(timeout):
    collection = db_connection.get_collection('inference_slots')
    owner = uuid.uuid4().hex
    deadline = time.monotonic() + timeout
    slot_ids = ['vllm'] + [f'vllm:{i}' for i in range(1, MAX_PARALLELISM)]
    for slot_id in slot_ids:
        try:
            collection.insert_one({'_id': slot_id, 'owner': '', 'expires': datetime.now(timezone.utc)})
        except DuplicateKeyError:
            pass
    acquired = None
    while acquired is None:
        limit = parallelism(collection.database)
        # A reduced limit drains requests in retired slots before admitting more.
        retiring = collection.count_documents({'_id': {'$in': slot_ids[limit:]},
            'owner': {'$ne': ''}, 'expires': {'$gt': datetime.now(timezone.utc)}})
        for slot_id in ([] if retiring else slot_ids[:limit]):
            now = datetime.now(timezone.utc)
            slot = collection.find_one_and_update({'_id': slot_id, 'expires': {'$lte': now}},
                {'$set': {'owner': owner, 'expires': now + timedelta(seconds=timeout + 60)}},
                return_document=ReturnDocument.AFTER)
            if slot:
                acquired = slot_id
                break
        if acquired is not None:
            break
        if time.monotonic() >= deadline:
            raise TimeoutError('Inference queue is busy; retry this attempt later')
        time.sleep(0.5)
    renewal_stop = threading.Event()
    def renew():
        while not renewal_stop.wait(20):
            try:
                changed = collection.update_one({'_id': acquired, 'owner': owner,
                    'expires': {'$gt': datetime.now(timezone.utc)}}, {'$set': {
                    'expires': datetime.now(timezone.utc) + timedelta(seconds=timeout + 60)}})
                if not changed.matched_count:
                    return
            except Exception:
                logging.getLogger(__name__).exception('Inference lease renewal failed')
                return
    renewal = threading.Thread(target=renew, daemon=True)
    renewal.start()
    try:
        yield
    finally:
        renewal_stop.set()
        renewal.join(timeout=1)
        collection.update_one({'_id': acquired, 'owner': owner},
            {'$set': {'owner': '', 'expires': datetime.now(timezone.utc)}})
