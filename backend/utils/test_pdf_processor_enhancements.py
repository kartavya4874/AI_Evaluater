"""Real processor boundary tests without Poppler or model-server calls."""
import unittest
from unittest.mock import Mock, patch
from utils.pdf_processor import PDFProcessor


class PDFBoundaryTests(unittest.TestCase):
    def test_render_requests_only_one_bounded_page(self):
        image = Mock()
        with patch('utils.pdf_processor.convert_from_path', return_value=[image]) as render:
            self.assertIs(PDFProcessor.render_page('input.pdf', 19), image)
        args = render.call_args.kwargs
        self.assertEqual((args['first_page'], args['last_page']), (20, 20))
        self.assertEqual(args['thread_count'], 1)
        self.assertEqual(args['timeout'], 120)
        self.assertEqual(args['size'], 2500)

    def test_unexpected_render_images_are_closed(self):
        images = [Mock(), Mock()]
        with patch('utils.pdf_processor.convert_from_path', return_value=images):
            with self.assertRaises(ValueError):
                PDFProcessor.render_page('input.pdf', 0)
        for image in images:
            image.close.assert_called_once()

    def test_short_page_is_not_silently_dropped(self):
        pages = [Mock(), Mock()]
        pages[0].extract_text.return_value = 'A complete text layer with enough content'
        pages[1].extract_text.return_value = 'Q2 answer'
        with patch('utils.pdf_processor.PdfReader', return_value=Mock(pages=pages)):
            with self.assertRaisesRegex(Exception, 'visual extraction'):
                PDFProcessor.extract_text_from_pdf('input.pdf')
