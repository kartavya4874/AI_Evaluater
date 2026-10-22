"""Shared HTTP input boundaries; run after authentication, before route effects."""
import math
import re
from bson import ObjectId
from flask import request
from werkzeug.exceptions import BadRequest


def json_object():
    value = request.get_json()
    if not isinstance(value, dict):
        raise BadRequest('Request body must be a JSON object')
    return value


def validate_request():
    endpoint = request.endpoint or ''
    for key, value in (request.view_args or {}).items():
        if key in ('teacher_id', 'student_id', 'evaluation_id') and not ObjectId.is_valid(value):
            raise BadRequest('Invalid record ID')
    if 'limit' in request.args:
        try:
            limit = int(request.args['limit'])
        except ValueError:
            raise BadRequest('limit must be a whole number from 1 to 1000')
        if not 1 <= limit <= 1000:
            raise BadRequest('limit must be a whole number from 1 to 1000')
    if request.is_json:
        data = json_object()
        for field in ('force', 'async'):
            if field in data and type(data[field]) is not bool:
                raise BadRequest(f'{field} must be true or false')
        if endpoint in ('create_teacher', 'create_student'):
            for field in ('name', 'email'):
                if not isinstance(data.get(field), str) or not data[field].strip() or len(data[field]) > 254:
                    raise BadRequest(f'A valid {field} is required')
            if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', data['email'].strip()):
                raise BadRequest('A valid email is required')
            data['email'] = data['email'].strip().lower()
            data['name'] = data['name'].strip()
            for field in ('subject', 'roll_number', 'class'):
                if data.get(field) is not None and (not isinstance(data[field], str) or len(data[field]) > 200):
                    raise BadRequest(f'{field} must be text of at most 200 characters')
        if endpoint == 'update_manual_evaluation' and 'marks_awarded' in data:
            marks = data['marks_awarded']
            if type(marks) not in (int, float) or not math.isfinite(marks):
                raise BadRequest('marks_awarded must be a finite number')
            if 'feedback' in data and not isinstance(data['feedback'], str):
                raise BadRequest('feedback must be text')
    if endpoint == 'evaluate_answer':
        try:
            maximum = int(request.form.get('max_marks', ''))
        except ValueError:
            raise BadRequest('Maximum marks must be a whole number from 1 to 1000')
        if not 1 <= maximum <= 1000:
            raise BadRequest('Maximum marks must be a whole number from 1 to 1000')
        for field in ('teacher_id', 'student_id'):
            if request.form.get(field) and not ObjectId.is_valid(request.form[field]):
                raise BadRequest(f'Invalid {field}')
