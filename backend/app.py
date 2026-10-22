from flask import Flask, request, jsonify, Response, g
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
import jwt
import datetime
import shutil
import tempfile
from functools import wraps
from utils.workspace import safe_path
from access import account, authorize, is_admin
from werkzeug.exceptions import HTTPException
from utils.result_validation import validate_result, ReviewRequired
from utils.api_contract import json_object, validate_request
from pymongo.errors import PyMongoError
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configure CORS for both development and production
cors_origins = [
    'http://localhost:3000',  # Local development
    'http://localhost:3001',  # Local development when port 3000 is occupied
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
# Legacy folder uploads contain one file and one path field per document.
app.config['MAX_FORM_PARTS'] = 2100

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
        if 'marks' in doc and 'max_marks' in doc:
            from utils.verification import revision
            doc['verification_revision'] = revision(doc)
        if doc.get('batch_mode') and not doc.get('status'):
            doc.update(status='needs_review', needs_review=True)
        if str(doc.get('feedback', '')).startswith(('Error during evaluation:', 'Evaluation error')):
            doc.update(status='error', needs_review=True, marks=None, percentage=None, grade=None)
        if '_id' in doc:
            doc['_id'] = str(doc['_id'])
        return doc
    return doc

# ==================== AUTH HELPERS ====================

def require_auth(f):
    """Decorator to require JWT authentication on routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = None
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header.split(' ', 1)[1]

        if not token:
            return jsonify({'error': 'Authentication required'}), 401

        try:
            payload = jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=['HS256'])
            if payload.get('provider') != 'google':
                return jsonify(error='Sign in with Google again'), 401
            g.user_email = payload.get('email')
            g.user = account(db_connection.get_db(), g.user_email)
            if not g.user:
                return jsonify(error='Your account is not enabled. Contact the administrator.'), 403
            if not is_admin() and not (request.path.startswith('/api/workspace/') or request.path.startswith('/api/access') or request.path in ('/api/auth/me', '/api/batch/upload-folder')):
                return jsonify(error='Administrator access required'), 403
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401

        validate_request()
        return f(*args, **kwargs)
    return decorated_function


# ==================== AUTH ROUTES ====================

@app.errorhandler(HTTPException)
def http_error(error):
    return jsonify(error=error.description), error.code



@app.errorhandler(PyMongoError)
@app.errorhandler(RuntimeError)
def storage_unavailable(error):
    logger.error('Storage operation unavailable: %s', type(error).__name__)
    return jsonify(error='Persistent storage is unavailable. Refresh before retrying.'), 503


def api_failure(error):
    if isinstance(error, HTTPException):
        return http_error(error)
    if isinstance(error, ReviewRequired):
        return jsonify(error=str(error), needs_review=True), 422
    if isinstance(error, (PyMongoError, RuntimeError)):
        return storage_unavailable(error)
    if isinstance(error, (requests.exceptions.Timeout, requests.exceptions.ConnectionError)):
        return jsonify(error='The model server is temporarily unavailable. Please retry.'), 503
    if isinstance(error, ValueError):
        return jsonify(error=str(error)), 400
    logger.exception('API request failed')
    return jsonify(error='The request could not be completed. Contact the administrator.'), 500

@app.route('/api/auth/config')
def auth_config():
    return jsonify(client_id=Config.GOOGLE_CLIENT_ID)


@app.route('/api/auth/login', methods=['POST'])
def auth_login():
    return jsonify(error='Password login is disabled. Sign in with Google.'), 410


@app.route('/api/auth/google', methods=['POST'])
def auth_google():
    from google.oauth2 import id_token
    from google.auth.transport.requests import Request
    from google.auth.exceptions import TransportError
    if not Config.GOOGLE_CLIENT_ID:
        return jsonify(error='Google sign-in has not been configured by the administrator.'), 503
    from pymongo import ReturnDocument
    limits = db_connection.get_db().login_limits
    limits.create_index('expires', expireAfterSeconds=0)
    timestamp = datetime.datetime.now(datetime.timezone.utc)
    bucket = timestamp.strftime('%Y%m%d%H%M')
    rate = limits.find_one_and_update({'_id': f'{request.remote_addr}:{bucket}'},
        {'$inc': {'count': 1}, '$setOnInsert': {'expires': timestamp + datetime.timedelta(minutes=2)}},
        upsert=True, return_document=ReturnDocument.AFTER)
    if rate['count'] > 10:
        return jsonify(error='Too many login attempts; try again in a minute'), 429
    credential = json_object().get('credential')
    if not isinstance(credential, str) or len(credential) > 10000:
        return jsonify(error='A Google credential is required'), 400
    try:
        identity = id_token.verify_oauth2_token(credential, Request(), Config.GOOGLE_CLIENT_ID)
        if identity.get('email_verified') is not True:
            raise ValueError('Unverified email')
    except ValueError:
        return jsonify(error='Google sign-in could not be verified'), 401
    except TransportError:
        return jsonify(error='Google is temporarily unavailable. Please try again.'), 503
    email = identity.get('email', '').strip().lower()
    database = db_connection.get_db()
    user = account(database, email)
    if not user:
        return jsonify(error='This email has not been approved by the administrator.'), 403
    token = jwt.encode({'email': email, 'provider': 'google',
        'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=8)},
        Config.JWT_SECRET_KEY, algorithm='HS256')
    return jsonify(token=token, user=user)


@app.route('/api/auth/me', methods=['GET'])
@require_auth
def auth_me():
    return jsonify(user=g.user)


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
        db_status = 'disconnected'

    return jsonify({
        'status': 'healthy' if db_status == 'connected' else 'unavailable',
        'message': 'AI Examiner API is running',
        'database': db_status
    }), (200 if db_status == 'connected' else 503)

@app.route('/api/ready', methods=['GET'])
def readiness():
    from utils.workspace import now
    try:
        database = db_connection.get_db()
        database.command('ping')
        lease = database.worker_leases.find_one({'_id': 'inference'})
        online = bool(lease and lease.get('owner') and lease['expires'] > now())
        return jsonify(database=True, worker=online, queued=database.jobs.count_documents({'state': 'queued'}),
                       processing=database.jobs.count_documents({'state': 'processing'})), (200 if online else 503)
    except Exception:
        return jsonify(database=False, worker=False), 503


# ==================== TEACHER ROUTES ====================

@app.route('/api/teachers', methods=['POST'])
@require_auth
def create_teacher():
    """Create a new teacher"""
    try:
        data = json_object()
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
        return api_failure(e)

@app.route('/api/teachers/<teacher_id>', methods=['GET'])
@require_auth
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
        return api_failure(e)

@app.route('/api/teachers', methods=['GET'])
@require_auth
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
        return api_failure(e)

# ==================== STUDENT ROUTES ====================

@app.route('/api/students', methods=['POST'])
@require_auth
def create_student():
    """Create a new student"""
    try:
        data = json_object()
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
        return api_failure(e)

@app.route('/api/students/<student_id>', methods=['GET'])
@require_auth
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
        return api_failure(e)

@app.route('/api/students', methods=['GET'])
@require_auth
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
        return api_failure(e)

@app.route('/api/students/<student_id>/statistics', methods=['GET'])
@require_auth
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
        return api_failure(e)

@app.route('/api/teachers/<teacher_id>', methods=['DELETE'])
@require_auth
def delete_teacher(teacher_id):
    """Delete a teacher"""
    try:
        if not Teacher.delete(teacher_id).deleted_count:
            return jsonify(error='Teacher not found'), 404
        return jsonify({'success': True, 'message': 'Teacher deleted successfully'})
    except Exception as e:
        logger.error(f"Error deleting teacher: {str(e)}")
        return api_failure(e)

@app.route('/api/students/<student_id>', methods=['DELETE'])
@require_auth
def delete_student(student_id):
    """Delete a student"""
    try:
        if not Student.delete(student_id).deleted_count:
            return jsonify(error='Student not found'), 404
        return jsonify({'success': True, 'message': 'Student deleted successfully'})
    except Exception as e:
        logger.error(f"Error deleting student: {str(e)}")
        return api_failure(e)

# ==================== EVALUATION ROUTES ====================

def atomic_cache_write(path, text):
    fd, temporary = tempfile.mkstemp(dir=os.path.dirname(path), suffix='.part')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as output:
            output.write(text)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)


def extract_uploaded_pdf(path, kind):
    """Single-form extraction uses the same bounded rendering and explicit unreadability rules."""
    from utils.gemini_service import VLLM_MODEL
    cache_dir = app.config.get('CACHE_FOLDER', os.path.join(os.path.dirname(__file__), 'cache'))
    os.makedirs(cache_dir, exist_ok=True)
    with open(path, 'rb') as source:
        checksum = hashlib.file_digest(source, 'sha256').hexdigest()
    key = hashlib.sha256(json.dumps(['ocr-single-v4', kind, VLLM_MODEL, checksum]).encode()).hexdigest()
    cache_file = os.path.join(cache_dir, key + '.txt')
    if os.path.exists(cache_file):
        with open(cache_file, encoding='utf-8') as cached:
            text = cached.read()
    else:
        try:
            text = pdf_processor.extract_text_from_pdf(path)
        except Exception:
            pages = []
            for index in range(pdf_processor.page_count(path)):
                image = pdf_processor.render_page(path, index)
                try:
                    pages.append(pdf_processor.extract_text_from_images_via_gemini([image], gemini_service, document_kind=kind))
                finally:
                    image.close()
            text = '\n'.join(pages)
        if not text.strip() or '[UNREADABLE]' in text or '[No text detected]' in text or '[Error' in text:
            raise ReviewRequired('Source text is missing or unreadable; inspect the PDF before evaluation')
        atomic_cache_write(cache_file, text)
    return text


@app.route('/api/upload-model-answer', methods=['POST'])
@require_auth
def upload_model_answer():
    """Handle model answer upload"""
    file_path = None
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

        text = extract_uploaded_pdf(file_path, 'answer_key')

        # Clean up
        os.remove(file_path)
        file_path = None

        return jsonify({
            'success': True,
            'model_answer': text,
            'message': 'Model answer uploaded successfully'
        })

    except Exception as e:
        return api_failure(e)
    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)


@app.route('/api/evaluate-answer', methods=['POST'])
@require_auth
def evaluate_answer():
    """Evaluate student answer against model answer and store in database"""
    student_file_path = None
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

        student_text = extract_uploaded_pdf(student_file_path, 'student')
        cache_dir = app.config.get('CACHE_FOLDER', os.path.join(os.path.dirname(__file__), 'cache'))

        # --- EVALUATION RESULT CACHING ---
        # Hash the combination of student text + model answer + max marks
        # to guarantee identical results for identical inputs.
        from utils.gemini_service import VLLM_MODEL, END_SEM_PROMPT
        eval_input = json.dumps(['structured-v1', VLLM_MODEL, END_SEM_PROMPT, student_text, model_answer, max_marks, question])
        eval_hash = hashlib.sha256(eval_input.encode('utf-8')).hexdigest()
        eval_cache_file = os.path.join(cache_dir, f'eval_{eval_hash}.json')

        if os.path.exists(eval_cache_file):
            # Evaluation cache HIT - return the exact same result
            logger.info(f"Evaluation cache HIT for hash {eval_hash[:12]}... Returning cached grade.")
            with open(eval_cache_file, 'r', encoding='utf-8') as ecf:
                evaluation_result = validate_result(json.load(ecf), max_marks)
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
            evaluation_result = validate_result(evaluation_result, max_marks)
            atomic_cache_write(eval_cache_file, json.dumps(evaluation_result, ensure_ascii=False))
            logger.info(f"Cached evaluation result to {eval_cache_file}")

        # Store evaluation in database
        evaluation_result = validate_result(evaluation_result, max_marks)
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
        evaluation_result['max_marks'] = max_marks

        # Clean up
        os.remove(student_file_path)
        student_file_path = None

        return jsonify({
            'success': True,
            'evaluation': evaluation_result
        })

    except Exception as e:
        logger.error(f"Evaluation error: {str(e)}")
        return api_failure(e)
    finally:
        if student_file_path and os.path.exists(student_file_path):
            os.remove(student_file_path)


@app.route('/api/evaluations', methods=['GET'])
@require_auth
def get_all_evaluations():
    """Get all evaluations"""
    try:
        evaluations = Evaluation.get_all()
        if not evaluations:
            return jsonify([])

        return jsonify([serialize_doc(e) for e in evaluations])
    except Exception as e:
        logger.error(f"Error fetching evaluations: {str(e)}")
        return api_failure(e)

@app.route('/api/evaluations/<evaluation_id>', methods=['GET'])
@require_auth
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
        return api_failure(e)

@app.route('/api/evaluations/<evaluation_id>/manual', methods=['PUT'])
@require_auth
def update_manual_evaluation(evaluation_id):
    """Manually grade an evaluation that needed review"""
    try:
        from bson.objectid import ObjectId
        data = json_object()
        if not data or 'marks_awarded' not in data:
            return jsonify({'error': 'Missing marks_awarded'}), 400

        marks = float(data['marks_awarded'])
        import math
        record = Evaluation.find_by_id(evaluation_id)
        if not record:
            return jsonify(error='Evaluation not found'), 404
        if not math.isfinite(marks) or not 0 <= marks <= record['max_marks']:
            return jsonify(error='Marks must be within the maximum'), 400
        feedback = data.get('feedback', 'Manually Graded')
        validated = validate_result({'marks_awarded': marks, 'feedback': feedback,
                                     'strengths': [], 'missing_points': []}, record['max_marks'])

        db_connection.get_collection('audit').insert_one({'actor': g.user_email, 'action': 'manual_legacy_grade',
            'evaluation_id': evaluation_id, 'previous_marks': record.get('marks'), 'marks': marks,
            'previous_question_scores': record.get('question_scores', []), 'reason': feedback, 'at': datetime.datetime.now(datetime.timezone.utc)})
        db_connection.get_collection('evaluations').update_one(
            {'_id': ObjectId(evaluation_id)},
            {
                '$set': {
                    'marks': marks,
                    'percentage': validated['percentage'],
                    'grade': validated['grade'],
                    'feedback': feedback,
                    'needs_review': False,
                    'status': 'completed_manually',
                    'question_scores': [], 'rubric': None,
                    'verified': False, 'verified_by': None, 'verified_at': None,
                    'updated_at': datetime.datetime.now(datetime.timezone.utc)
                }
            }
        )
        return jsonify({'success': True, 'message': 'Manual grade saved'})
    except Exception as e:
        logger.error(f"Error saving manual grade: {str(e)}")
        return api_failure(e)

@app.route('/api/evaluations/student/<student_id>', methods=['GET'])
@require_auth
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
        return api_failure(e)

@app.route('/api/evaluations/teacher/<teacher_id>', methods=['GET'])
@require_auth
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
        return api_failure(e)

@app.route('/api/evaluations/recent', methods=['GET'])
@require_auth
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
        return api_failure(e)

@app.route('/api/evaluations/<evaluation_id>', methods=['DELETE'])
@require_auth
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
        return api_failure(e)

@app.route('/api/ocr-only', methods=['POST'])
@require_auth
def ocr_only():
    """Extract text from handwritten PDF without evaluation"""
    file_path = None
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400

        file = request.files['file']

        if not Config.allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type'}), 400

        # Save and process file
        file_path = pdf_processor.save_uploaded_file(file, app.config['UPLOAD_FOLDER'])
        extracted_text = extract_uploaded_pdf(file_path, 'student')

        # Clean up
        os.remove(file_path)
        file_path = None

        return jsonify({
            'success': True,
            'extracted_text': extracted_text
        })

    except Exception as e:
        return api_failure(e)

# ==================== BATCH PROCESSING ROUTES ====================

# Legacy processing endpoints are retired; saved legacy results remain readable.
    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)


@app.route('/api/batch/process-courses', methods=['POST'])
@app.route('/api/batch/stream', methods=['GET'])
@app.route('/api/batch/stop', methods=['POST'])
@app.route('/api/batch/status', methods=['GET'])
@require_auth
def retired_batch_processing():
    return jsonify(error='Use the durable evaluation workspace'), 410

@app.route('/api/batch/results', methods=['GET'])
@require_auth
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
        return api_failure(e)


@app.route('/api/batch/results/<course_code>', methods=['GET'])
@require_auth
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
        return api_failure(e)

# ==================== FOLDER UPLOAD ROUTE ====================

@app.route('/api/batch/upload-folder', methods=['POST'])
@require_auth
def batch_upload_folder():
    """Accept folder upload from browser and reconstruct directory structure."""
    try:
        if 'files' not in request.files:
            return jsonify({'error': 'No files provided'}), 400

        files = request.files.getlist('files')
        if not files:
            return jsonify({'error': 'No files selected'}), 400
        if len(files) > 1000:
            return jsonify(error='Upload at most 1000 files per batch'), 400

        from utils.course_processor import COURSE_CODE_PATTERN
        for index, uploaded in enumerate(files):
            relative = request.form.get(f'path_{index}') or request.form.get(f'path_{uploaded.filename}') or uploaded.filename
            safe_path('/validation', relative)
            folders = relative.replace('\\', '/').split('/')[:-1]
            course_names = [part for part in folders if COURSE_CODE_PATTERN.fullmatch(part)]
            if not course_names:
                raise ValueError('Every PDF must be inside a registered course-code folder')
            for code in course_names:
                authorize(db_connection.get_db(), code, 'uploaders')

        # Create a unique temp directory for this upload
        upload_base = os.path.join(os.path.dirname(__file__), Config.BATCH_UPLOAD_FOLDER)
        os.makedirs(upload_base, exist_ok=True)
        upload_dir = tempfile.mkdtemp(dir=upload_base, prefix='batch_')

        # Collect ALL path_* fields from the form for debugging
        path_fields = {k: v for k, v in request.form.items() if k.startswith('path_')}
        logger.info(f"Folder upload: received {len(files)} files, {len(path_fields)} path fields")
        if path_fields:
            sample_paths = list(path_fields.values())[:3]
            logger.info(f"Sample paths from browser: {sample_paths}")

        saved_count = 0
        for file_index, file in enumerate(files):
            # Try multiple strategies to find the relative path
            # Strategy 1: path_{filename} (original approach)
            relative_path = request.form.get(f'path_{file_index}') or request.form.get(f'path_{file.filename}')

            # Strategy 2: If not found, try with just the basename
            if not relative_path:
                basename = os.path.basename(file.filename)
                relative_path = request.form.get(f'path_{basename}')

            # Strategy 3: Use the file.filename directly (Flask sometimes preserves full path)
            if not relative_path:
                relative_path = file.filename

            logger.info(f"  File: {file.filename} -> relative_path: {relative_path}")

            # Security: strip leading slashes and normalize
            relative_path = relative_path.lstrip('/').lstrip('\\')
            relative_path = relative_path.replace('\\', '/')

            # Create subdirectories as needed
            if not relative_path.lower().endswith('.pdf'):
                raise ValueError('Batch uploads support PDF files only')
            full_path = str(safe_path(upload_dir, relative_path))
            if os.path.exists(full_path):
                raise ValueError('Duplicate file path in upload')
            os.makedirs(os.path.dirname(full_path), exist_ok=True)

            file.save(full_path)
            saved_count += 1

        # Log the resulting directory structure for debugging
        for root, dirs, dir_files in os.walk(upload_dir):
            level = root.replace(upload_dir, '').count(os.sep)
            indent = ' ' * 2 * level
            logger.info(f"{indent}{os.path.basename(root)}/")
            sub_indent = ' ' * 2 * (level + 1)
            for f in dir_files:
                logger.info(f"{sub_indent}{f}")

        db_connection.get_db().uploads.insert_one({'_id': str(__import__('pathlib').Path(upload_dir).resolve()), 'owner': g.user_email})
        logger.info(f"Folder upload: saved {saved_count} files to {upload_dir}")

        return jsonify({
            'success': True,
            'upload_dir': upload_dir,
            'file_count': saved_count
        })

    except HTTPException:
        raise
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Folder upload error: {str(e)}")
        return jsonify({'error': 'Folder upload failed'}), 500


from admin_api import create_admin_api
app.register_blueprint(create_admin_api(require_auth))
from upload_api import create_upload_api
app.register_blueprint(create_upload_api(require_auth, os.path.join(os.path.dirname(__file__), Config.BATCH_UPLOAD_FOLDER)))
from workspace_api import create_workspace_api
app.register_blueprint(create_workspace_api(require_auth, os.path.join(os.path.dirname(__file__), Config.BATCH_UPLOAD_FOLDER)))
from teacher_comparison_api import create_teacher_comparison_api
app.register_blueprint(create_teacher_comparison_api(require_auth))

if __name__ == '__main__':
    from worker import EmbeddedWorker

    # Create uploads folder if it doesn't exist
    if not os.path.exists(Config.UPLOAD_FOLDER):
        os.makedirs(Config.UPLOAD_FOLDER)

    worker = None
    try:
        # Test database connection on startup
        logger.info("Testing database connection...")
        try:
            db_connection.connect()
            logger.info("Database connection successful")
        except RuntimeError:
            logger.warning("Database unavailable at startup; the worker will reconnect automatically")

        worker = EmbeddedWorker()
        worker.start()
        # The reloader would launch a second process and duplicate the worker.
        # Restart app.py after backend edits; frontend hot reload is unaffected.
        app.run(debug=Config.APP_ENV != 'production', use_reloader=False, host='0.0.0.0', port=5000)
    finally:
        # Do not close MongoDB underneath an in-flight worker operation.
        if worker is None or worker.stop():
            db_connection.close()
