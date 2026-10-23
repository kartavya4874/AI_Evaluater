import unittest
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

import test_workspace
from config import Config
from utils.workspace import now
from utils.run_policy import RunPaused, ModelOutputError, remaining_budget
from utils.structured_grading import (NeedsReview, validate_rubric, evaluate,
                                      administrative_text, json_call)


class RunRecoveryTests(unittest.TestCase):
    setUp = test_workspace.WorkspaceTests.setUp

    def test_expired_queued_run_never_calls_ai(self):
        self.service.enqueue(self.sheet_id, 'admin')
        self.db.jobs.update_one({'_id': self.sheet_id}, {'$set': {
            'deadline_at': now() - timedelta(seconds=1)}})
        self.assertIsNone(self.service.claim('worker'))
        self.assertEqual(self.db.jobs.find_one()['state'], 'paused')
        self.llm.evaluate_answer.assert_not_called()

    def test_worker_recovery_preserves_deadline_and_stops_at_budget(self):
        self.service.enqueue(self.sheet_id, 'admin')
        original = self.service.claim('old')
        self.db.attempts.insert_one({'_id': original['attempt_id'], 'status': 'processing', 'token': original['token']})
        self.db.jobs.update_one({'_id': self.sheet_id}, {'$set': {
            'retry_count': Config.EVALUATION_MAX_RETRIES}})
        self.service.recover_interrupted('new')
        job = self.db.jobs.find_one()
        self.assertEqual(job['deadline_at'], original['deadline_at'])
        self.assertEqual(job['state'], 'paused')
        self.assertEqual(self.db.attempts.find_one()['status'], 'paused')
        self.assertIsNone(self.service.claim('new'))

    def test_technical_output_failure_does_not_block_course_as_invalid_source(self):
        self.service.enqueue(self.sheet_id, 'admin')
        self.llm.prepare_marking_scheme.side_effect = ModelOutputError('Malformed AI JSON')
        self.service.process(self.service.claim('worker'), self.pdf, self.llm, 'worker')
        self.assertEqual(self.db.jobs.find_one()['state'], 'error')
        self.assertEqual(self.db.course_runs.find_one()['state'], 'paused')
        self.assertIsNone(self.db.sheets.find_one()['active_attempt'])
        self.service.enqueue(self.sheet_id, 'admin')
        self.assertIsNotNone(self.service.claim('worker'))

    def test_cancel_has_priority_over_expired_deadline(self):
        self.service.enqueue(self.sheet_id, 'admin')
        job = self.service.claim('worker')
        job['deadline_at'] = now() - timedelta(seconds=1)
        self.db.jobs.update_one({'_id': self.sheet_id}, {'$set': {'cancel_requested': True}})
        self.service.process(job, self.pdf, self.llm, 'worker')
        self.assertEqual(self.db.jobs.find_one()['state'], 'cancelled')
        self.llm.prepare_marking_scheme.assert_not_called()

    def test_run_budget_does_not_reset_on_check(self):
        with self.assertRaises(RunPaused):
            remaining_budget({'deadline_at': now() - timedelta(seconds=1)})

    def test_course_preparation_does_not_prevent_another_course_starting(self):
        from pathlib import Path
        folder = Path(self.temp.name) / 'MB3204'
        folder.mkdir()
        (folder / 'model_answer.pdf').write_bytes(b'another key')
        (folder / '201.pdf').write_bytes(b'another student')
        ids = self.service.prepare(self.temp.name, 'exam-1', 'mst', 100, 'admin')
        other = next(i for i in ids if i != self.sheet_id)
        self.service.enqueue(self.sheet_id, 'admin')
        first = self.service.claim('worker')
        self.service.enqueue(other, 'admin')
        second = self.service.claim('worker')
        self.assertIsNotNone(second)
        self.assertNotEqual(first['course_run_key'], second['course_run_key'])

    def test_old_course_preparation_cannot_publish_after_recovery(self):
        self.service.enqueue(self.sheet_id, 'admin')
        job = self.service.claim('old')
        def recovered(*args):
            self.service.recover_interrupted('replacement')
            return {'questions': []}
        self.llm.prepare_marking_scheme.side_effect = recovered
        self.service.process(job, self.pdf, self.llm, 'old')
        self.assertEqual(self.db.course_runs.find_one()['state'], 'retry')
        self.assertIsNone(self.db.course_runs.find_one().get('rubric'))
        self.llm.evaluate_answer.assert_not_called()
        self.assertIsNone(self.db.sheets.find_one()['active_attempt'])


