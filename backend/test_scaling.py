import hashlib
import io
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import Mock, patch
import mongomock
from flask import Flask, g
from functools import wraps
import test_workspace
from utils.workspace import Workspace, now
from utils.structured_grading import evaluate, validate_rubric, NeedsReview
from utils.result_validation import validate_result, ReviewRequired
from upload_api import create_upload_api


class RecoveryTests(unittest.TestCase):
    setUp = test_workspace.WorkspaceTests.setUp
    process = test_workspace.WorkspaceTests.process

    def test_bulk_submission_replays_without_duplicate_attempts(self):
        operation = {'_id': 'bulk-test', 'kind': 'evaluate', 'actor': 'admin',
            'owner': 'worker', 'sheet_ids': [self.sheet_id], 'submitted': 0, 'state': 'processing'}
        self.db.preparations.insert_one(dict(operation))
        self.service.process_preparation(operation)
        first = self.db.jobs.find_one({'_id': self.sheet_id})['attempt_id']
        # Replay from an old cursor, as after losing the progress acknowledgement.
        self.service.process_preparation(operation)
        self.assertEqual(self.db.jobs.count_documents({}), 1)
        self.assertEqual(self.db.jobs.find_one()['attempt_id'], first)
        self.assertEqual(self.db.preparations.find_one()['submitted'], 1)
        self.assertEqual(self.db.preparations.find_one()['state'], 'completed')

    def test_timeout_requeues_then_resumes_same_attempt(self):
        self.llm.evaluate_answer.side_effect = TimeoutError('model offline')
        row = self.process()
        self.assertEqual(row['job']['state'], 'queued')
        self.assertEqual(row['job']['stage'], 'retry_wait')
        self.assertIsNone(row['active'])
        self.assertIsNone(self.service.claim('worker'))
        self.db.jobs.update_one({'_id': self.sheet_id}, {'$set': {'next_run_at': now()}})
        self.llm.evaluate_answer.side_effect = None
        self.service.process(self.service.claim('worker'), self.pdf, self.llm, 'worker')
        self.assertEqual(self.db.jobs.find_one()['state'], 'completed')
        self.assertEqual(self.db.attempts.count_documents({}), 1)

    def test_retry_exhaustion_is_terminal(self):
        self.service.enqueue(self.sheet_id, 'admin')
        self.db.jobs.update_one({'_id': self.sheet_id}, {'$set': {'retry_count': 5}})
        self.llm.evaluate_answer.side_effect = TimeoutError('offline')
        self.service.process(self.service.claim('worker'), self.pdf, self.llm, 'worker')
        self.assertEqual(self.db.jobs.find_one()['state'], 'error')

    def test_old_worker_cannot_publish_after_generation_changes(self):
        self.service.enqueue(self.sheet_id, 'admin')
        job = self.service.claim('worker')
        original = self.db.attempts.update_one
        def takeover(query, change, **kwargs):
            if change.get('$set', {}).get('status') == 'completed':
                self.db.sheets.update_one({'_id': self.sheet_id}, {'$set': {'execution.token': 'new-owner-generation'}})
            return original(query, change, **kwargs)
        with patch.object(self.db.attempts, 'update_one', side_effect=takeover):
            with self.assertRaises(InterruptedError):
                self.service.process(job, self.pdf, self.llm, 'worker')
        self.assertIsNone(self.db.sheets.find_one()['active_attempt'])

    def test_cancel_during_final_save_prevents_activation(self):
        self.service.enqueue(self.sheet_id, 'admin')
        job = self.service.claim('worker')
        original = self.db.attempts.update_one
        def cancel(query, change, **kwargs):
            if change.get('$set', {}).get('status') == 'completed':
                self.db.sheets.update_one({'_id': self.sheet_id}, {'$set': {'execution.cancel_requested': True}})
                self.db.jobs.update_one({'_id': self.sheet_id}, {'$set': {'cancel_requested': True}})
            return original(query, change, **kwargs)
        with patch.object(self.db.attempts, 'update_one', side_effect=cancel):
            with self.assertRaises(InterruptedError):
                self.service.process(job, self.pdf, self.llm, 'worker')
        self.service.recover_interrupted('replacement')
        self.assertIsNone(self.db.sheets.find_one()['active_attempt'])
        self.assertEqual(self.db.jobs.find_one()['state'], 'cancelled')

    def test_changed_question_paper_is_rejected_before_grading(self):
        paper = Path(self.temp.name) / 'FS3401_MSE/question_paper.pdf'
        paper.write_bytes(b'original')
        self.service.prepare(self.temp.name, 'exam-1', 'mst', 100, 'admin')
        paper.write_bytes(b'changed')
        self.assertEqual(self.process()['job']['state'], 'error')
        self.llm.evaluate_answer.assert_not_called()

    def test_shared_key_is_reused_and_deleting_one_sheet_preserves_other_cache(self):
        (Path(self.temp.name) / 'FS3401_MSE/102.pdf').write_bytes(b'second')
        ids = self.service.prepare(self.temp.name, 'exam-1', 'mst', 100, 'admin')
        for sid in ids:
            self.service.enqueue(sid, 'admin')
            self.service.process(self.service.claim('worker'), self.pdf, self.llm, 'worker')
        key_reads = [c for c in self.pdf.extract_text_from_pdf.call_args_list if c.args[0].endswith('model_answer.pdf')]
        self.assertEqual(len(key_reads), 1)
        self.service.manage([ids[0]], 'sheet', 'admin')
        self.assertGreater(self.db.workspace_cache.count_documents({'sheet_ids': ids[1]}), 0)

    def test_snapshot_query_count_does_not_grow_with_sheet_count(self):
        template = self.db.sheets.find_one()
        self.db.sheets.insert_many([{**template, '_id': str(i)} for i in range(1000)])
        with patch.object(self.db.attempts, 'find', wraps=self.db.attempts.find) as attempts, patch.object(self.db.jobs, 'find', wraps=self.db.jobs.find) as jobs:
            rows = self.service.snapshot(limit=50, summaries=True)
        self.assertEqual(len(rows), 50)
        self.assertEqual(attempts.call_count, 1)
        self.assertEqual(jobs.call_count, 1)

    def test_render_only_uncached_pages(self):
        from utils.pdf_processor import PDFProcessor
        pdf = PDFProcessor()
        self.service.enqueue(self.sheet_id, 'admin')
        with patch.object(pdf, 'extract_text_from_pdf', side_effect=ValueError('scanned')), patch.object(pdf, 'page_count', return_value=2), patch.object(pdf, 'render_page', side_effect=lambda *args: Mock()) as render, patch.object(pdf, 'extract_text_from_images_via_gemini', side_effect=['key page one', TimeoutError('offline')]):
            self.service.process(self.service.claim('worker'), pdf, self.llm, 'worker')
            self.assertEqual(render.call_count, 2)
        self.db.jobs.update_one({'_id': self.sheet_id}, {'$set': {'next_run_at': now()}})
        with patch.object(pdf, 'extract_text_from_pdf', side_effect=ValueError('scanned')), patch.object(pdf, 'page_count', return_value=2), patch.object(pdf, 'render_page', side_effect=lambda *args: Mock()) as render, patch.object(pdf, 'extract_text_from_images_via_gemini', return_value='complete page'):
            self.service.process(self.service.claim('worker'), pdf, self.llm, 'worker')
            self.assertEqual(render.call_count, 3)

    def test_clearing_cache_forces_fresh_work_but_keeps_marks(self):
        self.process()
        self.service.manage([self.sheet_id], 'cache', 'admin')
        self.pdf.extract_text_from_pdf.reset_mock()
        self.process(force=True)
        self.assertEqual(self.pdf.extract_text_from_pdf.call_count, 2)
        self.assertIsNotNone(self.service.snapshot()[0]['active'])

    def test_page_bounds_and_history_are_not_in_summary(self):
        self.process()
        data = self.service.page({}, page=1, size=1, results_only=True)
        self.assertEqual(data['total'], 1)
        self.assertEqual(data['counts']['review'], 1)
        self.assertEqual(data['sheets'][0]['attempts'], [])
        self.assertNotIn('feedback', data['sheets'][0]['active'])
        self.assertEqual(self.service.page({}, page=2, size=1)['sheets'], [])

    def test_preparation_survives_coordinator_replacement(self):
        self.db.preparations.insert_one({'_id': 'prepare', 'state': 'processing', 'owner': 'dead',
            'directory': self.temp.name, 'exam_id': 'exam-2', 'exam_type': 'mst', 'max_marks': 100, 'actor': 'admin', 'created_at': now()})
        self.service.recover_interrupted('replacement')
        job = self.service.claim_preparation('replacement')
        self.service.process_preparation(job)
        self.assertEqual(self.db.preparations.find_one()['state'], 'completed')
        self.assertEqual(self.db.sheets.count_documents({'exam_id': 'exam-2'}), 1)


