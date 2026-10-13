import os
import json
import hashlib
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)


class EvaluationPipeline:
    def __init__(self, pdf_processor, gemini_service, cache_dir=None):
        self.pdf_processor = pdf_processor
        self.gemini_service = gemini_service
        self.cache_dir = cache_dir or os.path.join(os.path.dirname(os.path.dirname(__file__)), 'cache')
        os.makedirs(self.cache_dir, exist_ok=True)

    # ==================== CACHING ====================

    def _get_file_hash(self, file_path):
        """Generate SHA-256 hash of a file for caching."""
        with open(file_path, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()

    def _extract_text_cached(self, file_path):
        """Extract text from a PDF with caching support."""
        file_hash = self._get_file_hash(file_path)
        cache_file = os.path.join(self.cache_dir, f'{file_hash}.txt')

        if os.path.exists(cache_file):
            logger.info(f"  Cache HIT for {os.path.basename(file_path)} ({file_hash[:12]}...)")
            with open(cache_file, 'r', encoding='utf-8') as cf:
                return cf.read()

        logger.info(f"  Cache MISS for {os.path.basename(file_path)} — extracting text...")
        try:
            text = self.pdf_processor.extract_text_from_pdf(file_path)
            if len(text.strip()) < 100:
                logger.info(f"  Insufficient plain text, using Gemini vision API...")
                images = self.pdf_processor.convert_pdf_to_images(file_path, max_pages=36)
                text = self.pdf_processor.extract_text_from_images_via_gemini(
                    images, self.gemini_service
                )
        except Exception as e:
            logger.warning(f"  Text extraction failed: {e}, falling back to Gemini vision...")
            images = self.pdf_processor.convert_pdf_to_images(file_path, max_pages=36)
            text = self.pdf_processor.extract_text_from_images_via_gemini(
                images, self.gemini_service
            )

        # Save to cache
        with open(cache_file, 'w', encoding='utf-8') as cf:
            cf.write(text)
        logger.info(f"  Cached text for {os.path.basename(file_path)}")

        return text

    def _evaluate_cached(self, student_text, model_text, max_marks,
                         question='', exam_type='end_sem', grading_context=None):
        """Run Gemini evaluation with result caching."""
        # Include exam_type and grading_context in hash for cache differentiation
        eval_input = f"{student_text}|||{model_text}|||{max_marks}|||{exam_type}"
        eval_hash = hashlib.sha256(eval_input.encode('utf-8')).hexdigest()
        eval_cache_file = os.path.join(self.cache_dir, f'eval_{eval_hash}.json')

        if os.path.exists(eval_cache_file):
            logger.info(f"  Evaluation cache HIT ({eval_hash[:12]}...)")
            with open(eval_cache_file, 'r', encoding='utf-8') as ecf:
                return json.load(ecf)

        logger.info(f"  Evaluation cache MISS — calling Gemini grading...")
        result = self.gemini_service.evaluate_answer(
            student_text, model_text, max_marks, question,
            exam_type=exam_type, grading_context=grading_context
        )

        # Protect against caching internal errors.
        # If the result is a JSON/API error fallback, it's flagged with 'needs_review' and an error payload.
        if result.get('status') == 'error' or (result.get('marks_awarded') == 0 and "Evaluation error" in result.get('feedback', '')):
            logger.warning(f"  Refusing to cache failed evaluation result")
        else:
            # Save to cache only if it's a legitimate grading output
            with open(eval_cache_file, 'w', encoding='utf-8') as ecf:
                json.dump(result, ecf, ensure_ascii=False, indent=2)
            logger.info(f"  Cached evaluation result ({eval_hash[:12]}...)")

        return result

    # ==================== PROGRESS TRACKING (RESUME) ====================

    def _get_progress_file(self, root_directory, course_code):
        """Get path to progress file for a course."""
        progress_dir = os.path.join(root_directory, '.progress')
        os.makedirs(progress_dir, exist_ok=True)
        return os.path.join(progress_dir, f'{course_code}_progress.json')

    def _load_progress(self, root_directory, course_code):
        """Load progress for a course. Returns set of completed roll numbers."""
        completed = set()
        progress_file = self._get_progress_file(root_directory, course_code)
        
        # Load from disk (if the user hasn't deleted .progress)
        if os.path.exists(progress_file):
            try:
                with open(progress_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                completed.update(data.get('completed', []))
            except (json.JSONDecodeError, IOError):
                pass
                
        # CRITICAL: Verify with Database! 
        # Only skip students who actually exist in the DB and are successfully graded (not flagged for review)
        try:
            from models.evaluation import Evaluation
            db_evals = Evaluation.find_by_course(course_code)
            
            # Rebuild a true representation of absolute completed rolls
            db_completed = set()
            for db_eval in db_evals:
                # If they actually got marks or passed successfully without triggering review/errors, they are done.
                if db_eval.get('status') != 'error' and not db_eval.get('needs_review', False):
                    db_completed.add(db_eval.get('roll_number'))
                    
            # If the user wiped the corrupted 0s from the DB, we MUST remove them from the 'completed' set 
            # so the pipeline is forced to evaluate them again, even if the .progress file still thinks they are done
            # We ONLY consider it completed if it is both in the DB as complete, OR we recently did it.
            # Actually, to be extremely robust, just union the DB completes and ignore the disk if DB disagrees
            completed = db_completed
            
        except Exception as e:
            logger.error(f"Failed to query DB for progress: {e}")
            
        return completed

    def _save_progress(self, root_directory, course_code, completed_rolls, results):
        """Save progress after each student evaluation."""
        progress_file = self._get_progress_file(root_directory, course_code)
        data = {
            'course_code': course_code,
            'completed': list(completed_rolls),
            'total_completed': len(completed_rolls),
            'last_results': [
                {
                    'roll_number': r['roll_number'],
                    'marks_awarded': r.get('evaluation_result', {}).get('marks_awarded', 0),
                    'grade': r.get('evaluation_result', {}).get('grade', 'N/A'),
                    'status': r.get('status', 'unknown')
                }
                for r in results if r.get('status') == 'completed'
            ]
        }
        with open(progress_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ==================== LEARNING MECHANISM ====================

    def _build_learning_context(self, completed_results):
        """
        Build grading calibration context from completed evaluations.
        Called every 3 completed evaluations to provide consistency context.
        """
        if len(completed_results) < 3:
            return None

        marks_list = []
        grade_counts = {}
        for r in completed_results:
            ev = r.get('evaluation_result', {})
            marks = ev.get('marks_awarded', 0)
            grade = ev.get('grade', 'N/A')
            marks_list.append(marks)
            grade_counts[grade] = grade_counts.get(grade, 0) + 1

        avg_marks = sum(marks_list) / len(marks_list)
        min_marks = min(marks_list)
        max_marks_val = max(marks_list)

        context = f"""Previously graded {len(completed_results)} students in this course:
- Average marks: {avg_marks:.1f}
- Range: {min_marks} to {max_marks_val}
- Grade distribution: {', '.join(f'{g}: {c}' for g, c in sorted(grade_counts.items()))}
- Recent scores: {', '.join(str(m) for m in marks_list[-5:])}
Maintain consistency with these patterns while grading independently."""

        return context

    # ==================== MAIN EVALUATION ====================

    def evaluate_course(self, course_code, model_answer_path, student_sheets, max_marks,
                        question='', exam_type='end_sem', root_directory=None,
                        cancel_event=None, on_student_complete=None, max_workers=3):
        """
        Evaluate all student sheets for a single course in parallel.
        """
        results = []
        total_students = len(student_sheets)

        logger.info(f"[{course_code}] Starting evaluation — {total_students} students, "
                     f"max_marks={max_marks}, exam_type={exam_type}")

        # Shared state for progress & learning (needs locks)
        state_lock = threading.Lock()
        completed_rolls = set()
        completed_for_learning = []
        skipped_count = 0
        grading_context = None

        if root_directory:
            completed_rolls = self._load_progress(root_directory, course_code)
            if completed_rolls:
                skipped_count = len([s for s in student_sheets if s['roll_number'] in completed_rolls])
                logger.info(f"[{course_code}] Resuming — {len(completed_rolls)} already completed "
                            f"(Skipping {skipped_count} for this run)")

        # Step 1: Extract model answer text
        logger.info(f"[{course_code}] Extracting model answer text...")
        try:
            model_text = self._extract_text_cached(model_answer_path)
        except Exception as e:
            logger.error(f"[{course_code}] FATAL: Failed to extract model answer: {e}")
            error_result = {
                'course_code': course_code,
                'roll_number': 'N/A',
                'status': 'error',
                'error': f"Failed to extract model answer: {str(e)}"
            }
            if on_student_complete:
                on_student_complete(course_code, error_result)
            return [error_result]

        def process_student(student, idx):
            nonlocal grading_context

            if cancel_event and cancel_event.is_set():
                return None

            roll_number = student['roll_number']
            file_path = student['file_path']

            if roll_number in completed_rolls:
                return None  # Skipped

            logger.info(f"[{course_code}] Processing {idx + 1}/{total_students}: Roll #{roll_number}")

            try:
                # Capture current grading context thread-safely
                with state_lock:
                    current_context = grading_context

                student_text = self._extract_text_cached(file_path)
                evaluation_result = self._evaluate_cached(
                    student_text, model_text, max_marks, question,
                    exam_type=exam_type, grading_context=current_context
                )

                result = {
                    'course_code': course_code,
                    'roll_number': roll_number,
                    'status': 'completed',
                    'model_answer_text': model_text,
                    'student_answer_text': student_text,
                    'evaluation_result': evaluation_result,
                    'max_marks': max_marks
                }

                # Thread-safe updates to shared state
                with state_lock:
                    results.append(result)
                    completed_rolls.add(roll_number)
                    completed_for_learning.append(result)
                    
                    if root_directory:
                        self._save_progress(root_directory, course_code, completed_rolls, results)

                    if len(completed_for_learning) % 3 == 0:
                        grading_context = self._build_learning_context(completed_for_learning)
                        logger.info(f"[{course_code}] Learning context updated "
                                    f"(based on {len(completed_for_learning)} evaluations)")

                if on_student_complete:
                    on_student_complete(course_code, result)

                return result

            except Exception as e:
                logger.error(f"[{course_code}] Roll #{roll_number} FAILED: {e}")
                error_result = {
                    'course_code': course_code,
                    'roll_number': roll_number,
                    'status': 'error',
                    'error': str(e),
                    'max_marks': max_marks
                }
                with state_lock:
                    results.append(error_result)
                if on_student_complete:
                    on_student_complete(course_code, error_result)
                return error_result

        # Process all students concurrently using thread pool
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for idx, student in enumerate(student_sheets):
                if cancel_event and cancel_event.is_set():
                    break
                if student['roll_number'] in completed_rolls:
                    continue
                futures.append(executor.submit(process_student, student, idx))
                
            for future in as_completed(futures):
                if cancel_event and cancel_event.is_set():
                    break
                future.result()  # Surface any unhandled thread exceptions

        completed = sum(1 for r in results if r.get('status') == 'completed')
        failed = sum(1 for r in results if r.get('status') == 'error')
        logger.info(
            f"[{course_code}] Evaluation complete: "
            f"{completed} succeeded, {failed} failed, {skipped_count} skipped (resumed) "
            f"out of {total_students}"
        )

        return results
