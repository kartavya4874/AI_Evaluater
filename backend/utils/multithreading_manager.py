import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils.evaluation_pipeline import EvaluationPipeline

logger = logging.getLogger(__name__)


class MultithreadingManager:
    def __init__(self, pdf_processor, gemini_service, max_workers=3):
        self.pdf_processor = pdf_processor
        self.gemini_service = gemini_service
        self.max_workers = max_workers
        self.results = {}
        self.status = {}
        self._lock = threading.Lock()
        self._cancel_event = threading.Event()
        self._on_student_complete = None

    def _update_status(self, course_code, status, detail=''):
        """Thread-safe status update."""
        with self._lock:
            self.status[course_code] = {
                'status': status,
                'detail': detail
            }

    def set_on_student_complete(self, callback):
        """Set the callback for real-time student completion events."""
        self._on_student_complete = callback

    def cancel(self):
        """Signal all running evaluations to stop."""
        logger.warning("Batch processing CANCEL requested")
        self._cancel_event.set()

    def is_cancelled(self):
        """Check if cancellation was requested."""
        return self._cancel_event.is_set()

    def _process_single_course(self, course_code, course_info, max_marks,
                                exam_type='end_sem', root_directory=None):
        """Process a single course (runs within a thread)."""
        self._update_status(course_code, 'processing',
                            f"Evaluating {len(course_info['student_sheets'])} students...")

        pipeline = EvaluationPipeline(self.pdf_processor, self.gemini_service)

        try:
            results = pipeline.evaluate_course(
                course_code=course_code,
                model_answer_path=course_info['model_answer_path'],
                student_sheets=course_info['student_sheets'],
                max_marks=max_marks,
                exam_type=exam_type,
                root_directory=root_directory,
                cancel_event=self._cancel_event,
                on_student_complete=self._on_student_complete,
                max_workers=self.max_workers
            )

            completed = sum(1 for r in results if r.get('status') == 'completed')
            total = len(course_info['student_sheets'])

            if self._cancel_event.is_set():
                self._update_status(course_code, 'cancelled',
                                    f"{completed}/{total} students completed before cancellation")
            else:
                self._update_status(course_code, 'completed',
                                    f"{completed}/{total} students evaluated successfully")
            return results

        except Exception as e:
            logger.error(f"[{course_code}] Course processing failed: {e}")
            self._update_status(course_code, 'failed', str(e))
            return [{
                'course_code': course_code,
                'roll_number': 'N/A',
                'status': 'error',
                'error': f"Course processing failed: {str(e)}"
            }]

    def process_courses_parallel(self, courses_data, max_marks,
                                  exam_type='end_sem', root_directory=None):
        """
        Process multiple courses in parallel using thread pool.

        Args:
            courses_data: Dict of course_code -> course_info
            max_marks: Maximum marks for all evaluations
            exam_type: 'mst' or 'end_sem'
            root_directory: Root directory for progress tracking

        Returns:
            Dict of course_code -> list of evaluation results
        """
        # Reset cancel event for new run
        self._cancel_event.clear()

        logger.info(f"Starting PARALLEL processing of {len(courses_data)} courses "
                     f"with {self.max_workers} workers (exam_type={exam_type})...")

        # Initialize all statuses
        for code in courses_data:
            self._update_status(code, 'queued')

        all_results = {}

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}
            for course_code, course_info in courses_data.items():
                future = executor.submit(
                    self._process_single_course,
                    course_code, course_info, max_marks,
                    exam_type, root_directory
                )
                futures[future] = course_code

            for future in as_completed(futures):
                course_code = futures[future]
                try:
                    result = future.result()
                    all_results[course_code] = result
                except Exception as e:
                    logger.error(f"[{course_code}] Thread exception: {e}")
                    all_results[course_code] = [{
                        'course_code': course_code,
                        'roll_number': 'N/A',
                        'status': 'error',
                        'error': str(e)
                    }]
                    self._update_status(course_code, 'failed', str(e))

        status_msg = "cancelled" if self._cancel_event.is_set() else "complete"
        logger.info(f"Parallel processing {status_msg}. "
                     f"{len(all_results)} courses processed.")
        self.results = all_results
        return all_results

    def process_courses_sequential(self, courses_data, max_marks,
                                    exam_type='end_sem', root_directory=None):
        """
        Process courses one after another (for testing/debugging).
        """
        self._cancel_event.clear()

        logger.info(f"Starting SEQUENTIAL processing of {len(courses_data)} courses "
                     f"(exam_type={exam_type})...")

        for code in courses_data:
            self._update_status(code, 'queued')

        all_results = {}

        for course_code, course_info in courses_data.items():
            if self._cancel_event.is_set():
                logger.warning(f"[{course_code}] Skipping due to cancellation")
                self._update_status(course_code, 'cancelled', 'Skipped due to cancellation')
                continue

            try:
                result = self._process_single_course(
                    course_code, course_info, max_marks,
                    exam_type, root_directory
                )
                all_results[course_code] = result
            except Exception as e:
                logger.error(f"[{course_code}] Sequential processing failed: {e}")
                all_results[course_code] = [{
                    'course_code': course_code,
                    'roll_number': 'N/A',
                    'status': 'error',
                    'error': str(e)
                }]
                self._update_status(course_code, 'failed', str(e))

        status_msg = "cancelled" if self._cancel_event.is_set() else "complete"
        logger.info(f"Sequential processing {status_msg}. "
                     f"{len(all_results)} courses processed.")
        self.results = all_results
        return all_results

    def get_status(self):
        """Return current processing status for all courses."""
        with self._lock:
            return dict(self.status)
