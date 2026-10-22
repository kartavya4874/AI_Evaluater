import threading
import unittest
from unittest.mock import MagicMock, patch

from worker import EmbeddedWorker, run


class WorkerLifecycleTests(unittest.TestCase):
    def test_pool_runs_three_jobs_and_queues_fourth_until_capacity_available(self):
        import mongomock
        from worker import Config
        db = mongomock.MongoClient().db
        db.settings.insert_one({'_id': 'evaluation', 'parallelism': 3})
        stopped = threading.Event()
        three_running = threading.Event()
        release = threading.Event()
        fourth_finished = threading.Event()
        lock = threading.Lock()
        started = []
        errors = []
        jobs = iter([{'_id': str(i)} for i in range(4)])
        service = MagicMock()
        service.claim.side_effect = lambda owner: next(jobs, None)
        def process(job, pdf, llm, owner):
            with lock:
                started.append(job['_id'])
                if len(started) == 3:
                    three_running.set()
            if job['_id'] == '3':
                fourth_finished.set()
                stopped.set()
            elif not release.wait(5):
                raise TimeoutError('test did not release jobs')
        service.process.side_effect = process
        def execute():
            try:
                run(stopped)
            except Exception as error:
                errors.append(error)
        with patch('worker.db_connection.get_db', return_value=db), patch('worker.Workspace', return_value=service), patch.object(Config, 'BATCH_PROCESSING_MAX_WORKERS', 3):
            thread = threading.Thread(target=execute)
            thread.start()
            try:
                self.assertTrue(three_running.wait(3))
                self.assertEqual(service.claim.call_count, 3)
                self.assertFalse(fourth_finished.is_set())
                release.set()
                self.assertTrue(fourth_finished.wait(3))
            finally:
                release.set()
                stopped.set()
                thread.join(5)
            self.assertFalse(thread.is_alive())
            self.assertEqual(errors, [])
            self.assertEqual(len(started), 4)
            service.recover_interrupted.assert_called_once()
            self.assertEqual(db.worker_leases.find_one({'_id': 'inference'})['owner'], '')

    def test_saved_limit_increases_running_pool_without_restart(self):
        import mongomock
        db = mongomock.MongoClient().db
        db.settings.insert_one({'_id': 'evaluation', 'parallelism': 1})
        stopped = threading.Event()
        first = threading.Event()
        five = threading.Event()
        release = threading.Event()
        lock = threading.Lock()
        started = []
        jobs = iter([{'_id': str(i)} for i in range(5)])
        service = MagicMock()
        service.claim.side_effect = lambda owner: next(jobs, None)
        def process(job, *args):
            with lock:
                started.append(job['_id'])
                first.set()
                if len(started) == 5:
                    five.set()
            release.wait(5)
        service.process.side_effect = process
        with patch('worker.db_connection.get_db', return_value=db), patch('worker.Workspace', return_value=service):
            thread = threading.Thread(target=run, args=(stopped,))
            thread.start()
            try:
                self.assertTrue(first.wait(2))
                self.assertEqual(len(started), 1)
                db.settings.update_one({'_id': 'evaluation'}, {'$set': {'parallelism': 5}})
                self.assertTrue(five.wait(3))
                self.assertEqual(db.worker_leases.find_one({'_id': 'inference'})['capacity'], 5)
            finally:
                stopped.set(); release.set(); thread.join(5)
            self.assertFalse(thread.is_alive())

    def test_embedded_worker_runs_in_background_and_stops(self):
        entered = threading.Event()

        def process(stopped):
            entered.set()
            stopped.wait(3)

        with patch('worker.run', side_effect=process):
            worker = EmbeddedWorker()
            worker.start()
            try:
                self.assertTrue(entered.wait(2))
                self.assertTrue(worker.thread.is_alive())
            finally:
                self.assertTrue(worker.stop())
            self.assertTrue(worker.stopped.is_set())

    def test_worker_failure_is_logged(self):
        with patch('worker.run', side_effect=RuntimeError('database unavailable')):
            with self.assertLogs('worker', level='ERROR') as logs:
                worker = EmbeddedWorker()
                worker.start()
                worker.thread.join(timeout=2)
                self.assertTrue(worker.stop())
            self.assertIn('automatically recovering', logs.output[0])

    def test_stopped_worker_does_not_recover_or_claim_jobs(self):
        stopped = threading.Event()
        stopped.set()
        with patch('worker.db_connection.get_db', return_value=MagicMock()):
            with patch('worker.Workspace') as workspace:
                run(stopped)
                workspace.return_value.recover_interrupted.assert_not_called()
                workspace.return_value.claim.assert_not_called()

    def test_recovery_failure_releases_lease(self):
        db = MagicMock()
        with patch('worker.db_connection.get_db', return_value=db):
            with patch('worker.Workspace') as workspace:
                workspace.return_value.recover_interrupted.side_effect = RuntimeError('recovery failed')
                with self.assertRaisesRegex(RuntimeError, 'recovery failed'):
                    run()
        self.assertEqual(db.worker_leases.update_one.call_args.args[1]['$set']['owner'], '')


if __name__ == '__main__':
    unittest.main()
