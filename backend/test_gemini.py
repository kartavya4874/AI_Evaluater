"""Offline contract checks for the current vLLM provider; never call a live API."""
import unittest
from unittest.mock import Mock, patch
from utils import gemini_service as service


class ProviderContractTests(unittest.TestCase):
    def test_cancel_before_request_does_not_call_provider(self):
        provider = service.GeminiService()
        provider.check_cancelled = Mock(side_effect=InterruptedError('Evaluation cancelled'))
        with patch.object(service, '_call_vllm') as call:
            with self.assertRaises(InterruptedError):
                provider._generate_with_retry('grade')
        call.assert_not_called()

    def test_cancel_after_response_prevents_truncation_retry(self):
        provider = service.GeminiService()
        cancelled = False
        def check():
            if cancelled:
                raise InterruptedError('Evaluation cancelled')
        def response(*args, **kwargs):
            nonlocal cancelled
            cancelled = True
            result = Mock(status_code=200)
            result.json.return_value = {'choices': [{'finish_reason': 'length'}]}
            return result
        provider.check_cancelled = check
        with patch.object(service, 'VLLM_TOKENIZE_URL', ''), patch.object(service, 'inference_slot'), patch.object(service.requests, 'post', side_effect=response) as post:
            with self.assertRaises(InterruptedError):
                provider._generate_with_retry('grade')
        self.assertEqual(post.call_count, 1)

    def test_cancel_while_waiting_for_capacity(self):
        import mongomock
        from utils import inference_gate
        db = mongomock.MongoClient().db
        checks = Mock(side_effect=[None, None, InterruptedError('Evaluation cancelled')])
        with patch.object(inference_gate.db_connection, 'get_collection', return_value=db.inference_slots), patch.object(inference_gate, 'parallelism', return_value=1), patch.object(db.inference_slots, 'find_one_and_update', return_value=None), patch.object(inference_gate.time, 'sleep'):
            with self.assertRaises(InterruptedError):
                with inference_gate.inference_slot(600, check_cancelled=checks):
                    self.fail('Cancelled request acquired capacity')

    def test_json_mode_and_transport_deadline(self):
        response = Mock(status_code=200)
        response.json.return_value = {'choices': [{'finish_reason': 'stop', 'message': {'content': '{}'}}]}
        with patch.object(service, 'VLLM_TOKENIZE_URL', ''), patch.object(service, 'inference_slot'), patch.object(service.requests, 'post', return_value=response) as post:
            result = service._call_vllm([], require_json=True, timeout=17)
        self.assertEqual(result.text, '{}')
        self.assertEqual(post.call_args.kwargs['json']['response_format'], {'type': 'json_object'})
        self.assertEqual(post.call_args.kwargs['timeout'], (service.VLLM_CONNECT_TIMEOUT_SECONDS, 17))

    def test_empty_response_is_not_a_grade(self):
        response = Mock(status_code=200)
        response.json.return_value = {'choices': [{'finish_reason': 'stop', 'message': {'content': ''}}]}
        with patch.object(service, 'VLLM_TOKENIZE_URL', ''), patch.object(service, 'inference_slot'), patch.object(service.requests, 'post', return_value=response):
            with self.assertRaisesRegex(ValueError, 'no text'):
                service._call_vllm([])
