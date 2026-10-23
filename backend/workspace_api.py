from utils.api_contract import json_object
from flask import Blueprint, request, jsonify, g, send_file
from pathlib import Path
from utils.db_connection import db_connection
from utils.workspace import Workspace, excel_bytes
from utils.workspace import now
from utils.result_validation import validate_result
import uuid
import re
from access import scope, sheets_allowed, authorize, is_admin
from werkzeug.exceptions import Forbidden
from pymongo.errors import PyMongoError


def create_workspace_api(require_auth, upload_root):
    api = Blueprint('workspace', __name__, url_prefix='/api/workspace')

    def workspace():
        return Workspace(db_connection.get_db())

    def record_filters():
        query = {k: request.args[k] for k in ('exam_id', 'course_code') if request.args.get(k)}
        search = request.args.get('q', '').strip()
        if len(search) > 120:
            raise ValueError('Search must be 120 characters or fewer')
        if search:
            query['$or'] = [{field: {'$regex': re.escape(search), '$options': 'i'}}
                for field in ('roll_number', 'student_rollno', 'student_name', 'course_code', 'exam_id')]
        return query

    @api.errorhandler(ValueError)
    def invalid(error):
        return jsonify(error=str(error)), 400

    @api.errorhandler(PyMongoError)
    @api.errorhandler(RuntimeError)
    def unavailable(error):
        return jsonify(error='Persistent storage is unavailable. No success has been confirmed; refresh before retrying.'), 503

    @api.get('/sheets')
    @require_auth
    def sheets():
        query = {k: request.args[k] for k in ('exam_id', 'course_code') if request.args.get(k)}
        page = int(request.args.get('page', 1))
        size = int(request.args.get('page_size', 50))
        if page < 1 or not 1 <= size <= 100:
            raise ValueError('Invalid page; choose 1 to 100 rows')
        view = request.args.get('view', 'all')
        if view not in ('all', 'existing', 'pending', 'verified', 'failed'):
            raise ValueError('Invalid view')
        service = workspace()
        lease = service.db.worker_leases.find_one({'_id': 'inference'})
        data = service.page(scope(service.db, query), page, size, view, request.args.get('results_only') == 'true')
        return jsonify(**data, capabilities={'admin_all_courses': True, 'activity_log': True, 'pagination': True},
            worker_online=bool(lease and lease.get('owner') and lease['expires'] > now()),
            worker_capacity=lease.get('capacity', 1) if lease and lease['expires'] > now() else 0,
            examinations=service.db.sheets.distinct('exam_id', scope(service.db, {})),
            course_codes=service.db.sheets.distinct('course_code', scope(service.db, {})),
            preparations=list(service.db.preparations.find({} if is_admin() else {'actor': g.user_email},
                {'directory': 0, 'sheet_ids': 0}).sort('created_at', -1).limit(10)))

    @api.get('/inventory')
    @require_auth
    def inventory():
        """One administrative inventory, including records without active marks."""
        if not is_admin():
            raise Forbidden('Only administrators can manage all answer sheets')
        page = int(request.args.get('page', 1))
        size = int(request.args.get('page_size', 50))
        if page < 1 or not 1 <= size <= 100:
            raise ValueError('Invalid page; choose 1 to 100 rows')
        source = request.args.get('source', 'all')
        if source not in ('all', 'workspace', 'legacy'):
            raise ValueError('Invalid source')
        query = record_filters()
        status = request.args.get('status', 'all')
        views = {'all': 'all', 'unverified': 'pending', 'verified': 'verified', 'failed': 'failed', 'no_marks': 'ungraded'}
        if status not in views:
            raise ValueError('Invalid status filter')
        service = workspace()
        if source == 'legacy':
            workspace_page = {'total': 0, 'sheets': []}
        elif status == 'all':
            workspace_page = {'total': service.db.sheets.count_documents(query),
                'sheets': service.snapshot(query, offset=(page - 1) * size, limit=size, summaries=True)}
        else:
            workspace_page = service.page(query, page, size, views[status])
        workspace_count = workspace_page['total']
        legacy_query = dict(query)
        if status in ('verified', 'unverified'):
            legacy_query['verified'] = True if status == 'verified' else {'$ne': True}
            if status == 'unverified':
                legacy_query['marks'] = {'$ne': None}
        elif status == 'failed':
            legacy_query = {'$and': [query, {'$or': [{'status': {'$in': ['error', 'needs_review']}}, {'needs_review': True}, {'batch_mode': True, 'status': {'$exists': False}}]}]}
        elif status == 'no_marks':
            legacy_query = {'$and': [query, {'$or': [{'marks': None}, {'status': 'error'}, {'feedback': {'$regex': '^(Error during evaluation:|Evaluation error)'}}]}]}
        saved_count = service.db.evaluations.count_documents(legacy_query) if source != 'workspace' else 0
        offset = (page - 1) * size
        rows = []
        if offset < workspace_count:
            for sheet in workspace_page['sheets']:
                active = sheet.get('active') or {}
                job = sheet.get('job') or {}
                rows.append({'id': sheet['_id'], 'source': 'workspace',
                    'course_code': sheet.get('course_code'), 'exam_id': sheet.get('exam_id'),
                    'roll_number': sheet.get('roll_number'), 'marks': active.get('marks'),
                    'max_marks': sheet.get('max_marks'), 'verified': active.get('verified', False),
                    'status': job.get('state') or ('completed' if active else 'ready')})
        remaining = size - len(rows)
        if remaining and saved_count:
            records = service.db.evaluations.find(legacy_query, {'roll_number': 1, 'student_rollno': 1,
                'course_code': 1, 'exam_id': 1, 'marks': 1, 'max_marks': 1, 'verified': 1,
                'status': 1, 'needs_review': 1, 'feedback': 1, 'batch_mode': 1}).sort([('created_at', -1), ('_id', 1)]).skip(max(0, offset - workspace_count)).limit(remaining)
            for record in records:
                display = saved_result(record)
                rows.append({'id': str(record['_id']), 'source': 'legacy',
                    'course_code': record.get('course_code'), 'exam_id': record.get('exam_id'),
                    'roll_number': record.get('roll_number') or record.get('student_rollno'),
                    'marks': display.get('marks'), 'max_marks': record.get('max_marks'),
                    'verified': record.get('verified', False),
                    'status': 'needs_review' if display.get('needs_review') and display.get('status') != 'error' else display.get('status') or 'saved'})
        return jsonify(items=rows, total=workspace_count + saved_count, page=page, page_size=size,
            counts={'workspace': workspace_count, 'legacy': saved_count},
            course_codes=sorted(set(filter(None, service.db.sheets.distinct('course_code') + service.db.evaluations.distinct('course_code')))),
            examinations=sorted(set(filter(None, service.db.sheets.distinct('exam_id') + service.db.evaluations.distinct('exam_id')))))

    def saved_result(record):
        from utils.verification import revision
        row = {k: record.get(k) for k in ('marks', 'max_marks', 'percentage', 'grade', 'feedback',
            'question_scores', 'strengths', 'missing_points', 'verified', 'verified_by', 'status', 'needs_review')}
        row.update(_id=str(record['_id']), verification_revision=revision(record))
        if record.get('batch_mode') and not record.get('status'):
            row.update(status='needs_review', needs_review=True)
        if record.get('status') == 'error' or str(record.get('feedback', '')).startswith(('Error during evaluation:', 'Evaluation error')):
            row.update(status='error', needs_review=True, marks=None, percentage=None, grade=None)
        return row

    @api.get('/results')
    @require_auth
    def combined_results():
        service = workspace()
        page, size = int(request.args.get('page', 1)), int(request.args.get('page_size', 50))
        view = request.args.get('view', 'all')
        if page < 1 or not 1 <= size <= 100 or view not in ('all', 'pending', 'verified', 'needs_review'):
            raise ValueError('Invalid results page or filter')
        filters = record_filters()
        source = request.args.get('source', 'all')
        if source not in ('all', 'workspace', 'legacy'):
            raise ValueError('Invalid source')
        query = scope(service.db, filters, 'reviewers')
        workspace_page = service.page(query, page, size, view, results_only=True) if source != 'legacy' else {'total': 0, 'counts': {}, 'sheets': []}
        legacy_filter = dict(filters)
        legacy_review_filter = {'$or': [{'needs_review': True}, {'status': 'needs_review'}]}
        if view == 'needs_review':
            legacy_filter['$and'] = [legacy_review_filter]
        elif view != 'all':
            legacy_filter['verified'] = True if view == 'verified' else {'$ne': True}
            legacy_filter['$nor'] = [legacy_review_filter]
        legacy_query = scope(service.db, legacy_filter, 'reviewers')
        if source == 'workspace':
            legacy_query = {'$and': [legacy_query, {'_id': {'$in': []}}]}
        legacy_count = service.db.evaluations.count_documents(legacy_query)
        legacy_verified = service.db.evaluations.count_documents({'$and': [legacy_query, {'verified': True}, {'$nor': [legacy_review_filter]}]})
        legacy_review_count = service.db.evaluations.count_documents({'$and': [legacy_query, legacy_review_filter]})
        rows = [{'id': s['_id'], 'source': 'workspace', 'course_code': s.get('course_code'),
            'exam_id': s.get('exam_id'), 'roll_number': s.get('roll_number'), 'max_marks': s.get('max_marks'),
            'result': ({'status': 'needs_review', 'needs_review': True, 'marks': None, 'verified': False,
                        'feedback': (s.get('job') or {}).get('error') or 'Marking scheme needs review'}
                       if (s.get('job') or {}).get('state') == 'needs_review' else s['active']),
            'can_edit': True} for s in workspace_page['sheets']]
        if len(rows) < size:
            offset = max(0, (page - 1) * size - workspace_page['total'])
            for record in service.db.evaluations.find(legacy_query, {'model_answer': 0, 'student_answer': 0, 'extracted_text': 0}).sort([('created_at', -1), ('_id', 1)]).skip(offset).limit(size - len(rows)):
                result = saved_result(record)
                result['feedback'] = str(result.get('feedback') or '')[:160]
                for field in ('question_scores', 'strengths', 'missing_points'):
                    result.pop(field, None)
                rows.append({'id': str(record['_id']), 'source': 'legacy', 'course_code': record.get('course_code'),
                    'exam_id': record.get('exam_id'), 'roll_number': record.get('roll_number') or record.get('student_rollno'),
                    'max_marks': record.get('max_marks'), 'result': result, 'can_edit': is_admin()})
        verified = workspace_page['counts'].get('verified', 0) + legacy_verified
        total = workspace_page['total'] + legacy_count
        needs_review = workspace_page['counts'].get('needs_review', 0) + legacy_review_count
        return jsonify(items=rows, total=total, verified=verified, pending=total - verified - needs_review, needs_review=needs_review,
            course_codes=sorted(set(filter(None, service.db.sheets.distinct('course_code', scope(service.db, {}, 'reviewers')) + service.db.evaluations.distinct('course_code', scope(service.db, {}, 'reviewers'))))),
            examinations=sorted(set(filter(None, service.db.sheets.distinct('exam_id', scope(service.db, {}, 'reviewers')) + service.db.evaluations.distinct('exam_id', scope(service.db, {}, 'reviewers'))))))

    @api.get('/results/legacy/<result_id>')
    @require_auth
    def saved_result_detail(result_id):
        from bson import ObjectId
        if not ObjectId.is_valid(result_id):
            raise ValueError('Invalid result ID')
        service = workspace()
        record = service.db.evaluations.find_one(scope(service.db, {'_id': ObjectId(result_id)}, 'reviewers'))
        if not record:
            raise Forbidden('Result is not accessible')
        return jsonify(result=saved_result(record))

    @api.get('/sheets/<sheet_id>')
    @require_auth
    def sheet_detail(sheet_id):
        service = workspace()
        rows = service.snapshot(scope(service.db, {'_id': sheet_id}), summaries=True)
        if not rows:
            raise Forbidden('Sheet is not accessible')
        row = rows[0]
        offset = int(request.args.get('offset', 0))
        if offset < 0:
            raise ValueError('Invalid history offset')
        row['attempts'] = list(service.db.attempts.find({'sheet_id': sheet_id},
            {'ocr': 0, 'file_path': 0, 'model_path': 0}).sort('created_at', -1).skip(offset).limit(20))
        row['attempt_count'] = service.db.attempts.count_documents({'sheet_id': sheet_id})
        active = service.db.attempts.find_one({'_id': row.get('active_attempt')}, {'ocr': 0, 'file_path': 0, 'model_path': 0})
        row['active'] = active if active and active.get('status') == 'completed' and active.get('config') == row['config'] else None
        return jsonify(sheet=row)

    @api.post('/prepare')
    @require_auth
    def prepare():
        data = json_object()
        if not isinstance(data.get('directory'), str) or not data['directory'].strip():
            raise ValueError('An uploaded directory is required')
        if not isinstance(data.get('exam_id'), str) or not data['exam_id'].strip() or len(data['exam_id']) > 120:
            raise ValueError('An examination ID/session is required (maximum 120 characters)')
        if data.get('exam_type') not in ('mst', 'end_sem') or type(data.get('max_marks')) is not int or not 1 <= data['max_marks'] <= 1000:
            raise ValueError('Invalid examination type or maximum marks')
        directory = Path(data['directory']).resolve()
        root = Path(upload_root).resolve()
        if directory == root or not directory.is_relative_to(root) or not directory.is_dir():
            raise ValueError('Select a folder uploaded through this application')
        service = workspace()
        if not service.db.uploads.find_one({'_id': str(directory), **({} if is_admin() else {'owner': g.user_email})}):
            raise Forbidden('Upload this folder from your own account first')
        from utils.course_processor import CourseProcessor
        processor = CourseProcessor(str(directory), int(data.get('max_marks', 0)))
        courses, _ = processor.discover_courses(allow_empty=True)
        for code in processor.discovered_codes:
            authorize(service.db, code, 'uploaders')
        if data.get('async') is True:
            from utils.workspace import digest
            operation_id = digest([str(directory), data.get('exam_id'), data.get('exam_type'), data.get('max_marks'), g.user_email])
            service.db.preparations.update_one({'_id': operation_id}, {'$setOnInsert': {
                'directory': str(directory), 'exam_id': data.get('exam_id'), 'exam_type': data.get('exam_type'),
                'max_marks': int(data.get('max_marks', 0)), 'actor': g.user_email,
                'state': 'queued', 'created_at': now(), 'updated_at': now()}}, upsert=True)
            return jsonify(operation_id=operation_id, issues=processor.discovery_errors), 202
        issues = []
        ids = workspace().prepare(str(directory), data.get('exam_id'), data.get('exam_type'),
                                  int(data.get('max_marks', 0)), g.user_email, issues=issues)
        return jsonify(sheet_ids=ids, issues=issues)

    @api.get('/preparations/<operation_id>')
    @require_auth
    def preparation_status(operation_id):
        record = workspace().db.preparations.find_one({'_id': operation_id, **({} if is_admin() else {'actor': g.user_email})}, {'directory': 0})
        if not record:
            raise Forbidden('Preparation not found')
        return jsonify(operation=record)

    @api.post('/evaluate')
    @require_auth
    def evaluate():
        data = json_object()
        ids = data.get('sheet_ids', [])
        if not isinstance(ids, list) or not ids or len(ids) > 1000 or not all(isinstance(x, str) for x in ids):
            raise ValueError('Select between 1 and 1000 sheets')
        sheets_allowed(workspace().db, ids, 'uploaders')
        jobs = [workspace().enqueue(i, g.user_email, data.get('force') is True) for i in ids]
        return jsonify(jobs=[{k: v for k, v in job.items() if k != 'sheet_snapshot'} for job in jobs]), 202

    @api.post('/evaluate-all')
    @require_auth
    def evaluate_all():
        data = json_object()
        query = {key: data[key] for key in ('exam_id', 'course_code') if data.get(key)}
        if not all(isinstance(value, str) for value in query.values()):
            raise ValueError('Invalid filter')
        service = workspace()
        if data.get('view') == 'failed':
            query['_id'] = {'$in': service.db.jobs.distinct('_id', {'state': {'$in': ['error', 'needs_review']}})}
        elif data.get('view') == 'existing':
            query['active_attempt'] = {'$ne': None}
        elif data.get('view', 'all') != 'all':
            raise ValueError('Invalid evaluation view')
        ids = [row['_id'] for row in service.db.sheets.find(scope(service.db, query, 'uploaders'), {'_id': 1}).limit(20001)]
        if not 1 <= len(ids) <= 20000:
            raise ValueError('Choose filters matching 1 to 20000 sheets you can evaluate')
        operation_id = uuid.uuid4().hex
        service.db.preparations.insert_one({'_id': operation_id, 'kind': 'evaluate', 'actor': g.user_email,
            'sheet_ids': ids, 'force': data.get('force') is True, 'submitted': 0, 'state': 'queued',
            'exam_id': data.get('exam_id') or 'All selected examinations', 'created_at': now(), 'updated_at': now()})
        return jsonify(operation_id=operation_id, count=len(ids)), 202

    @api.post('/cancel')
    @require_auth
    def cancel():
        data = json_object()
        ids = data.get('sheet_ids', [])
        if not isinstance(ids, list) or not 1 <= len(ids) <= 1000 or not all(isinstance(x, str) for x in ids):
            raise ValueError('Invalid sheet selection')
        service = workspace()
        sheets_allowed(service.db, ids, 'uploaders')
        service.db.jobs.update_many({'_id': {'$in': ids}, 'state': 'queued'}, {'$set': {'state': 'cancelled', 'stage': 'cancelled'}})
        service.db.sheets.update_many({'_id': {'$in': ids}, 'execution.state': 'processing'},
            {'$set': {'execution.cancel_requested': True}})
        service.db.jobs.update_many({'_id': {'$in': ids}, 'state': 'processing'}, {'$set': {'cancel_requested': True}})
        service.audit(g.user_email, 'cancel', sheet_ids=ids)
        return jsonify(success=True)

    @api.post('/manage')
    @require_auth
    def manage():
        data = json_object()
        if data.get('confirmation') != 'DELETE':
            raise ValueError('Explicit DELETE confirmation is required')
        ids = data.get('sheet_ids', [])
        if not isinstance(ids, list) or not 1 <= len(ids) <= 1000 or not all(isinstance(x, str) for x in ids):
            raise ValueError('Invalid sheet selection')
        if not is_admin():
            raise Forbidden('Only administrators can delete workspace data')
        workspace().manage(ids, data.get('scope'), g.user_email)
        return jsonify(success=True)

    @api.post('/result')
    @require_auth
    def result():
        data = json_object()
        if not isinstance(data.get('sheet_id'), str):
            raise ValueError('Invalid sheet ID')
        service = workspace()
        sheet = service.db.sheets.find_one({'_id': data.get('sheet_id')})
        if not sheet:
            raise ValueError('Sheet not found')
        authorize(service.db, sheet['course_code'], 'reviewers')
        with service.reserve([sheet['_id']]) as reserved:
            if 'marks' in data:
                reason = data.get('reason', '')
                if not isinstance(reason, str) or not reason.strip():
                    raise ValueError('A reason is required for manual grading')
                validated = validate_result({'marks_awarded': data['marks'], 'feedback': reason,
                                             'strengths': [], 'missing_points': []}, sheet['max_marks'])
                attempt_id = uuid.uuid4().hex
                service.db.attempts.insert_one({'_id': attempt_id, 'sheet_id': sheet['_id'],
                    'status': 'completed', 'source': 'manual', 'marks': validated['marks_awarded'],
                    'percentage': validated['percentage'], 'grade': validated['grade'],
                    'feedback': reason, 'actor': g.user_email, 'created_at': now(), 'config': sheet['config']})
            else:
                attempt_id = data.get('attempt_id')
                if not isinstance(attempt_id, str):
                    raise ValueError('Invalid attempt ID')
                if not service.db.attempts.find_one({'_id': attempt_id, 'sheet_id': sheet['_id'], 'status': 'completed', 'config': sheet['config']}):
                    raise ValueError('Choose a successful attempt')
            service.db.sheets.update_one({'_id': sheet['_id']}, {'$set': {'active_attempt': attempt_id, 'active_pinned': True}})
            for _, previous_job in reserved:
                if previous_job and previous_job.get('state') == 'needs_review':
                    previous_job.update(state='completed', stage='completed', error=None)
            service.audit(g.user_email, 'select_result', sheet_id=sheet['_id'], attempt_id=attempt_id)
        return jsonify(success=True)

    @api.get('/export')
    @require_auth
    def export():
        if request.args.get('source', 'all') not in ('all', 'workspace', 'legacy'):
            raise ValueError('Invalid export source')
        query = record_filters()
        service = workspace()
        rows = service.snapshot(scope(service.db, query), summaries=True, include_jobs=False) if request.args.get('source') != 'legacy' else []
        if request.args.get('source') != 'workspace':
            from utils.verification import checked
            for record in service.db.evaluations.find(scope(service.db, {**query, 'verified': True}, 'reviewers')):
                try:
                    checked(record)
                except (ValueError, TypeError):
                    continue
                rows.append({'exam_id': record.get('exam_id', 'Previous evaluations'),
                    'course_code': record.get('course_code', 'Other'),
                    'roll_number': str(record.get('roll_number') or record.get('student_rollno') or ''),
                    'max_marks': record['max_marks'], 'active': record})
        return send_file(excel_bytes(rows), as_attachment=True,
                         download_name='evaluation-results.xlsx',
                         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    @api.post('/verify')
    @require_auth
    def verify():
        from bson import ObjectId
        from utils.verification import revision, checked
        data = json_object()
        items = data.get('items')
        source = data.get('source')
        if source not in ('workspace', 'legacy') or not isinstance(items, list) or not 1 <= len(items) <= 1000:
            raise ValueError('Select between 1 and 1000 results')
        if not all(isinstance(i, dict) and isinstance(i.get('id'), str) for i in items):
            raise ValueError('Invalid result selection')
        if source == 'workspace' and not all(isinstance(i.get('attempt_id'), str) for i in items):
            raise ValueError('Choose a saved active result')
        service = workspace()
        updates = []
        if source == 'workspace':
            sheets_allowed(service.db, [i['id'] for i in items], 'reviewers')
        if source == 'legacy':
            for item in items:
                if not ObjectId.is_valid(item['id']):
                    raise ValueError('Invalid result ID')
                record = service.db.evaluations.find_one({'_id': ObjectId(item['id'])})
                if not record or item.get('revision') != revision(record):
                    raise ValueError('Result changed; refresh and review it again')
                authorize(service.db, record.get('course_code'), 'reviewers')
                checked(record)
                updates.append(record)
            for record in updates:
                condition = {k: record.get(k) for k in ('marks', 'max_marks', 'feedback', 'updated_at', 'status')}
                result = service.db.evaluations.update_one({'_id': record['_id'], **condition}, {'$set': {
                    'verified': True, 'verified_by': g.user_email, 'verified_at': now(),
                    'status': 'completed', 'needs_review': False}})
                if not result.matched_count:
                    raise ValueError('A result changed during verification; refresh to see which results were verified')
        else:
            with service.reserve([i['id'] for i in items]):
                for item in items:
                    sheet = service.db.sheets.find_one({'_id': item['id']})
                    attempt = service.db.attempts.find_one({'_id': item.get('attempt_id'),
                        'sheet_id': item['id'], 'status': 'completed', 'config': sheet['config']})
                    if not attempt or sheet.get('active_attempt') != attempt['_id']:
                        raise ValueError('Active result changed; refresh and review it again')
                    checked({**attempt, 'max_marks': sheet['max_marks']})
                    updates.append(attempt)
                for attempt in updates:
                    service.db.attempts.update_one({'_id': attempt['_id']}, {'$set': {
                        'verified': True, 'verified_by': g.user_email, 'verified_at': now()}})
        service.audit(g.user_email, 'verify_results', source=source, result_ids=[str(r['_id']) for r in updates])
        return jsonify(success=True, verified_count=len(updates))

    return api
