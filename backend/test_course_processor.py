import tempfile
import unittest
from pathlib import Path

from utils.course_processor import CourseProcessor


class CourseDiscoveryTests(unittest.TestCase):
    def test_suffixed_upload_excludes_question_paper(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root) / 'FS3401_MSE'
            folder.mkdir()
            for name in ['FS3401_answerkey.pdf', 'FS3401_questionpaper.pdf'] + [
                f'FS3401_{number}.pdf' for number in range(101, 107)
            ]:
                (folder / name).touch()
            courses, marks = CourseProcessor(root, max_marks=100).discover_courses()
            course = courses['FS3401_MSE']
            self.assertEqual(marks, 100)
            self.assertEqual(len(course['student_sheets']), 6)
            self.assertEqual(Path(course['model_answer_path']).name, 'FS3401_answerkey.pdf')
            self.assertEqual(
                {sheet['roll_number'] for sheet in course['student_sheets']},
                {f'FS3401_{number}' for number in range(101, 107)},
            )

    def test_plain_and_suffixed_courses_remain_distinct(self):
        with tempfile.TemporaryDirectory() as root:
            for name in ['FS3401', 'FS3401_MSE']:
                folder = Path(root) / 'upload' / name
                folder.mkdir(parents=True)
                (folder / 'model_answer.pdf').touch()
                (folder / '101.pdf').touch()
            courses, _ = CourseProcessor(root, max_marks=50).discover_courses()
            self.assertEqual(set(courses), {'FS3401', 'FS3401_MSE'})

    def test_question_paper_alone_is_not_a_student(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root) / 'FS3401'
            folder.mkdir()
            (folder / 'answer_key.pdf').touch()
            (folder / 'question paper.pdf').touch()
            with self.assertRaisesRegex(ValueError, 'No valid course folders'):
                CourseProcessor(root, max_marks=100).discover_courses()


if __name__ == '__main__':
    unittest.main()
