"""Offline contract checks for the current vLLM provider; never call a live API."""
import unittest
from unittest.mock import Mock, patch
from utils import gemini_service as service


class ProviderContractTests(unittest.TestCase):
    def test_json_mode_and_transport_deadline(self):
        response = Mock(status_code=200)
        response.json.return_value = {'choices': [{'finish_reason': 'stop', 'message': {'content': '{}'}}]}
        with patch.object(service, 'VLLM_TOKENIZE_URL', ''), patch.object(service, 'inference_slot'), patch.object(service.requests, 'post', return_value=response) as post:
            result = service._call_vllm([], require_json=True, timeout=17)
        self.assertEqual(result.text, '{}')
        self.assertEqual(post.call_args.kwargs['json']['response_format'], {'type': 'json_object'})
        self.assertEqual(post.call_args.kwargs['timeout'], (10, 17))

    def test_empty_response_is_not_a_grade(self):
        response = Mock(status_code=200)
        response.json.return_value = {'choices': [{'finish_reason': 'stop', 'message': {'content': ''}}]}
        with patch.object(service, 'VLLM_TOKENIZE_URL', ''), patch.object(service, 'inference_slot'), patch.object(service.requests, 'post', return_value=response):
            with self.assertRaisesRegex(ValueError, 'no text'):
                service._call_vllm([])
