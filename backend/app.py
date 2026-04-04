from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from config import Config
from utils.pdf_processor import PDFProcessor
from utils.gemini_service import GeminiService
from utils.db_connection import db, db_connection
from models.teacher import Teacher
from models.student import Student
from models.evaluation import Evaluation
from bson import ObjectId
import os
import json
import hashlib
import logging
import threading
import queue

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configure CORS for both development and production
cors_origins = [
    'http://localhost:3000',  # Local development
    'http://localhost:5000',
    os.getenv('FRONTEND_URL', 'http://localhost:3000')  # Production Vercel URL
]
CORS(app, origins=cors_origins)

# Setup persistent auditing logs
from utils.logger_setup import LoggerSetup
logger = LoggerSetup.setup_app_logger()

# Configuration
app.config['UPLOAD_FOLDER'] = Config.UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = Config.MAX_FILE_SIZE

# Initialize services
pdf_processor = PDFProcessor()
gemini_service = GeminiService(Config.GEMINI_API_KEYS, deepseek_api_key=Config.DEEPSEEK_API_KEY)

# Helper function to serialize MongoDB documents
def serialize_doc(doc):
    """Convert MongoDB document to JSON serializable format"""
    if doc is None:
        return None
    if isinstance(doc, list):
        return [serialize_doc(item) for item in doc]
    if isinstance(doc, dict):
        doc = doc.copy()
        if '_id' in doc:
            doc['_id'] = str(doc['_id'])
        return doc
    return doc

@app.route('/', methods=['GET'])
def root():
    """Root endpoint - API info"""
    return jsonify({
        'message': 'AI Examiner API',
        'version': '1.0',
        'health_check': '/api/health'
    })

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        db_connection.get_db().command('ping')
        db_status = 'connected'
    except Exception as e:
        db_status = f'disconnected: {str(e)}'
    
    return jsonify({
        'status': 'healthy',
        'message': 'AI Examiner API is running',
        'database': db_status
    })

# ==================== TEACHER ROUTES ====================

@app.route('/api/teachers', methods=['POST'])
def create_teacher():
    """Create a new teacher"""
    try:
        data = request.json
        name = data.get('name')
        email = data.get('email')
        subject = data.get('subject')
        
        if not name or not email:
            return jsonify({'error': 'Name and email are required'}), 400
        
        # Check if teacher already exists
        existing = Teacher.find_by_email(email)
        if existing:
            return jsonify({'error': 'Teacher with this email already exists'}), 400
        
        teacher = Teacher.create(name, email, subject)
        return jsonify({
            'success': True,
            'teacher': serialize_doc(teacher)
        }), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/teachers/<teacher_id>', methods=['GET'])