class MarkingSafetyTests(unittest.TestCase):
    def rubric(self):
        return {'questions': [
            {'question_id': '1', 'max_marks': 5, 'source_quote': 'Q1 5 marks', 'answer': 'First'},
            {'question_id': '2', 'max_marks': 5, 'source_quote': 'Q2 5 marks', 'answer': 'Second'}],
            'choice_groups': []}

    def test_source_number_must_match_allocation(self):
        candidate = {'questions': [{'question_id': '1', 'max_marks': 10,
            'source_quote': 'Q1 5 marks', 'answer': 'Correct'}]}
        with self.assertRaises(NeedsReview):
            validate_rubric(candidate, 'Q1 5 marks Correct', 10)

    def test_question_one_cannot_use_question_ten_evidence(self):
        candidate = {'questions': [{'question_id': '1', 'max_marks': 5,
            'source_quote': 'Q10 5 marks', 'answer': 'Correct'}]}
        with self.assertRaises(NeedsReview):
            validate_rubric(candidate, 'Q10 5 marks Correct', 5)

    def test_own_page_header_is_administrative(self):
        self.assertTrue(administrative_text('Page 1:'))
        self.assertFalse(administrative_text('Page 1:\nActual student answer'))

    def test_wrong_mapping_cannot_publish_a_false_zero(self):
        text = 'Q1 First answer. Q2 Second answer.'
        with patch('utils.structured_grading.json_call', return_value={
                'segments': [{'question_id': '1', 'text': text}]}) as call:
            with self.assertRaises(NeedsReview):
                evaluate(SimpleNamespace(), text, 'References', 10, rubric=self.rubric())
        self.assertEqual(call.call_count, 1)  # No scoring started.

    def test_absence_without_explicit_confirmation_is_reviewed(self):
        with patch('utils.structured_grading.json_call', return_value={
                'segments': [{'question_id': '1', 'text': 'First answer'}]}) as call:
            with self.assertRaises(NeedsReview):
                evaluate(SimpleNamespace(), 'First answer', 'References', 10, rubric=self.rubric())
        self.assertEqual(call.call_count, 1)

    def test_malformed_generation_has_finite_repairs_and_technical_status(self):
        provider = SimpleNamespace(_generate_with_retry=Mock(return_value=SimpleNamespace(text='invalid')))
        with self.assertRaises(ModelOutputError):
            json_call(provider, 'Extract rubric')
        self.assertEqual(provider._generate_with_retry.call_count, Config.AI_JSON_REPAIR_ATTEMPTS)

    def test_confirmed_unanswered_question_can_receive_zero(self):
        score = {'marks_awarded': 3, 'feedback': 'Checked', 'strengths': [], 'missing_points': [],
                 'question_scores': [{'question_id': '1', 'max_marks': 5, 'marks_awarded': 3}]}
        with patch('utils.structured_grading.json_call', side_effect=[{
                'segments': [{'question_id': '1', 'text': 'Q1 First answer'}],
                'unanswered_question_ids': ['2']}, score]):
            result = evaluate(SimpleNamespace(question_workers=1), 'Q1 First answer',
                              'References', 10, rubric=self.rubric())
        self.assertEqual(result['marks_awarded'], 3)
        self.assertEqual(next(q for q in result['question_scores'] if q['question_id'] == '2')['marks_awarded'], 0)


class RequestBudgetTests(unittest.TestCase):
    def test_tokenizer_and_inference_share_remaining_budget(self):
        from contextlib import nullcontext
        from utils.gemini_service import _call_vllm
        token = Mock(status_code=200)
        token.json.return_value = {'count': 20}
        response = Mock(status_code=200)
        response.json.return_value = {'choices': [{'message': {'content': 'ok'}, 'finish_reason': 'stop'}]}
        with patch('utils.gemini_service.VLLM_TOKENIZE_URL', 'http://test/tokenize'), \
             patch('utils.gemini_service.inference_slot', return_value=nullcontext()) as slot, \
             patch('utils.gemini_service.requests.post', side_effect=[token, response]) as post:
            result = _call_vllm([], remaining_budget=Mock(side_effect=[10, 7, 5]))
        self.assertEqual(result.text, 'ok')
        self.assertLessEqual(sum(post.call_args_list[0].kwargs['timeout']), 10)
        self.assertLessEqual(sum(post.call_args_list[1].kwargs['timeout']), 5)
        self.assertLessEqual(slot.call_args.args[0], 7)
