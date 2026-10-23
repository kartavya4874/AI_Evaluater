import io
import json
import unittest
from functools import wraps
from unittest.mock import Mock, patch
import mongomock
from flask import Flask, g, request
from openpyxl import Workbook
from admin_api import create_admin_api
from utils.marking_schemes import validate_scheme
from utils.gemini_service import GeminiService
from utils.structured_grading import extract_rubric, NeedsReview


def scheme(exam_type='mst', marks=10):
    return {'course_code': 'FS3401', 'exam_type': exam_type, 'max_marks': marks,
            'questions': [{'question_id': '1', 'max_marks': marks}]}


class SchemeTests(unittest.TestCase):
    def test_rejects_invalid_totals_and_duplicates(self):
        for value in ({**scheme(), 'max_marks': 11}, {**scheme(), 'questions': scheme()['questions'] * 2},
                      {**scheme(), 'exam_type': 'other'}):
            with self.assertRaises(ValueError): validate_scheme(value)

    def test_optional_rule_total(self):
        value = {**scheme(), 'questions': [{'question_id': str(i), 'max_marks': 10,
            'group': 'A', 'choose': 1, 'selection': 'best'} for i in (1, 2)]}
        self.assertEqual(validate_scheme(value)['choice_groups'][0]['count'], 1)

    def test_fallback_fills_only_missing_allocations_and_records_source(self):
        key = {'questions': [{'question_id': '1', 'max_marks': None, 'source_quote': 'Q1 Answer', 'answer': 'Answer'}]}
        with patch('utils.structured_grading.json_call', return_value=key):
            rubric = extract_rubric(Mock(), 'Q1 Answer', 10, allocations=validate_scheme(scheme()))
        self.assertEqual(rubric['questions'][0]['max_marks'], 10)
        self.assertEqual(rubric['allocation_source'], 'admin_fallback')

    def test_fallback_does_not_override_explicit_marks(self):
        key = {'questions': [{'question_id': '1', 'max_marks': 5, 'source_quote': 'Q1 5 marks Answer', 'answer': 'Answer'}]}
        with patch('utils.structured_grading.json_call', return_value=key):
            with self.assertRaises(NeedsReview):
                extract_rubric(Mock(), 'Q1 5 marks Answer', 10, allocations=validate_scheme(scheme()))

    def test_fallback_rejects_mismatched_question_ids(self):
        key = {'questions': [{'question_id': '2', 'max_marks': None, 'source_quote': 'Q2 Answer', 'answer': 'Answer'}]}
        with patch('utils.structured_grading.json_call', return_value=key):
            with self.assertRaisesRegex(NeedsReview, 'IDs'):
                extract_rubric(Mock(), 'Q2 Answer', 10, allocations=validate_scheme(scheme()))

    def test_answer_key_success_does_not_read_paper(self):
        provider = GeminiService()
        provider.question_paper_loader = Mock()
        with patch('utils.structured_grading.extract_rubric', return_value={'questions': []}), patch('utils.structured_grading.evaluate', return_value={'marks_awarded': 5}):
            provider.evaluate_answer('student', 'key', 10)
        provider.question_paper_loader.assert_not_called()

    def test_fallback_order_is_key_paper_admin(self):
        provider = GeminiService()
        provider.question_paper_loader = Mock(return_value='paper')
        provider.marking_scheme = validate_scheme(scheme())
        with patch('utils.structured_grading.extract_rubric', side_effect=[NeedsReview('missing'), NeedsReview('missing'), {'questions': []}]) as extract, patch('utils.structured_grading.evaluate', return_value={}):
            provider.evaluate_answer('student', 'key', 10)
        self.assertEqual(extract.call_count, 3)
        self.assertEqual(extract.call_args_list[1].args[-1], 'paper')
        self.assertEqual(extract.call_args.kwargs['allocations']['exam_type'], 'mst')

    def test_student_mapping_failure_does_not_trigger_fallback(self):
        provider = GeminiService()
        provider.question_paper_loader = Mock()
        with patch('utils.structured_grading.extract_rubric', return_value={'questions': []}), patch('utils.structured_grading.evaluate', side_effect=NeedsReview('unmapped answer')):
            with self.assertRaises(NeedsReview): provider.evaluate_answer('student', 'key', 10)
        provider.question_paper_loader.assert_not_called()

    def test_real_grading_pipeline_uses_admin_marks_when_key_has_none(self):
        provider = GeminiService()
        provider.question_paper_loader = Mock(return_value=None)
        provider.marking_scheme = {**validate_scheme(scheme()), 'revision': 'rev-1'}
        key = {'questions': [{'question_id': '1', 'max_marks': None, 'source_quote': 'Q1 Answer', 'answer': 'Answer'}]}
        mapped = {'segments': [{'question_id': '1', 'text': 'student answer'}]}
        score = {'marks_awarded': 7, 'feedback': 'Checked', 'strengths': [], 'missing_points': [],
                 'question_scores': [{'question_id': '1', 'max_marks': 10, 'marks_awarded': 7}]}
        responses = [Mock(text=json.dumps(value)) for value in (key, mapped, score)]
        with patch.object(provider, '_generate_with_retry', side_effect=responses):
            result = provider.evaluate_answer('student answer', 'Q1 Answer', 10)
        self.assertEqual(result['marks_awarded'], 7)
        self.assertEqual(result['rubric']['allocation_source'], 'admin_fallback')
        self.assertEqual(result['rubric']['scheme_revision'], 'rev-1')


class SchemeApiTests(unittest.TestCase):
    def setUp(self):
        self.db = mongomock.MongoClient().db
        patcher = patch('admin_api.db_connection.get_db', return_value=self.db)
        patcher.start(); self.addCleanup(patcher.stop)
        def auth(fn):
            @wraps(fn)
            def wrapped(*args, **kwargs):
                g.user_email = 'admin'
                g.user = {'role': request.headers.get('Role', 'admin')}
                return fn(*args, **kwargs)
            return wrapped
        app = Flask(__name__)
        app.register_blueprint(create_admin_api(auth))
        self.client = app.test_client()

    def test_mst_and_end_sem_are_independent_and_admin_only(self):
        for kind, marks in [('mst', 10), ('end_sem', 100)]:
            self.assertEqual(self.client.post('/api/access/marking-scheme', json=scheme(kind, marks)).status_code, 200)
        for kind, marks in [('mst', 10), ('end_sem', 100)]:
            value = self.client.get('/api/access/marking-scheme', query_string={'course_code': 'FS3401', 'exam_type': kind}).get_json()['scheme']
            self.assertEqual(value['max_marks'], marks)
        self.assertEqual(self.client.post('/api/access/marking-scheme', json=scheme(), headers={'Role': 'faculty'}).status_code, 403)
        self.assertEqual(self.client.get('/api/access/marking-scheme', headers={'Role': 'faculty'}).status_code, 403)

    def test_excel_is_previewed_without_saving(self):
        workbook = Workbook(); ws = workbook.active
        ws.append(['question_id', 'max_marks', 'group', 'choose', 'selection']); ws.append(['1', 10])
        output = io.BytesIO(); workbook.save(output); output.seek(0)
        response = self.client.post('/api/access/marking-scheme/import', data={'file': (output, 'scheme.xlsx'),
            'course_code': 'FS3401', 'exam_type': 'mst', 'max_marks': '10'})
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()['scheme']['questions'][0]['max_marks'], 10)
        self.assertEqual(self.db.marking_schemes.count_documents({}), 0)
