import json
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock, patch
import requests
import test_workspace
from utils.gemini_service import GeminiService
from utils.structured_grading import NeedsReview
from utils.workspace import now


class CoursePreflightTests(unittest.TestCase):
    setUp = test_workspace.WorkspaceTests.setUp
    def process(self, force=False):
        self.service.enqueue(self.sheet_id, 'admin', force)
        self.service.process(self.service.claim('worker'), self.pdf, self.llm, 'worker')
        return self.service.snapshot({'_id': self.sheet_id})[0]

    def add_second_sheet(self):
        (Path(self.temp.name) / 'FS3401_MSE/102.pdf').write_bytes(b'second student')
        ids = self.service.prepare(self.temp.name, 'exam-1', 'mst', 100, 'admin')
        return next(identifier for identifier in ids if identifier != self.sheet_id)

    def test_marking_scheme_is_validated_before_any_student_ocr(self):
        order = []
        def extract(path):
            order.append('key' if path.endswith('model_answer.pdf') else 'student')
            return 'Extracted complete text'
        def preflight(*args):
            order.append('validate marks')
            self.assertEqual(order, ['key', 'validate marks'])
            return {'questions': []}
        self.pdf.extract_text_from_pdf.side_effect = extract
        self.llm.prepare_marking_scheme.side_effect = preflight
        self.assertEqual(self.process()['job']['state'], 'completed')
        self.assertEqual(order, ['key', 'validate marks', 'student'])

    def test_invalid_course_blocks_all_its_sheets_without_student_ocr_or_repeated_ai(self):
        second = self.add_second_sheet()
        self.llm.prepare_marking_scheme.side_effect = NeedsReview('No usable question allocations')
        self.assertEqual(self.process()['job']['state'], 'needs_review')
        self.service.enqueue(second, 'admin')
        self.service.process(self.service.claim('worker'), self.pdf, self.llm, 'worker')
        self.assertEqual(self.db.jobs.find_one({'_id': second})['state'], 'needs_review')
        self.llm.prepare_marking_scheme.assert_called_once()
        self.llm.evaluate_answer.assert_not_called()
        self.assertEqual(self.pdf.extract_text_from_pdf.call_count, 1)
        self.assertTrue(self.pdf.extract_text_from_pdf.call_args.args[0].endswith('model_answer.pdf'))

    def test_transient_preflight_failure_is_not_cached_as_an_invalid_scheme(self):
        second = self.add_second_sheet()
        self.llm.prepare_marking_scheme.side_effect = [requests.ConnectionError('AI offline'), {'questions': []}]
        self.assertEqual(self.process()['job']['state'], 'queued')
        self.db.course_runs.update_many({'state': 'retry'}, {'$set': {'next_run_at': now()}})
        self.service.enqueue(second, 'admin')
        self.service.process(self.service.claim('worker'), self.pdf, self.llm, 'worker')
        self.assertEqual(self.db.jobs.find_one({'_id': second})['state'], 'completed')
        self.assertEqual(self.db.workspace_cache.count_documents({'blocked': True}), 0)

    def test_admin_revision_rechecks_a_blocked_course(self):
        self.llm.prepare_marking_scheme.side_effect = [NeedsReview('Missing marks'), {'questions': []}]
        self.assertEqual(self.process()['job']['state'], 'needs_review')
        from utils.marking_schemes import scheme_id
        code = self.db.sheets.find_one({'_id': self.sheet_id})['course_code']
        self.db.marking_schemes.insert_one({'_id': scheme_id(code, 'mst'), 'revision': 'new-admin-revision'})
        self.assertEqual(self.process(force=True)['job']['state'], 'completed')
        self.assertEqual(self.llm.prepare_marking_scheme.call_count, 2)

    def test_parallel_sheets_wait_for_one_course_preparation(self):
        second = self.add_second_sheet()
        entered, release = threading.Event(), threading.Event()
        def preflight(*args):
            entered.set()
            self.assertTrue(release.wait(5))
            return {'questions': []}
        first_provider = self.llm
        first_provider.prepare_marking_scheme.side_effect = preflight
        second_provider = Mock()
        second_provider.prepare_marking_scheme.return_value = {'questions': []}
        second_provider.evaluate_answer.return_value = test_workspace.grade()
        self.service.enqueue(self.sheet_id, 'admin')
        first_job = self.service.claim('worker')
        self.service.enqueue(second, 'admin')
        self.assertIsNone(self.service.claim('worker'))
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(self.service.process, first_job, self.pdf, first_provider, 'worker')
            self.assertTrue(entered.wait(5))
            self.assertIsNone(self.service.claim('worker'))
            self.assertEqual(self.db.jobs.find_one({'_id': second})['state'], 'queued')
            self.assertTrue(all(call.args[0].endswith('model_answer.pdf') for call in self.pdf.extract_text_from_pdf.call_args_list))
            release.set()
            first.result(timeout=5)
        self.service.process(self.service.claim('worker'), self.pdf, second_provider, 'worker')
        self.assertEqual(first_provider.prepare_marking_scheme.call_count + second_provider.prepare_marking_scheme.call_count, 1)
        self.assertEqual(self.db.jobs.count_documents({'state': 'completed'}), 2)


class PaperFallbackTests(unittest.TestCase):
    def test_paper_supplies_marks_without_reextracting_the_key_or_requiring_admin(self):
        provider = GeminiService()
        provider.question_paper_loader = Mock(return_value='Q1 10 marks')
        key = {'questions': [{'question_id': '1', 'max_marks': None, 'source_quote': 'Q1 Correct answer', 'answer': 'Correct answer'}]}
        paper = {'questions': [{'question_id': '1', 'max_marks': 10, 'source_quote': 'Q1 10 marks', 'answer': None}]}
        responses = [Mock(text=json.dumps(value)) for value in (key, paper)]
        with patch.object(provider, '_generate_with_retry', side_effect=responses) as generate:
            rubric = provider.prepare_marking_scheme('Q1 Correct answer', 10)
        self.assertEqual(generate.call_count, 2)
        self.assertEqual(rubric['questions'][0]['answer'], 'Correct answer')
        self.assertEqual(rubric['questions'][0]['max_marks'], 10)
        self.assertEqual(rubric['allocation_source'], 'question_paper')
        self.assertIn('question paper', generate.call_args.args[0])