class StructuredGradingTests(unittest.TestCase):
    def test_parallel_questions_preserve_scores_and_order(self):
        import threading
        from types import SimpleNamespace
        barrier = threading.Barrier(2)
        rubric = {'questions': [
            {'question_id': str(i), 'max_marks': 5, 'source_quote': f'Q{i} 5 marks', 'answer': f'Answer{i}'}
            for i in (1, 2)], 'choice_groups': []}
        def respond(service, prompt):
            if prompt.startswith('Extract'):
                return rubric
            if prompt.startswith('Assign'):
                return {'segments': [{'question_id': '1', 'text': 'one '}, {'question_id': '2', 'text': 'two'}]}
            identifier = prompt.split()[3]
            if service.question_workers == 2:
                barrier.wait(timeout=5)
            marks = int(identifier)
            return {'marks_awarded': marks, 'strengths': [], 'missing_points': [], 'feedback': 'Checked',
                'question_scores': [{'question_id': identifier, 'max_marks': 5, 'marks_awarded': marks, 'feedback': 'Checked'}]}
        with patch('utils.structured_grading.json_call', side_effect=respond):
            sequential = evaluate(SimpleNamespace(question_workers=1), 'one two', 'Q1 5 marks Answer1 Q2 5 marks Answer2', 10)
            concurrent = evaluate(SimpleNamespace(question_workers=2), 'one two', 'Q1 5 marks Answer1 Q2 5 marks Answer2', 10)
        self.assertEqual(concurrent, sequential)
        self.assertEqual([q['question_id'] for q in concurrent['question_scores']], ['1', '2'])

    def test_unknown_question_is_rejected_by_rubric(self):
        result = {'marks_awarded': 5, 'strengths': [], 'missing_points': [], 'feedback': 'ok',
            'question_scores': [{'question_id': 'invented', 'max_marks': 10, 'marks_awarded': 5}]}
        with self.assertRaises(ReviewRequired):
            validate_result(result, 10, True, rubric=[{'question_id': '1', 'max_marks': 10}])

    def test_full_question_flow_preserves_zero_and_checks_source(self):
        rubric = {'questions': [{'question_id': '1', 'max_marks': 10, 'source_quote': 'Q1 10 marks', 'answer': 'Correct answer'}], 'choice_groups': []}
        score = {'marks_awarded': 0, 'strengths': [], 'missing_points': [], 'feedback': 'Incorrect',
            'question_scores': [{'question_id': '1', 'max_marks': 10, 'marks_awarded': 0, 'feedback': 'Incorrect'}]}
        with patch('utils.structured_grading.json_call', side_effect=[rubric, {'segments': [{'question_id': '1', 'text': 'Q1 wrong answer'}]}, score]):
            result = evaluate(Mock(), 'Q1 wrong answer', 'Q1 10 marks\nCorrect answer', 10)
        self.assertEqual(result['marks_awarded'], 0)
        self.assertEqual(result['status'], 'completed')

    def test_dropped_answer_text_requires_review(self):
        rubric = {'questions': [{'question_id': '1', 'max_marks': 10, 'source_quote': 'Q1 10 marks', 'answer': 'Correct'}], 'choice_groups': []}
        with patch('utils.structured_grading.json_call', side_effect=[rubric, {'segments': [{'question_id': '1', 'text': 'partial'}]}]):
            with self.assertRaisesRegex(NeedsReview, 'full source'):
                evaluate(Mock(), 'whole student answer', 'Q1 10 marks Correct', 10)

    def test_optional_rules_cannot_invent_best_selection(self):
        source = 'Q1 5 marks A. Q2 5 marks B. Attempt any one.'
        rubric = {'questions': [{'question_id': '1', 'max_marks': 5, 'source_quote': 'Q1 5 marks', 'answer': 'A.'},
            {'question_id': '2', 'max_marks': 5, 'source_quote': 'Q2 5 marks', 'answer': 'B.'}],
            'choice_groups': [{'question_ids': ['1', '2'], 'count': 1, 'selection': 'best', 'source_quote': 'Attempt any one.'}]}
        with self.assertRaisesRegex(NeedsReview, 'highest'):
            validate_rubric(rubric, source, 5)

    def test_optional_best_rule_selects_correct_scores(self):
        source = 'Q1 5 marks A. Q2 5 marks B. Count the best one.'
        rubric = {'questions': [{'question_id': '1', 'max_marks': 5, 'source_quote': 'Q1 5 marks', 'answer': 'A.'},
            {'question_id': '2', 'max_marks': 5, 'source_quote': 'Q2 5 marks', 'answer': 'B.'}],
            'choice_groups': [{'question_ids': ['1', '2'], 'count': 1, 'selection': 'best', 'source_quote': 'Count the best one.'}]}
        def result(qid, marks):
            return {'marks_awarded': marks, 'strengths': ['Good point'], 'missing_points': [], 'feedback': 'Reviewed',
                'question_scores': [{'question_id': qid, 'max_marks': 5, 'marks_awarded': marks, 'feedback': 'Reviewed'}]}
        with patch('utils.structured_grading.json_call', side_effect=[rubric,
            {'segments': [{'question_id': '1', 'text': 'one '}, {'question_id': '2', 'text': 'two'}]}, result('1', 2), result('2', 4)]):
            value = evaluate(Mock(), 'one two', source, 5)
        self.assertEqual(value['marks_awarded'], 4)
        self.assertEqual(value['question_scores'][0]['question_id'], '2')
        self.assertEqual(value['strengths'], ['2: Good point'])

    def test_actual_answer_cannot_be_discarded_as_a_header(self):
        rubric = {'questions': [{'question_id': '1', 'max_marks': 10, 'source_quote': 'Q1 10 marks', 'answer': 'Correct'}], 'choice_groups': []}
        with patch('utils.structured_grading.json_call', side_effect=[rubric, {'segments': [{'question_id': None, 'text': 'Actual answer'}]}]):
            with self.assertRaises(NeedsReview):
                evaluate(Mock(), 'Actual answer', 'Q1 10 marks Correct', 10)


class ResumableUploadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = mongomock.MongoClient().db
        patcher = patch('upload_api.db_connection.get_db', return_value=self.db)
        patcher.start(); self.addCleanup(patcher.stop)
        def auth(fn):
            @wraps(fn)
            def wrapped(*args, **kwargs):
                g.user_email = 'admin'; g.user = {'role': 'admin'}
                return fn(*args, **kwargs)
            return wrapped
        app = Flask(__name__)
        app.register_blueprint(create_upload_api(auth, self.temp.name))
        self.client = app.test_client()
        self.sid = 'a' * 32
        self.base = '/api/workspace/uploads'

    def test_resume_checksum_and_idempotent_finalize(self):
        manifest = {'session_id': self.sid, 'files': [{'path': 'FS3401/101.pdf', 'size': 3}]}
        self.assertEqual(self.client.post(self.base, json=manifest).status_code, 200)
        self.assertEqual(self.client.post(f'{self.base}/{self.sid}/complete').status_code, 400)
        headers = {'X-Content-SHA256': hashlib.sha256(b'pdf').hexdigest()}
        for _ in range(2):
            self.assertEqual(self.client.put(f'{self.base}/{self.sid}/0', data=b'pdf', headers=headers).status_code, 200)
            self.assertEqual(self.client.post(self.base, json=manifest).status_code, 200)
        for _ in range(2):
            self.assertEqual(self.client.post(f'{self.base}/{self.sid}/complete').status_code, 200)
        self.assertEqual(self.db.upload_parts.count_documents({}), 1)
        self.assertEqual(self.db.uploads.count_documents({}), 1)

    def test_partial_file_never_becomes_accepted(self):
        self.client.post(self.base, json={'session_id': self.sid, 'files': [{'path': 'FS3401/101.pdf', 'size': 3}]})
        response = self.client.put(f'{self.base}/{self.sid}/0', data=b'p', headers={'X-Content-SHA256': hashlib.sha256(b'pdf').hexdigest()})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.db.upload_parts.count_documents({}), 0)
        self.assertFalse((Path(self.temp.name) / self.sid / 'FS3401/101.pdf').exists())

    def test_manifest_accepts_thousands_without_multipart(self):
        response = self.client.post(self.base, json={'session_id': self.sid,
            'files': [{'path': f'FS3401/{i}.pdf', 'size': 3} for i in range(1200)]})
        self.assertEqual(response.status_code, 200)
