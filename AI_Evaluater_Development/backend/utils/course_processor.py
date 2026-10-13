import os
import re
import logging
from utils.config_loader import ConfigLoader

logger = logging.getLogger(__name__)

# Pattern to match course codes like MB3103, CH3501, PH2401, FS3401
COURSE_CODE_PATTERN = re.compile(r'^[A-Z]{2,}\d{3,}$')


class CourseProcessor:
    def __init__(self, root_directory, max_marks=None):
        self.root_directory = root_directory
        self.courses = {}
        self.max_marks = max_marks  # If provided from UI, skip config.json

    def discover_courses(self):
        """
        Scan the root directory for course folders.
        If max_marks was provided via constructor (from UI), config.json is optional.
        Returns (courses_dict, max_marks).

        courses_dict structure:
        {
            "MB3103": {
                "course_code": "MB3103",
                "folder_path": "/path/to/MB3103",
                "model_answer_path": "/path/to/MB3103/model_answer.pdf",
                "max_marks": 100,
                "student_sheets": [
                    {"roll_number": "12345", "file_path": "/path/to/MB3103/12345.pdf"},
                    ...
                ]
            },
            ...
        }
        """
        if not os.path.isdir(self.root_directory):
            raise FileNotFoundError(f"Root directory not found: {self.root_directory}")

        # Load config: prefer UI-provided max_marks, fall back to config.json
        if self.max_marks is not None:
            logger.info(f"Using UI-provided config: max_marks={self.max_marks}")
        else:
            try:
                config = ConfigLoader.load_root_config(self.root_directory)
                self.max_marks = config['max_marks']
                logger.info(f"Loaded config.json: max_marks={self.max_marks}")
            except FileNotFoundError:
                raise ValueError(
                    "max_marks not provided and config.json not found. "
                    "Please set max_marks in the UI or add a config.json file."
                )

        # Scan subdirectories recursively to find course folders regardless of nesting level
        for root, dirs, files in os.walk(self.root_directory):
            for item in dirs:
                if item.startswith('.'):
                    continue

                # Check if folder name matches course code pattern
                if not COURSE_CODE_PATTERN.match(item):
                    continue
                
                course_code = item
                
                # If we already processed this course code (e.g. nested MB3103/MB3103), skip
                if course_code in self.courses:
                    continue

                item_path = os.path.join(root, item)
                course_info = self._process_course_folder(course_code, item_path)

                if course_info:
                    self.courses[course_code] = course_info
                    logger.info(
                        f"Discovered course {course_code}: "
                        f"{len(course_info['student_sheets'])} student sheets"
                    )

        if not self.courses:
            raise ValueError(f"No valid course folders found in {self.root_directory}")

        logger.info(f"Total courses discovered: {len(self.courses)}")
        return self.courses, self.max_marks

    def _process_course_folder(self, course_code, folder_path):
        """Process a single course folder to extract model answer and student sheets."""
        # Check for nested subfolder with same name (e.g., MB3103/MB3103/)
        nested_path = os.path.join(folder_path, course_code)
        if os.path.isdir(nested_path):
            # If no PDFs at top level but PDFs exist in nested folder, use nested
            top_pdfs = [f for f in os.listdir(folder_path) if f.lower().endswith('.pdf')]
            if not top_pdfs:
                logger.info(f"  [{course_code}] Using nested subfolder: {course_code}/{course_code}/")
                folder_path = nested_path

        model_answer_path = None
        student_sheets = []

        # Pattern to match model answers with ANY course-code-like prefix
        # e.g., MB3103_model_answer, MA3134_Model_Answer, model_answer, answer_key
        model_answer_pattern = re.compile(
            r'^([a-z]{2,}\d{3,}_?)?(model[_\s]?answer|answer[_\s]?key)$'
        )

        for filename in sorted(os.listdir(folder_path)):
            if not filename.lower().endswith('.pdf'):
                continue

            file_path = os.path.join(folder_path, filename)
            base_name = os.path.splitext(filename)[0].lower()

            # Identify model answer (flexible naming)
            if model_answer_pattern.match(base_name):
                model_answer_path = file_path
                logger.info(f"  [{course_code}] Model answer: {filename}")
            else:
                # Everything else is a student sheet — filename is roll number
                roll_number = os.path.splitext(filename)[0]
                student_sheets.append({
                    'roll_number': roll_number,
                    'file_path': file_path,
                    'filename': filename
                })

        if not model_answer_path:
            logger.error(f"  [{course_code}] No model_answer.pdf found — skipping course")
            return None

        if not student_sheets:
            logger.warning(f"  [{course_code}] No student answer sheets found — skipping course")
            return None

        return {
            'course_code': course_code,
            'folder_path': folder_path,
            'model_answer_path': model_answer_path,
            'max_marks': self.max_marks,
            'student_sheets': student_sheets
        }

    def get_course_summary(self):
        """Return a summary of discovered courses."""
        summary = {}
        for code, info in self.courses.items():
            summary[code] = {
                'course_code': code,
                'student_count': len(info['student_sheets']),
                'max_marks': info['max_marks'],
                'model_answer': os.path.basename(info['model_answer_path']),
                'roll_numbers': [s['roll_number'] for s in info['student_sheets']]
            }
        return summary
