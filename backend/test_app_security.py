import io
import tempfile
import unittest
from unittest.mock import patch
import jwt
import mongomock
from app import app, Config


class AppSecurityTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.database = mongomock.MongoClient().db
        self.connection = patch('app.db_connection.get_db', return_value=self.database)
        self.connection.start()
        self.addCleanup(self.connection.stop)
        self.database.courses.insert_many([{'_id': 'FS3401'}, {'_id': 'MB3103'}])
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.upload = patch.object(Config, 'BATCH_UPLOAD_FOLDER', self.temp.name)
        self.upload.start()
        self.addCleanup(self.upload.stop)
        token = jwt.encode({'email': Config.ADMIN_EMAIL, 'provider': 'google'}, Config.JWT_SECRET_KEY, algorithm='HS256')
        self.headers = {'Authorization': 'Bearer ' + token}

    def test_access_preflight_does_not_require_login(self):
        for path, method in [('/api/access', 'GET'), ('/api/access/faculty', 'POST'),
                             ('/api/access/courses', 'POST'), ('/api/access/import', 'POST')]:
            response = self.client.options(path, headers={
                'Origin': 'http://localhost:3000',
                'Access-Control-Request-Method': method,
                'Access-Control-Request-Headers': 'authorization,content-type',
            })
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers.get('Access-Control-Allow-Origin'), 'http://localhost:3000')
            self.assertIn('authorization', response.headers.get('Access-Control-Allow-Headers', '').lower())
        self.assertEqual(self.client.get('/api/access').status_code, 401)
        self.assertEqual(self.client.post('/api/access/faculty', json={}).status_code, 401)

    def test_health_returns_unavailable_when_database_fails(self):
        with patch('app.db_connection.get_db', side_effect=RuntimeError('offline')):
            self.assertEqual(self.client.get('/api/health').status_code, 503)

    def test_stream_does_not_accept_query_token(self):
        self.assertEqual(self.client.get('/api/batch/stream?token=invalid').status_code, 401)

    def test_upload_rejects_parent_traversal(self):
        result = self.client.post('/api/batch/upload-folder', headers=self.headers,
            data={'files': (io.BytesIO(b'pdf'), 'test.pdf'), 'path_test.pdf': '../outside.pdf'})
        self.assertEqual(result.status_code, 400)

    def test_old_batch_start_cannot_launch_thread(self):
        result = self.client.post('/api/batch/process-courses', headers=self.headers, json={})
        self.assertEqual(result.status_code, 410)

    def test_same_filename_in_different_courses_is_preserved(self):
        from pathlib import Path
        result = self.client.post('/api/batch/upload-folder', headers=self.headers,
            data={'files': [(io.BytesIO(b'first'), '101.pdf'), (io.BytesIO(b'second'), '101.pdf')],
                  'path_0': 'FS3401/101.pdf', 'path_1': 'MB3103/101.pdf'})
        self.assertEqual(result.status_code, 200)
        root = Path(result.json['upload_dir'])
        self.assertEqual((root / 'FS3401/101.pdf').read_bytes(), b'first')
        self.assertEqual((root / 'MB3103/101.pdf').read_bytes(), b'second')

    def test_password_login_is_disabled(self):
        self.assertEqual(self.client.post('/api/auth/login', json={'email': Config.ADMIN_EMAIL, 'password': Config.ADMIN_PASSWORD}).status_code, 410)

    def test_google_login_requires_approved_verified_identity(self):
        with patch.object(Config, 'GOOGLE_CLIENT_ID', 'test-client'), patch('google.oauth2.id_token.verify_oauth2_token') as verify:
            verify.return_value = {'email': 'unknown@example.com', 'email_verified': True, 'sub': 'unknown'}
            self.assertEqual(self.client.post('/api/auth/google', json={'credential': 'test'}).status_code, 403)
            verify.return_value = {'email': Config.ADMIN_EMAIL, 'email_verified': False, 'sub': 'admin'}
            self.assertEqual(self.client.post('/api/auth/google', json={'credential': 'test'}).status_code, 401)
            verify.return_value = {'email': Config.ADMIN_EMAIL, 'email_verified': True, 'sub': 'admin'}
            response = self.client.post('/api/auth/google', json={'credential': 'test'})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json['user']['role'], 'admin')
            verify.assert_called_with('test', unittest.mock.ANY, 'test-client')

    def test_login_attempts_are_rate_limited(self):
        with patch.object(Config, 'GOOGLE_CLIENT_ID', 'test-client'), patch('google.oauth2.id_token.verify_oauth2_token', side_effect=ValueError('bad token')):
            for _ in range(10):
                self.assertEqual(self.client.post('/api/auth/google', json={'credential': 'bad'}).status_code, 401)
            self.assertEqual(self.client.post('/api/auth/google', json={'credential': 'bad'}).status_code, 429)

    def test_admin_can_upload_unregistered_course(self):
        result = self.client.post('/api/batch/upload-folder', headers=self.headers,
            data={'files': (io.BytesIO(b'pdf'), '101.pdf'), 'path_0': 'XX1234/101.pdf'})
        self.assertEqual(result.status_code, 200)

    def test_added_admin_has_full_access_and_role_changes_apply_immediately(self):
        email = 'second-admin@example.com'
        self.database.faculty.insert_one({'_id': email, 'email': email, 'name': 'Second admin', 'role': 'admin', 'active': True})
        token = jwt.encode({'email': email, 'provider': 'google'}, Config.JWT_SECRET_KEY, algorithm='HS256')
        headers = {'Authorization': 'Bearer ' + token}
        self.assertEqual(self.client.get('/api/auth/me', headers=headers).json['user']['role'], 'admin')
        self.assertEqual(self.client.post('/api/access/settings', headers=headers, json={'parallelism': 2}).status_code, 200)
        self.database.faculty.update_one({'_id': email}, {'$set': {'role': 'faculty'}})
        self.assertEqual(self.client.post('/api/access/settings', headers=headers, json={'parallelism': 2}).status_code, 403)
        result = self.client.post('/api/batch/upload-folder', headers=headers,
            data={'files': (io.BytesIO(b'pdf'), '101.pdf'), 'path_0': 'XX1234/101.pdf'})
        self.assertEqual(result.status_code, 403)

    def test_disabled_faculty_and_legacy_routes_rejected(self):
        email = 'faculty@example.com'
        self.database.faculty.insert_one({'_id': email, 'email': email, 'role': 'faculty', 'active': True})
        token = jwt.encode({'email': email, 'provider': 'google'}, Config.JWT_SECRET_KEY, algorithm='HS256')
        headers = {'Authorization': 'Bearer ' + token}
        self.assertEqual(self.client.get('/api/evaluations', headers=headers).status_code, 403)
        self.database.faculty.update_one({'_id': email}, {'$set': {'active': False}})
        self.assertEqual(self.client.get('/api/auth/me', headers=headers).status_code, 403)


if __name__ == '__main__':
    unittest.main()
