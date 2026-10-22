"""Course-scoped authorization shared by every workspace endpoint."""
import re
from flask import g
from werkzeug.exceptions import Forbidden
from config import Config


def account(db, email):
    if email == Config.ADMIN_EMAIL.strip().lower():
        return {'email': email, 'name': 'Administrator', 'role': 'admin', 'active': True}
    return db.faculty.find_one({'_id': email, 'active': True}, {'google_sub': 0})


def is_admin():
    return g.user.get('role') == 'admin'


def codes(db, permission=None):
    if is_admin():
        return [c['_id'] for c in db.courses.find()]
    fields = [permission] if permission else ['uploaders', 'reviewers']
    return [c['_id'] for c in db.courses.find({'$or': [{f: g.user_email} for f in fields]})]


def authorize(db, course, permission):
    if is_admin():
        return
    record = db.courses.find_one({'_id': course})
    if not record or (not is_admin() and g.user_email not in record.get(permission, [])):
        raise Forbidden('This course is not registered or assigned to you for this action.')


def scope(db, query, permission=None):
    if is_admin():
        return query
    return {'$and': [query, {'course_code': {'$in': codes(db, permission)}}]}


def sheets_allowed(db, ids, permission):
    if not isinstance(ids, list) or not ids or len(ids) > 1000 or not all(isinstance(i, str) for i in ids):
        raise ValueError('Select between 1 and 1000 sheets')
    for sid in ids:
        sheet = db.sheets.find_one({'_id': sid})
        if not sheet:
            raise ValueError('Sheet not found')
        authorize(db, sheet['course_code'], permission)


def course_code(value):
    from utils.course_processor import COURSE_CODE_PATTERN
    if not isinstance(value, str) or len(value) > 80 or not COURSE_CODE_PATTERN.fullmatch(value.strip()):
        raise ValueError('Use a course code such as FS3401 or FS3401_MSE')
    return value.strip().upper()
