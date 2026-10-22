import io
import unittest
from functools import wraps
from unittest.mock import patch
import mongomock
from flask import Flask, g, request, jsonify
from werkzeug.exceptions import HTTPException
from openpyxl import Workbook
from admin_api import create_admin_api
from workspace_api import create_workspace_api
from access import account


class MultiuserTests(unittest.TestCase):
    def setUp(self):
        self.db = mongomock.MongoClient().db
        self.db.faculty.insert_one({'_id': 'faculty@example.com', 'email': 'faculty@example.com', 'role': 'faculty', 'active': True})
        self.db.courses.insert_many([{'_id': 'FS3401', 'uploaders': ['faculty@example.com'], 'reviewers': []}, {'_id': 'MB3103', 'uploaders': [], 'reviewers': ['faculty@example.com']}])
        for code in ['FS3401', 'MB3103', 'XX1234']:
            self.db.sheets.insert_one({'_id': code, 'course_code': code, 'config': {}, 'max_marks': 100})
        self.patch = patch('utils.db_connection.db_connection.get_db', return_value=self.db)
        self.patch.start(); self.addCleanup(self.patch.stop)
        app = Flask(__name__)
        def auth(fn):
            @wraps(fn)
            def wrapped(*a, **kw):
                g.user_email = 'faculty@example.com'
                g.user = {'role': request.headers.get('Role', 'faculty')}
                return fn(*a, **kw)
            return wrapped
        app.register_blueprint(create_admin_api(auth))
        app.register_blueprint(create_workspace_api(auth, '.'))
        @app.errorhandler(HTTPException)
        def error(e):
            return jsonify(error=e.description), e.code
        self.client = app.test_client()

    def test_admin_can_evaluate_unregistered_course(self):
        response = self.client.post('/api/workspace/evaluate', headers={'Role': 'admin'}, json={'sheet_ids': ['XX1234']})
        self.assertEqual(response.status_code, 202)
        self.assertEqual(self.db.jobs.find_one({'_id': 'XX1234'})['state'], 'queued')

    def test_multiple_admins_and_role_preservation(self):
        for email in ['admin1@example.com', 'admin2@example.com']:
            response = self.client.post('/api/access/faculty', headers={'Role': 'admin'}, json={'email': email, 'name': 'Admin', 'role': 'admin'})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(account(self.db, email)['role'], 'admin')
        response = self.client.post('/api/access/faculty', headers={'Role': 'admin'}, json={'email': 'admin1@example.com', 'name': 'Updated'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(account(self.db, 'admin1@example.com')['role'], 'admin')
        self.client.post('/api/access/faculty', headers={'Role': 'admin'}, json={'email': 'admin1@example.com', 'name': 'Updated', 'active': False})
        self.assertIsNone(account(self.db, 'admin1@example.com'))

    def test_faculty_cannot_promote_itself_and_admin_cannot_disable_self(self):
        payload = {'email': 'faculty@example.com', 'name': 'Account', 'role': 'admin'}
        self.assertEqual(self.client.post('/api/access/faculty', json=payload).status_code, 403)
        for changes in [{'active': False}, {'role': 'faculty'}, {'role': 'owner'}]:
            self.assertEqual(self.client.post('/api/access/faculty', headers={'Role': 'admin'}, json={**payload, **changes}).status_code, 400)

    def test_initial_admin_is_protected(self):
        from config import Config
        self.assertEqual(self.client.post('/api/access/faculty', headers={'Role': 'admin'}, json={'email': Config.ADMIN_EMAIL, 'name': 'Initial', 'active': False}).status_code, 400)

    def test_parallel_limit_requires_admin_and_integer_between_one_and_five(self):
        self.assertEqual(self.client.post('/api/access/settings', json={'parallelism': 5}).status_code, 403)
        for value in [0, 6, -1, True, 2.5, '3', None]:
            self.assertEqual(self.client.post('/api/access/settings', headers={'Role': 'admin'}, json={'parallelism': value}).status_code, 400)
        for value in [1, 5]:
            result = self.client.post('/api/access/settings', headers={'Role': 'admin'}, json={'parallelism': value})
            self.assertEqual(result.status_code, 200)
            self.assertEqual(self.client.get('/api/access').json['parallelism'], value)
            self.assertEqual(self.db.settings.find_one({'_id': 'evaluation'})['parallelism'], value)

    def test_snapshot_excludes_unassigned_courses(self):
        result = self.client.get('/api/workspace/sheets')
        self.assertEqual({s['_id'] for s in result.json['sheets']}, {'FS3401', 'MB3103'})

    def test_upload_assignment_does_not_allow_review(self):
        result = self.client.post('/api/workspace/result', json={'sheet_id': 'FS3401', 'marks': 50, 'reason': 'review'})
        self.assertEqual(result.status_code, 403)
        self.assertEqual(self.db.attempts.count_documents({}), 0)

    def test_review_assignment_allows_manual_revision(self):
        result = self.client.post('/api/workspace/result', json={'sheet_id': 'MB3103', 'marks': 50, 'reason': 'review'})
        self.assertEqual(result.status_code, 200)

    def test_review_assignment_cannot_evaluate(self):
        self.assertEqual(self.client.post('/api/workspace/evaluate', json={'sheet_ids': ['MB3103']}).status_code, 403)

    def test_mixed_selection_rejected_before_enqueue(self):
        self.assertEqual(self.client.post('/api/workspace/evaluate', json={'sheet_ids': ['FS3401', 'XX1234']}).status_code, 403)
        self.assertEqual(self.db.jobs.count_documents({}), 0)

    def test_faculty_cannot_manage_accounts_or_delete(self):
        self.assertEqual(self.client.post('/api/access/faculty', json={}).status_code, 403)
        self.assertEqual(self.client.post('/api/workspace/manage', json={'sheet_ids': ['FS3401'], 'confirmation': 'DELETE', 'scope': 'sheet'}).status_code, 403)

    def test_disabled_account_is_rejected(self):
        self.db.faculty.update_one({'_id': 'faculty@example.com'}, {'$set': {'active': False}})
        self.assertIsNone(account(self.db, 'faculty@example.com'))

    def test_excel_import_preserves_assignments_and_rejects_invalid_rows(self):
        def upload(rows):
            wb = Workbook(); ws = wb.active
            ws.append(['course_code', 'name'])
            for row in rows: ws.append(row)
            content = io.BytesIO(); wb.save(content); content.seek(0)
            return self.client.post('/api/access/import', headers={'Role': 'admin'}, data={'file': (content, 'courses.xlsx')})
        self.assertEqual(upload([['FS3401', 'Physics']]).status_code, 200)
        self.assertEqual(self.db.courses.find_one({'_id': 'FS3401'})['uploaders'], ['faculty@example.com'])
        self.assertEqual(upload([['ZZ1234', 'Valid'], ['bad/code', 'Invalid']]).status_code, 400)
        self.assertIsNone(self.db.courses.find_one({'_id': 'ZZ1234'}))

    def test_unknown_faculty_cannot_be_assigned(self):
        self.assertEqual(self.client.post('/api/access/courses', headers={'Role': 'admin'}, json={'code': 'FS3401', 'uploaders': ['unknown@example.com']}).status_code, 400)
