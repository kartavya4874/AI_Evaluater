import json
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock, patch
from utils.structured_grading import evaluate, json_call


class GradingProgressTests(unittest.TestCase):
    def test_shared_prompt_generates_once_and_rechecks_cache_after_lock(self):
        cache = {}
        lock = threading.RLock()
        entered = threading.Event()
        release = threading.Event()
        def stored(prompt, value=None):
            if value is None:
                return cache.get(prompt)
            cache[prompt] = value
        def generate(*args, **kwargs):
            entered.set()
            self.assertTrue(release.wait(5))
            return SimpleNamespace(text='{"questions":[]}')
        provider = SimpleNamespace(structured_cache=stored, structured_cache_lock=lambda _: lock,
                                   _generate_with_retry=Mock(side_effect=generate))
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(json_call, provider, 'shared rubric')
            self.assertTrue(entered.wait(5))
            second = pool.submit(json_call, provider, 'shared rubric')
            release.set()
            self.assertEqual(first.result(), second.result())
        self.assertEqual(provider._generate_with_retry.call_count, 1)

    def test_progress_records_mapping_and_validated_question_completion(self):
        progress = Mock()
        rubric = {'questions': [{'question_id': '1', 'max_marks': 10,
                                'source_quote': 'Q1 10 marks', 'answer': 'Correct'}], 'choice_groups': []}
        score = {'marks_awarded': 7, 'feedback': 'Checked', 'strengths': [], 'missing_points': [],
                 'question_scores': [{'question_id': '1', 'max_marks': 10, 'marks_awarded': 7}]}
        provider = SimpleNamespace(report_stage=progress, question_workers=1)
        with patch('utils.structured_grading.json_call', side_effect=[rubric,
                {'segments': [{'question_id': '1', 'text': 'student'}]}, score]):
            result = evaluate(provider, 'student', 'Q1 10 marks Correct', 10)
        self.assertEqual(result['marks_awarded'], 7)
        progress.assert_any_call('building_marking_scheme', {'completed': 0, 'total': 1, 'unit': 'source parts'})
        progress.assert_any_call('mapping_student_answers', {'completed': 1, 'total': 1, 'unit': 'answer parts'})
        progress.assert_any_call('marking_questions', {'completed': 1, 'total': 1, 'unit': 'questions'})

    def test_failed_question_is_not_counted_as_marked(self):
        provider = SimpleNamespace(report_stage=Mock(), question_workers=1)
        rubric = {'questions': [{'question_id': '1', 'max_marks': 10, 'source_quote': 'Q1 10 marks', 'answer': 'Correct'}]}
        with patch('utils.structured_grading.json_call', side_effect=[
                {'segments': [{'question_id': '1', 'text': 'student'}]}, RuntimeError('AI unavailable')]):
            with self.assertRaises(RuntimeError):
                evaluate(provider, 'student', 'Q1 10 marks Correct', 10, rubric=rubric)
        self.assertNotIn(('marking_questions', {'completed': 1, 'total': 1, 'unit': 'questions'}),
                         [call.args for call in provider.report_stage.call_args_list])
