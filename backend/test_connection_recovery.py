import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock, patch

from config import Config, positive_int
from utils.db_connection import DatabaseConnection


class ConnectionRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.connection = object.__new__(DatabaseConnection)
        self.connection._client = None
        self.connection._db = None
        self.connection._connected = False
        self.connection._create_indexes = Mock()

    def test_concurrent_startup_creates_one_client(self):
        client = Mock()
        database = Mock()
        client.__getitem__ = Mock(return_value=database)
        with patch('utils.db_connection.MongoClient', return_value=client) as create:
            with ThreadPoolExecutor(max_workers=8) as pool:
                databases = list(pool.map(lambda _: self.connection.get_db(), range(20)))
        self.assertTrue(all(db is database for db in databases))
        create.assert_called_once()
        self.assertEqual(create.call_args.kwargs['socketTimeoutMS'], Config.MONGO_SOCKET_TIMEOUT_MS)

    def test_failed_connection_is_closed_and_next_request_can_recover(self):
        failed, recovered = Mock(), Mock()
        failed.admin.command.side_effect = RuntimeError('offline')
        database = Mock()
        recovered.__getitem__ = Mock(return_value=database)
        with patch('utils.db_connection.MongoClient', side_effect=[failed, recovered]):
            with self.assertRaisesRegex(RuntimeError, 'unavailable'):
                self.connection.get_db()
            failed.close.assert_called_once()
            self.assertIsNone(self.connection._client)
            self.assertFalse(self.connection._connected)
            self.assertIs(self.connection.get_db(), database)

    def test_close_allows_a_fresh_connection(self):
        first, second = Mock(), Mock()
        first.__getitem__ = Mock(return_value=Mock())
        second.__getitem__ = Mock(return_value=Mock())
        with patch('utils.db_connection.MongoClient', side_effect=[first, second]) as create:
            self.connection.get_db()
            self.connection.close()
            self.assertFalse(self.connection._connected)
            self.connection.get_db()
        self.assertEqual(create.call_count, 2)

    def test_invalid_configuration_names_the_setting(self):
        for value in ('0', '-1', 'abc', ''):
            with self.subTest(value=value), patch.dict(os.environ, {'TEST_TIMEOUT': value}):
                with self.assertRaisesRegex(ValueError, 'TEST_TIMEOUT must be a positive integer'):
                    positive_int('TEST_TIMEOUT', 10)
        with patch.dict(os.environ, {'TEST_TIMEOUT': '27'}):
            self.assertEqual(positive_int('TEST_TIMEOUT', 10), 27)
