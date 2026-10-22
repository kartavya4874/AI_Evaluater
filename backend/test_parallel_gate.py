import unittest
from unittest.mock import patch
import mongomock
from config import Config
from utils.inference_gate import inference_slot


class ParallelGateTests(unittest.TestCase):
    def test_global_limit_and_release_after_error(self):
        collection = mongomock.MongoClient().db.inference_slots
        collection.database.settings.insert_one({'_id': 'evaluation', 'parallelism': 3})
        with patch('utils.inference_gate.db_connection.get_collection', return_value=collection), patch.object(Config, 'VLLM_MAX_CONCURRENT_REQUESTS', 3):
            with inference_slot(1), inference_slot(1), inference_slot(1):
                self.assertEqual(collection.count_documents({'owner': {'$ne': ''}}), 3)
                with self.assertRaises(TimeoutError):
                    with inference_slot(0):
                        self.fail('Fourth request must wait')
            self.assertEqual(collection.count_documents({'owner': {'$ne': ''}}), 0)
            with self.assertRaises(ValueError):
                with inference_slot(1):
                    raise ValueError('failed request')
            with inference_slot(1):
                self.assertEqual(collection.count_documents({'owner': {'$ne': ''}}), 1)
            self.assertEqual(collection.count_documents({'owner': {'$ne': ''}}), 0)

    def test_lower_limit_drains_retired_slots_and_raise_applies_immediately(self):
        from contextlib import ExitStack
        collection = mongomock.MongoClient().db.inference_slots
        settings = collection.database.settings
        settings.insert_one({'_id': 'evaluation', 'parallelism': 2})
        with patch('utils.inference_gate.db_connection.get_collection', return_value=collection):
            first = ExitStack(); second = ExitStack()
            try:
                first.enter_context(inference_slot(1))
                second.enter_context(inference_slot(1))
                settings.update_one({'_id': 'evaluation'}, {'$set': {'parallelism': 1}})
                first.close()
                with self.assertRaises(TimeoutError):
                    with inference_slot(0):
                        self.fail('Retired slot must drain before new requests')
                second.close()
                with inference_slot(1):
                    with self.assertRaises(TimeoutError):
                        with inference_slot(0):
                            self.fail('Limit is one')
                    settings.update_one({'_id': 'evaluation'}, {'$set': {'parallelism': 5}})
                    with inference_slot(1), inference_slot(1), inference_slot(1), inference_slot(1):
                        self.assertEqual(collection.count_documents({'owner': {'$ne': ''}}), 5)
                        with self.assertRaises(TimeoutError):
                            with inference_slot(0):
                                self.fail('Sixth request is forbidden')
            finally:
                first.close(); second.close()