def get_teacher(teacher_id):
    """Get teacher by ID"""
    try:
        teacher = Teacher.find_by_id(teacher_id)
        if not teacher:
            return jsonify({'error': 'Teacher not found'}), 404
        
        return jsonify({
            'success': True,
            'teacher': serialize_doc(teacher)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/teachers', methods=['GET'])
def get_all_teachers():
    """Get all teachers"""
    try:
        teachers = Teacher.get_all()
        return jsonify({
            'success': True,
            'teachers': serialize_doc(teachers),
            'count': len(teachers)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== STUDENT ROUTES ====================

@app.route('/api/students', methods=['POST'])
def create_student():
    """Create a new student"""
    try:
        data = request.json
        name = data.get('name')
        email = data.get('email')
        roll_number = data.get('roll_number')
        class_name = data.get('class')
        
        if not name or not email:
            return jsonify({'error': 'Name and email are required'}), 400
        
        # Check if student already exists
        existing = Student.find_by_email(email)
        if existing:
            return jsonify({'error': 'Student with this email already exists'}), 400
        
        student = Student.create(name, email, roll_number, class_name)
        return jsonify({
            'success': True,
            'student': serialize_doc(student)
        }), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/students/<student_id>', methods=['GET'])
def get_student(student_id):
    """Get student by ID"""
    try:
        student = Student.find_by_id(student_id)
        if not student:
            return jsonify({'error': 'Student not found'}), 404
        
        return jsonify({
            'success': True,
            'student': serialize_doc(student)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/students', methods=['GET'])
def get_all_students():
    """Get all students"""
    try:
        students = Student.get_all()
        return jsonify({
            'success': True,
            'students': serialize_doc(students),
            'count': len(students)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/students/<student_id>/statistics', methods=['GET'])
def get_student_statistics(student_id):
    """Get statistics for a student"""
    try:
        stats = Evaluation.get_student_statistics(student_id)
        if not stats:
            return jsonify({
                'success': True,
                'statistics': {
                    'total_evaluations': 0,
                    'average_marks': 0,
                    'average_percentage': 0
                }
            })
        
        return jsonify({
            'success': True,
            'statistics': serialize_doc(stats)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/teachers/<teacher_id>', methods=['DELETE'])
def delete_teacher(teacher_id):
    """Delete a teacher"""
    try:
        Teacher.delete(teacher_id)
        return jsonify({'success': True, 'message': 'Teacher deleted successfully'})
    except Exception as e:
        logger.error(f"Error deleting teacher: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/students/<student_id>', methods=['DELETE'])
def delete_student(student_id):
    """Delete a student"""
    try:
        Student.delete(student_id)
        return jsonify({'success': True, 'message': 'Student deleted successfully'})
    except Exception as e:
        logger.error(f"Error deleting student: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ==================== EVALUATION ROUTES ====================

@app.route('/api/upload-model-answer', methods=['POST'])
def upload_model_answer():
    """Handle model answer upload"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not Config.allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type. Only PDF allowed.'}), 400
        
        # Save file
        file_path = pdf_processor.save_uploaded_file(file, app.config['UPLOAD_FOLDER'])
        
        # --- OCR TEXT CACHING for model answer ---
        cache_dir = os.path.join(os.path.dirname(__file__), 'cache')
        os.makedirs(cache_dir, exist_ok=True)
        
        with open(file_path, 'rb') as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()
        
        cache_file = os.path.join(cache_dir, f'{file_hash}.txt')
        
        if os.path.exists(cache_file):
            logger.info(f"Cache HIT for model answer hash {file_hash[:12]}...")
            with open(cache_file, 'r', encoding='utf-8') as cf:
                text = cf.read()
        else:
            logger.info(f"Cache MISS for model answer hash {file_hash[:12]}... Extracting text.")
            text = pdf_processor.extract_text_from_pdf(file_path)
            if len(text.strip()) < 50:
                logger.info("Insufficient text in model answer extraction, using Gemini vision API...")
                images = pdf_processor.convert_pdf_to_images(file_path, max_pages=36)
                text = pdf_processor.extract_text_from_images_via_gemini(images, gemini_service)
            
            # Save to cache
            with open(cache_file, 'w', encoding='utf-8') as cf:
                cf.write(text)
            logger.info(f"Cached model answer text to {cache_file}")
        
        # Clean up
        os.remove(file_path)
        
        return jsonify({
            'success': True,
            'model_answer': text,
            'message': 'Model answer uploaded successfully'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/evaluate-answer', methods=['POST'])
def evaluate_answer():
    """Evaluate student answer against model answer and store in database"""
    try:
        # Validate inputs
        if 'student_file' not in request.files:
            return jsonify({'error': 'No student file provided'}), 400
        
        student_file = request.files['student_file']
        model_answer = request.form.get('model_answer')
        max_marks = request.form.get('max_marks')
        question = request.form.get('question', '')
        teacher_id = request.form.get('teacher_id')
        student_id = request.form.get('student_id')
        
        if not model_answer or not max_marks:
            return jsonify({'error': 'Model answer and max marks are required'}), 400
        
        if not Config.allowed_file(student_file.filename):
            return jsonify({'error': 'Invalid file type'}), 400
        
        # Convert max_marks to integer
        try:
            max_marks = int(max_marks)
        except ValueError:
            return jsonify({'error': 'Invalid max marks value'}), 400
        
        # Fetch teacher and student info for storing in evaluation
        teacher_name = 'Unknown'
        student_name = 'Unknown'
        student_rollno = 'N/A'
        
        if teacher_id:
            teacher = Teacher.find_by_id(teacher_id)
            if teacher:
                teacher_name = teacher.get('name', 'Unknown')
        
        if student_id:
            student = Student.find_by_id(student_id)
            if student:
                student_name = student.get('name', 'Unknown')
                student_rollno = student.get('roll_number', 'N/A')
        
        # Save student file
        student_file_path = pdf_processor.save_uploaded_file(
            student_file, 
            app.config['UPLOAD_FOLDER']
        )
        
        # --- OCR TEXT CACHING ---
        # Generate a unique hash of the uploaded file to check for cached OCR text.
        # If the same file has been processed before, we reuse the cached text
        # to guarantee identical grading results on repeated evaluations.
        cache_dir = os.path.join(os.path.dirname(__file__), 'cache')
        os.makedirs(cache_dir, exist_ok=True)
        
        with open(student_file_path, 'rb') as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()
        
        cache_file = os.path.join(cache_dir, f'{file_hash}.txt')
        
        if os.path.exists(cache_file):
            # Cache HIT - use previously extracted text
            logger.info(f"Cache HIT for file hash {file_hash[:12]}... Loading cached OCR text.")
            with open(cache_file, 'r', encoding='utf-8') as cf:
                student_text = cf.read()
        else:
            # Cache MISS - extract text and save to cache
            logger.info(f"Cache MISS for file hash {file_hash[:12]}... Extracting text.")
            try:
                student_text = pdf_processor.extract_text_from_pdf(student_file_path)
                if len(student_text.strip()) < 100:
                    # Not enough text extracted, use Gemini vision
                    logger.info("Insufficient text from extraction, using Gemini vision API...")
                    images = pdf_processor.convert_pdf_to_images(student_file_path, max_pages=36)
                    student_text = pdf_processor.extract_text_from_images_via_gemini(images, gemini_service)
            except Exception as extract_error:
                logger.warning(f"Text extraction failed: {str(extract_error)}, using Gemini vision...")
                images = pdf_processor.convert_pdf_to_images(student_file_path, max_pages=36)
                student_text = pdf_processor.extract_text_from_images_via_gemini(images, gemini_service)
            
            # Save extracted text to cache
            with open(cache_file, 'w', encoding='utf-8') as cf:
                cf.write(student_text)
            logger.info(f"Cached OCR text to {cache_file}")
        
        # --- EVALUATION RESULT CACHING ---
        # Hash the combination of student text + model answer + max marks
        # to guarantee identical results for identical inputs.
        eval_input = f"{student_text}|||{model_answer}|||{max_marks}"
        eval_hash = hashlib.sha256(eval_input.encode('utf-8')).hexdigest()
        eval_cache_file = os.path.join(cache_dir, f'eval_{eval_hash}.json')
        
        if os.path.exists(eval_cache_file):
            # Evaluation cache HIT - return the exact same result
            logger.info(f"Evaluation cache HIT for hash {eval_hash[:12]}... Returning cached grade.")
            import json
            with open(eval_cache_file, 'r', encoding='utf-8') as ecf:
                evaluation_result = json.load(ecf)
        else:
            # Evaluation cache MISS - run Gemini grading
            logger.info(f"Evaluation cache MISS for hash {eval_hash[:12]}... Running Gemini grading.")
            evaluation_result = gemini_service.evaluate_answer(
                student_text, 
                model_answer, 
                max_marks,
                question
            )
            
            # Save evaluation result to cache
            import json
            with open(eval_cache_file, 'w', encoding='utf-8') as ecf:
                json.dump(evaluation_result, ecf, ensure_ascii=False, indent=2)
            logger.info(f"Cached evaluation result to {eval_cache_file}")
        
        # Store evaluation in database
        evaluation_doc = Evaluation.create(
            teacher_id=teacher_id,
            student_id=student_id,
            question=question,
            model_answer=model_answer,
            student_answer=student_file.filename,
            extracted_text=student_text,
            max_marks=max_marks,
            evaluation_result=evaluation_result,
            teacher_name=teacher_name,
            student_name=student_name,
            student_rollno=student_rollno
        )
        
        # Add extracted text to response
        evaluation_result['extracted_text'] = student_text
        evaluation_result['evaluation_id'] = str(evaluation_doc['_id'])
        
        # Clean up
        os.remove(student_file_path)
        
        return jsonify({
            'success': True,
            'evaluation': evaluation_result
        })
        
    except Exception as e:
        logger.error(f"Evaluation error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/evaluations', methods=['GET'])
def get_all_evaluations():
    """Get all evaluations"""
    try:
        evaluations = Evaluation.get_all()
        if not evaluations:
            return jsonify([])
        
        return jsonify([serialize_doc(e) for e in evaluations])
    except Exception as e:
        logger.error(f"Error fetching evaluations: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/evaluations/<evaluation_id>', methods=['GET'])
def get_evaluation(evaluation_id):
    """Get evaluation by ID"""
    try:
        evaluation = Evaluation.find_by_id(evaluation_id)
        if not evaluation:
            return jsonify({'error': 'Evaluation not found'}), 404
        
        return jsonify({
            'success': True,
            'evaluation': serialize_doc(evaluation)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/evaluations/<evaluation_id>/manual', methods=['PUT'])
def update_manual_evaluation(evaluation_id):
    """Manually grade an evaluation that needed review"""
    try:
        from bson.objectid import ObjectId
        data = request.json
        if not data or 'marks_awarded' not in data:
            return jsonify({'error': 'Missing marks_awarded'}), 400
            
        marks = float(data['marks_awarded'])
        feedback = data.get('feedback', 'Manually Graded')
        
        db.evaluations.update_one(
            {'_id': ObjectId(evaluation_id)},
            {
                '$set': {
                    'evaluation_result.marks_awarded': marks,
                    'evaluation_result.feedback': feedback,
                    'evaluation_result.needs_review': False,
                    'status': 'completed_manually'
                }
            }
        )
        return jsonify({'success': True, 'message': 'Manual grade saved'})
    except Exception as e:
        logger.error(f"Error saving manual grade: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/evaluations/student/<student_id>', methods=['GET'])
def get_student_evaluations(student_id):
    """Get all evaluations for a student"""
    try:
        limit = request.args.get('limit', 10, type=int)
        evaluations = Evaluation.find_by_student(student_id, limit)
        
        return jsonify({
            'success': True,
            'evaluations': serialize_doc(evaluations),
            'count': len(evaluations)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/evaluations/teacher/<teacher_id>', methods=['GET'])
def get_teacher_evaluations(teacher_id):
    """Get all evaluations by a teacher"""
    try:
        limit = request.args.get('limit', 10, type=int)
        evaluations = Evaluation.find_by_teacher(teacher_id, limit)
        
        return jsonify({
            'success': True,
            'evaluations': serialize_doc(evaluations),
            'count': len(evaluations)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/evaluations/recent', methods=['GET'])
def get_recent_evaluations():
    """Get recent evaluations"""
    try:
        limit = request.args.get('limit', 20, type=int)
        evaluations = Evaluation.get_recent_evaluations(limit)
        
        return jsonify({
            'success': True,
            'evaluations': serialize_doc(evaluations),
            'count': len(evaluations)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/evaluations/<evaluation_id>', methods=['DELETE'])
def delete_evaluation(evaluation_id):
    """Delete an evaluation"""
    try:
        result = Evaluation.delete(evaluation_id)
        
        if result.deleted_count == 0:
            return jsonify({'error': 'Evaluation not found'}), 404
        
        return jsonify({
            'success': True,
            'message': 'Evaluation deleted successfully'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ocr-only', methods=['POST'])
def ocr_only():
    """Extract text from handwritten PDF without evaluation"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        
        if not Config.allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type'}), 400
        
        # Save and process file
        file_path = pdf_processor.save_uploaded_file(file, app.config['UPLOAD_FOLDER'])
        extracted_text = pdf_processor.extract_text_from_pdf(file_path)
        
        # Clean up
        os.remove(file_path)
        
        return jsonify({
            'success': True,
            'extracted_text': extracted_text
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== BATCH PROCESSING ROUTES ====================

# Global references for batch processing
_batch_manager = None
_batch_event_queue = queue.Queue()
_batch_processing = False
_batch_thread = None


def _store_result_in_db(result):
    """Store a single evaluation result in the database, avoiding duplicates."""
    status = result.get('status')
    if status not in ('completed', 'error'):
        return False
        
    try:
        # Check for existing evaluation to avoid duplicates on resume
        existing = Evaluation.find_by_course_and_roll(
            result['course_code'], result['roll_number']
        )
        if existing:
            logger.info(f"DB: Skipping duplicate {result['course_code']}/{result['roll_number']}")
            return False

        # Build evaluation_result object safely
        if status == 'completed':
            eval_res = result['evaluation_result']
        else:
            eval_res = {
                "marks_awarded": 0,
                "percentage": 0,
                "strengths": [],
                "missing_points": ["System Error Occurred"],
                "feedback": result.get('error', 'Unknown Error'),
                "grade": "N/A",
                "needs_review": True
            }

        Evaluation.create_batch(
            course_code=result['course_code'],
            roll_number=result['roll_number'],
            model_answer=result.get('model_answer_text', '')[:5000],
            student_answer=result.get('student_answer_text', '')[:5000],
            extracted_text=result.get('student_answer_text', ''),
            max_marks=result['max_marks'],
            evaluation_result=eval_res
        )
        
        # If it was an error, make sure the top-level DB status reflects that it needs manual intervention
        if status == 'error':
            from bson.objectid import ObjectId
            # Update the status to 'error' instead of completed
            latest = db.evaluations.find_one({
                'course_code': result['course_code'],
                'roll_number': result['roll_number']
            }, sort=[('_id', -1)])
            
            if latest:
                db.evaluations.update_one(
                    {'_id': latest['_id']},
                    {'$set': {'status': 'error', 'needs_review': True}}
                )
                
        return True
    except Exception as db_err:
        logger.error(f"DB store failed for {result.get('course_code')}/{result.get('roll_number')}: {db_err}")
        return False


def _on_student_complete(course_code, result):
    """Callback fired when a single student evaluation completes."""
    # Store in DB immediately
    _store_result_in_db(result)

    # Push event to SSE queue for real-time streaming
    event_data = {
        'type': 'student_complete',
        'course_code': course_code,
        'roll_number': result.get('roll_number', 'N/A'),
        'status': result.get('status', 'unknown'),
        'marks_awarded': result.get('evaluation_result', {}).get('marks_awarded', 0),
        'percentage': result.get('evaluation_result', {}).get('percentage', 0),
        'grade': result.get('evaluation_result', {}).get('grade', 'N/A'),
        'error': result.get('error', ''),
        'needs_review': result.get('evaluation_result', {}).get('needs_review', False)
    }
    _batch_event_queue.put(event_data)


def _run_batch_processing(root_directory, parallel, max_workers, max_marks, exam_type):
    """Background thread function for batch processing."""
    global _batch_manager, _batch_processing

    try:
        # Step 1: Discover courses
        logger.info(f"Batch processing: scanning {root_directory}...")
        from utils.course_processor import CourseProcessor
        processor = CourseProcessor(root_directory, max_marks=max_marks)
        courses, effective_max_marks = processor.discover_courses()

        logger.info(f"Discovered {len(courses)} courses with max_marks={effective_max_marks}")

        # Send discovery event
        _batch_event_queue.put({
            'type': 'courses_discovered',
            'total_courses': len(courses),
            'max_marks': effective_max_marks,
            'course_codes': list(courses.keys()),
            'course_details': {
                code: {'student_count': len(info['student_sheets'])}
                for code, info in courses.items()
            }
        })

        # Step 2: Process courses
        from utils.multithreading_manager import MultithreadingManager
        _batch_manager = MultithreadingManager(pdf_processor, gemini_service, max_workers=max_workers)
        _batch_manager.set_on_student_complete(_on_student_complete)

        if parallel:
            all_results = _batch_manager.process_courses_parallel(
                courses, effective_max_marks, exam_type=exam_type, root_directory=root_directory
            )
        else:
            all_results = _batch_manager.process_courses_sequential(
                courses, effective_max_marks, exam_type=exam_type, root_directory=root_directory
            )

        # Build final summary
        total_students = 0
        total_completed = 0
        total_failed = 0
        for course_code, results in all_results.items():
            total_students += len(results)
            total_completed += sum(1 for r in results if r.get('status') == 'completed')
            total_failed += sum(1 for r in results if r.get('status') == 'error')

        cancelled = _batch_manager.is_cancelled()
        _batch_event_queue.put({
            'type': 'batch_complete',
            'cancelled': cancelled,
            'total_courses': len(all_results),
            'total_students': total_students,
            'total_completed': total_completed,
            'total_failed': total_failed,
            'max_marks': effective_max_marks
        })

    except Exception as e:
        logger.error(f"Batch processing error: {str(e)}")
        import traceback
        traceback.print_exc()
        _batch_event_queue.put({
            'type': 'batch_error',
            'error': str(e)
        })
    finally:
        _batch_processing = False


@app.route('/api/batch/process-courses', methods=['POST'])
def batch_process_courses():
    """Start batch processing in a background thread."""
    global _batch_processing, _batch_thread, _batch_event_queue

    if _batch_processing:
        return jsonify({'error': 'Batch processing is already running'}), 409

    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Request body is required'}), 400

        root_directory = data.get('root_directory')
        parallel = data.get('parallel', True)
        max_workers = data.get('max_workers', Config.BATCH_PROCESSING_MAX_WORKERS)
        max_marks = data.get('max_marks')  # From UI (optional)
        exam_type = data.get('exam_type', 'end_sem')  # 'mst' or 'end_sem'

        if not root_directory:
            return jsonify({'error': 'root_directory is required'}), 400

        if not os.path.isdir(root_directory):
            return jsonify({'error': f'Directory not found: {root_directory}'}), 400

        # Convert max_marks to int if provided
        if max_marks is not None:
            try:
                max_marks = int(max_marks)
            except (ValueError, TypeError):
                return jsonify({'error': 'Invalid max_marks value'}), 400

        # Clear the event queue for a fresh run
        while not _batch_event_queue.empty():
            try:
                _batch_event_queue.get_nowait()
            except queue.Empty:
                break

        _batch_processing = True

        # Start background thread
        _batch_thread = threading.Thread(
            target=_run_batch_processing,
            args=(root_directory, parallel, max_workers, max_marks, exam_type),
            daemon=True
        )
        _batch_thread.start()

        return jsonify({
            'success': True,
            'message': 'Batch processing started',
            'exam_type': exam_type,
            'stream_url': '/api/batch/stream'
        })

    except Exception as e:
        _batch_processing = False
        logger.error(f"Batch start error: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/batch/stream', methods=['GET'])
def batch_stream():
    """Server-Sent Events stream for real-time batch processing updates."""
    def event_generator():
        while True:
            try:
                event = _batch_event_queue.get(timeout=30)
                yield f"data: {json.dumps(event)}\n\n"

                # Stop streaming after batch completes or errors
                if event.get('type') in ('batch_complete', 'batch_error'):
                    break
            except queue.Empty:
                # Send heartbeat to keep connection alive
                yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"

    return Response(
        event_generator(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Access-Control-Allow-Origin': '*'
        }
    )


@app.route('/api/batch/stop', methods=['POST'])
def batch_stop():
    """Stop the currently running batch processing."""
    global _batch_manager
    if _batch_manager is None or not _batch_processing:
        return jsonify({'error': 'No batch processing in progress'}), 400

    _batch_manager.cancel()
    return jsonify({
        'success': True,
        'message': 'Stop signal sent. Currently processing students will finish, then batch will stop.'
    })


@app.route('/api/batch/status', methods=['GET'])
def batch_status():
    """Get current batch processing status."""
    global _batch_manager, _batch_processing
    if _batch_manager is None:
        return jsonify({'status': 'idle', 'message': 'No batch processing in progress'})

    return jsonify({
        'status': 'processing' if _batch_processing else 'idle',
        'courses': _batch_manager.get_status()
    })


@app.route('/api/batch/results', methods=['GET'])
def batch_results():
    """Get all batch evaluation results."""
    try:
        evaluations = Evaluation.get_batch_evaluations(limit=500)

        # Group by course code
        courses = {}
        for ev in evaluations:
            code = ev.get('course_code', 'Unknown')
            if code not in courses:
                courses[code] = []
            courses[code].append(serialize_doc(ev))

        return jsonify({
            'success': True,
            'total_evaluations': len(evaluations),
            'courses': courses
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/batch/results/<course_code>', methods=['GET'])
def batch_results_by_course(course_code):
    """Get batch results for a specific course."""
    try:
        evaluations = Evaluation.find_by_course(course_code)
        stats = Evaluation.get_course_statistics(course_code)

        return jsonify({
            'success': True,
            'course_code': course_code,
            'evaluations': serialize_doc(evaluations),
            'statistics': serialize_doc(stats) if stats else None,
            'count': len(evaluations)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Validate required environment variables
    required_vars = ['GEMINI_API_KEY', 'MONGO_URI']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        raise RuntimeError(f"Missing environment variables: {', '.join(missing_vars)}")
    
    # Create uploads folder if it doesn't exist
    if not os.path.exists(Config.UPLOAD_FOLDER):
        os.makedirs(Config.UPLOAD_FOLDER)
    
    try:
        # Test database connection on startup
        logger.info("Testing database connection...")
        db_connection.connect()
        logger.info("Database connection successful")
        
        app.run(debug=True, host='0.0.0.0', port=5000)
    finally:
        # Close database connection on shutdown
        db_connection.close()

