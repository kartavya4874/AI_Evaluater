from utils.api_contract import json_object
"""Resumable, checksum-verified folder uploads with bounded request sizes."""
import hashlib
import os
import shutil
import uuid
from pathlib import Path
from flask import Blueprint, request, jsonify, g
from werkzeug.exceptions import Forbidden
from pymongo.errors import DuplicateKeyError
from utils.workspace import safe_path, now
from utils.db_connection import db_connection
from access import authorize
from utils.course_processor import COURSE_CODE_PATTERN


def create_upload_api(require_auth, upload_root):
    api = Blueprint('uploads', __name__, url_prefix='/api/workspace/uploads')
    root = Path(upload_root).resolve()

    @api.errorhandler(ValueError)
    def invalid(error):
        return jsonify(error=str(error)), 400

    def session(sid):
        record = db_connection.get_db().upload_sessions.find_one({'_id': sid, 'owner': g.user_email})
        if not record:
            raise Forbidden('Upload session not found for this account')
        return record

    @api.post('')
    @require_auth
    def start():
        data = json_object()
        sid = data.get('session_id', '')
        if not isinstance(sid, str) or len(sid) != 32 or any(c not in '0123456789abcdef' for c in sid):
            raise ValueError('Invalid upload session ID')
        files = data.get('files')
        if not isinstance(files, list) or not 1 <= len(files) <= 20000:
            raise ValueError('Choose 1 to 20000 PDF files per session')
        manifest = []
        seen = set()
        for item in files:
            if not isinstance(item, dict) or not isinstance(item.get('path'), str):
                raise ValueError('Invalid file manifest')
            path = item['path'].replace('\\', '/')
            safe_path(root, path)
            if not path.lower().endswith('.pdf') or path.casefold() in seen:
                raise ValueError('Use distinct PDF paths')
            if type(item.get('size')) is not int or not 0 < item['size'] <= 100 * 1024 * 1024:
                raise ValueError('Each PDF must be between 1 byte and 100 MiB')
            codes = [p.upper() for p in path.split('/')[:-1] if COURSE_CODE_PATTERN.fullmatch(p)]
            if not codes:
                raise ValueError('Every PDF must be in a course-code folder')
            for code in codes[-1:]:
                authorize(db_connection.get_db(), code, 'uploaders')
            seen.add(path.casefold())
            manifest.append({'path': path, 'size': item['size']})
        if sum(item['size'] for item in manifest) > int(os.getenv('MAX_UPLOAD_SESSION_BYTES', str(50 * 1024 ** 3))):
            raise ValueError('This folder exceeds the configured upload session quota')
        record = {'_id': sid, 'owner': g.user_email, 'files': manifest, 'created_at': now(), 'state': 'uploading'}
        try:
            db_connection.get_db().upload_sessions.insert_one(record)
        except DuplicateKeyError:
            old = session(sid)
            if old['files'] != manifest:
                raise ValueError('Session manifest changed; start a new upload')
        root.mkdir(parents=True, exist_ok=True)
        (root / sid).mkdir(exist_ok=True)
        return jsonify(session_id=sid)

    @api.put('/<sid>/<int:index>')
    @require_auth
    def upload_file(sid, index):
        record = session(sid)
        if not 0 <= index < len(record['files']):
            raise ValueError('Invalid file index')
        item = record['files'][index]
        checksum = request.headers.get('X-Content-SHA256', '')
        if len(checksum) != 64 or any(c not in '0123456789abcdef' for c in checksum):
            raise ValueError('A SHA-256 checksum is required')
        db = db_connection.get_db()
        file_id = f'{sid}:{index}'
        previous = db.upload_parts.find_one({'_id': file_id})
        if previous:
            if previous['sha256'] != checksum:
                raise ValueError('File contents changed; start a new upload session')
            return jsonify(saved=True, reused=True)
        if record['state'] != 'uploading':
            raise ValueError('Upload session has already been finalized')
        target = safe_path(root / sid, item['path'])
        target.parent.mkdir(parents=True, exist_ok=True)
        if shutil.disk_usage(root).free < item['size'] + 512 * 1024 * 1024:
            return jsonify(error='Upload storage is nearly full; ask the administrator to provide space'), 507
        temp = target.with_name(target.name + '.' + uuid.uuid4().hex + '.part')
        size = 0
        digest = hashlib.sha256()
        try:
            with temp.open('wb') as out:
                while True:
                    chunk = request.stream.read(1024 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > item['size']:
                        raise ValueError('File exceeds its declared size')
                    digest.update(chunk)
                    out.write(chunk)
                out.flush()
                os.fsync(out.fileno())
            if size != item['size'] or digest.hexdigest() != checksum:
                raise ValueError('Incomplete upload or checksum mismatch; retry this file')
            # Hard-link publication is atomic and never overwrites a finalized source.
            try:
                os.link(temp, target)
            except FileExistsError:
                with target.open('rb') as source:
                    if hashlib.file_digest(source, 'sha256').hexdigest() != checksum:
                        raise ValueError('Conflicting upload; start a new session')
            db.upload_parts.update_one({'_id': file_id}, {'$setOnInsert': {
                'session_id': sid, 'sha256': checksum, 'size': size, 'created_at': now()}}, upsert=True)
        finally:
            temp.unlink(missing_ok=True)
        return jsonify(saved=True)

    @api.post('/<sid>/complete')
    @require_auth
    def complete(sid):
        record = session(sid)
        db = db_connection.get_db()
        if db.upload_parts.count_documents({'session_id': sid}) != len(record['files']):
            raise ValueError('Some files are missing; resume the upload before finalizing')
        directory = str(root / sid)
        db.uploads.update_one({'_id': directory}, {'$setOnInsert': {
            'owner': g.user_email, 'created_at': now(), 'session_id': sid}}, upsert=True)
        db.upload_sessions.update_one({'_id': sid, 'owner': g.user_email}, {'$set': {'state': 'complete'}})
        return jsonify(upload_dir=directory, file_count=len(record['files']))

    return api
