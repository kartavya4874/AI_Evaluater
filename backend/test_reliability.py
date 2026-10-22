import unittest
from unittest.mock import Mock, patch
import requests
from tenacity import wait_none
from utils import gemini_service as service


class InferenceTests(unittest.TestCase):
    def setUp(self):
        self.gate = patch.object(service, 'inference_slot')
        self.gate.start()
        self.addCleanup(self.gate.stop)

    def test_timeout_retries_are_bounded(self):
        call = service.GeminiService._generate_with_retry.retry_with(wait=wait_none())
        with patch.object(service, '_call_vllm', side_effect=requests.ReadTimeout('timeout')) as mocked:
            with self.assertRaises(requests.ReadTimeout):
                call(service.GeminiService(), 'test')
            self.assertEqual(mocked.call_count, 2)

    def test_invalid_request_is_not_retried(self):
        call = service.GeminiService._generate_with_retry.retry_with(wait=wait_none())
        with patch.object(service, '_call_vllm', side_effect=ValueError('too long')) as mocked:
            with self.assertRaises(ValueError):
                call(service.GeminiService(), 'test')
            self.assertEqual(mocked.call_count, 1)

    def test_truncated_response_is_not_a_result(self):
        response = Mock(status_code=200)
        response.json.return_value = {'choices': [{'finish_reason': 'length', 'message': {'content': '{}'}}]}
        with patch.object(service.requests, 'post', return_value=response):
            with self.assertRaisesRegex(ValueError, 'truncated'):
                service._call_vllm([])

    def test_truncation_retries_with_context_aware_budget(self):
        with patch.object(service, 'VLLM_MAX_MODEL_LEN', 8192), patch.object(service, 'VLLM_MAX_OUTPUT_TOKENS', 6000), patch.object(service, '_call_vllm', side_effect=[service.TruncatedResponseError(6000), service._DummyResponse('complete')]) as call:
            result = service.GeminiService()._generate_with_retry('test')
            self.assertEqual(result.text, 'complete')
            self.assertEqual([c.kwargs['max_tokens'] for c in call.call_args_list], [1500, 2192])

    def test_persistent_truncation_is_bounded(self):
        with patch.object(service, 'VLLM_MAX_MODEL_LEN', 8192), patch.object(service, 'VLLM_MAX_OUTPUT_TOKENS', 6000), patch.object(service, '_call_vllm', side_effect=service.TruncatedResponseError()) as call:
            with self.assertRaises(service.TruncatedResponseError):
                service.GeminiService()._generate_with_retry('test', require_json=True)
            self.assertEqual([c.kwargs['max_tokens'] for c in call.call_args_list], [1500, 3000, 6000])

    def test_truncation_without_context_headroom_is_not_retried(self):
        with patch.object(service, 'VLLM_MAX_MODEL_LEN', 8192), patch.object(service, '_call_vllm', side_effect=service.TruncatedResponseError(7000)) as call:
            with self.assertRaises(service.TruncatedResponseError):
                service.GeminiService()._generate_with_retry('test')
            self.assertEqual(call.call_count, 1)

    def test_token_budget_blocks_oversized_prompt(self):
        response = Mock(status_code=200)
        response.json.return_value = {'count': 8000}
        with patch.object(service, 'VLLM_TOKENIZE_URL', 'http://test/tokenize'), patch.object(service.requests, 'post', return_value=response) as call:
            with self.assertRaisesRegex(ValueError, 'context limit'):
                service._call_vllm([], require_json=True)
            self.assertEqual(call.call_count, 1)

    def test_invalid_grading_schema_raises(self):
        instance = service.GeminiService()
        with patch.object(instance, '_generate_with_retry', return_value=service._DummyResponse('{}')):
            with self.assertRaises(ValueError):
                instance.evaluate_answer('student', 'key', 100)

    def test_legacy_failure_classification_preserves_genuine_zero(self):
        from migrate_evaluations import classify
        self.assertIsNone(classify({'status': 'completed', 'marks': 0, 'feedback': 'No correct answers'}))
        failure = classify({'marks': 0, 'feedback': 'Error during evaluation: timeout'})
        self.assertEqual(failure['status'], 'error')
        self.assertIsNone(failure['marks'])

    def test_inference_gate_releases_after_exception(self):
        import mongomock
        from utils.inference_gate import inference_slot
        collection = mongomock.MongoClient().db.inference_slots
        with patch('utils.inference_gate.db_connection.get_collection', return_value=collection):
            with self.assertRaises(ValueError):
                with inference_slot(1):
                    raise ValueError('failed request')
            with inference_slot(1):
                self.assertTrue(collection.find_one()['owner'])
            self.assertEqual(collection.find_one()['owner'], '')

    def test_question_totals_are_validated(self):
        from utils.result_validation import validate_result
        result = {'marks_awarded': 10, 'strengths': [], 'missing_points': [], 'feedback': 'Reviewed',
                  'question_scores': [{'question_id': '1', 'marks_awarded': 10, 'max_marks': 20}]}
        self.assertEqual(validate_result(result, 20, require_questions=True)['marks_awarded'], 10)
        with self.assertRaisesRegex(ValueError, 'totals'):
            validate_result(result, 100, require_questions=True)
        result['question_scores'].append(result['question_scores'][0])
        with self.assertRaisesRegex(ValueError, 'unique'):
            validate_result(result, 20, require_questions=True)


if __name__ == '__main__':
    unittest.main()
