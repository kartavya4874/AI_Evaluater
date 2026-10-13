import unittest
from unittest import mock
import os
# Assuming pdf_processor is in the same module structure relative to testing environment
# We must patch dependencies if they rely on external services (like real PDF loaders or OCR).
# For this example, we assume the main class structure and helper functions are available.

try:
    # Attempt a local import based on the provided context path
    from ai_examer.AI_Evaluater.backend.utils import pdf_processor 
except ImportError:
    print("Could not find pdf_processor via standard relative import. Please ensure your PYTHONPATH is set correctly.")
    # Fallback placeholder for demonstration purposes if actual paths fail the mock test setup
    class MockPDFProcessor:
        def process_document(self, file_path):
            raise NotImplementedError("Actual PDF processing logic depends on external dependencies (PyMuPDF/Tesseract) not available in this mocking context.")
        @staticmethod
        def analyze_layout(page_content):
            return {"blocks": 1} # Placeholder return

    pdf_processor = MockPDFProcessor()


class TestPdfProcessorEnhancements(unittest.TestCase):
    """
    Unit tests for complex PDF parsing logic in pdf_processor.py.
    These mocks assume the underlying PDF library interface is stable and focus on
    validating Python processing logic (column aggregation, OCR fallback, mixed element handling).
    """

    def setUp(self):
        # Initialize the processor instance before each test
        self.processor = pdf_processor()
        super().setUp()

    @mock.patch('pdf_processor.get_text_content') # Mocking external file reading/extraction
    @mock.patch('pdf_processor._extract_layout_data') # Mocking the core parsing logic
    def test_multi_column_report(self, mock_extract_layout_data, mock_get_text_content):
        """
        Test case 1: Handles complex multi-column report layouts (e.g., dual columns or segmented grid).
        The expected behavior is that the processor reads blocks sequentially and merges them by conceptual reading order, not just physical PDF coordinates.
        """
        # --- Mock Setup: Simulate data structure for a two-column layout ---
        mock_layout = [
            {'text': 'Left side passage 1.', 'bbox': (100, 50, 300, 80), 'source': 'col_A'}, # Top left 
            {'text': 'Right header info A.', 'bbox': (400, 50, 600, 80), 'source': 'col_B'}, # Top right
            {'text': 'Left side passage 2.', 'bbox': (100, 90, 300, 120), 'source': 'col_A'}, # Bottom left
            {'text': 'Right footer info B.', 'bbox': (400, 90, 600, 120), 'source': 'col_B'} # Bottom right
        ]
        mock_extract_layout_data.return_value = mock_layout

        # --- Test Execution ---
        result = self.processor.process_document("path/to/multi_column_report.pdf")
        
        # --- Assertions ---
        self.assertEqual(len(result['extracted_blocks']), 4)
        
        # Check if blocks are ordered correctly (e.g., Left-Top, Right-Top, Left-Bottom, Right-Bottom)
        expected_order = ["Left side passage 1.", "Right header info A.", "Left side passage 2.", "Right footer info B."]
        actual_texts = [block['text'] for block in result['extracted_blocks']]
        self.assertEqual(actual_texts, expected_order)

    @mock.patch('pdf_processor.get_text_content')
    @mock.patch('pdf_processor._extract_ocr_data', return_value={'text': 'OCR data recovered successfully.'}) 
    def test_scanned_image_only(self, mock_extract_ocr_data, mock_get_text_content):
        """
        Test case 2: Handles PDF pages consisting only of scanned images (zero native text layer).
        This must trigger the OCR fallback mechanism and process the resulting image data.
        """
        # --- Mock Setup: Simulate a document that fails native text extraction ---
        mock_get_text_content.return_value = None # Indicates no extractable text layer
        
        # --- Test Execution ---
        result = self.processor.process_document("path/to/scanned_image_only.pdf")

        # --- Assertions ---
        self.assertIsNotNone(result['ocr_used'], "OCR processing should be detected and used.")
        self.assertEqual(result['extracted_blocks'][0]['text'], 'OCR data recovered successfully.')
        self.assertIsInstance(result, dict) # Basic structure validation

    @mock.patch('pdf_processor.get_text_content')
    @mock.patch('pdf_processor._extract_layout_data')
    def test_mixed_elements_and_floating_objects(self, mock_extract_layout_data, mock_get_text_content):
        """
        Test case 3: Validates processing of mixed content (floating images/tables interspersed with text).
        The processor must distinguish between core flowing text and non-flowing graphical elements.
        """
        # --- Mock Setup: Simulate data structure for floating objects (Images, Tables) ---
        mock_layout = [
            {'text': 'Flowing text paragraph before the image.', 'bbox': (50, 50, 300, 100), 'source': 'text'}, # Start
            # Floating Image/Graphical Object Simulation: Text here indicates an object is present but not flowing with natural text.
            {'text': '[IMAGE: Quarterly Report Graph A]', 'bbox': (320, 50, 650, 150), 'source': 'float_image'}, 
            {'text': 'The main conclusion flows naturally after the visual aid.', 'bbox': (50, 180, 600, 210), 'source': 'text'} # End
        ]
        mock_extract_layout_data.return_value = mock_layout

        # --- Test Execution ---
        result = self.processor.process_document("path/to/mixed_elements.pdf")

        # --- Assertions ---
        self.assertEqual(len(result['extracted_blocks']), 3)
        
        # Check that the floating object is detected and classified correctly, but does not break text flow.
        intermediate_block = result['extracted_blocks'][1]
        self.assertIn('IMAGE', intermediate_block['text'].upper())
        self.assertEqual(intermediate_block['source'], 'float_image')

if __name__ == '__main__':
    unittest.main()