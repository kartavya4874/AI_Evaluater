import hashlib
import json
from utils.result_validation import validate_result


def revision(record):
    fields = ('marks', 'max_marks', 'feedback', 'percentage', 'grade', 'question_scores', 'updated_at')
    return hashlib.sha256(json.dumps({k: record.get(k) for k in fields}, sort_keys=True, default=str).encode()).hexdigest()


def checked(record):
    maximum = record.get('max_marks')
    if isinstance(maximum, bool) or not isinstance(maximum, (int, float)):
        raise ValueError('Result requires valid maximum marks')
    if record.get('status') in ('error', 'cancelled', 'processing'):
        raise ValueError('Failed or unfinished results cannot be verified')
    result = {'marks_awarded': record.get('marks'), 'feedback': record.get('feedback', ''),
                            'strengths': [], 'missing_points': []}
    if record.get('question_scores'):
        result['question_scores'] = record['question_scores']
    rubric = None
    if record.get('rubric'):
        selected = {q['question_id'] for q in record.get('question_scores', [])}
        rubric = [q for q in record['rubric']['questions'] if q['question_id'] in selected]
    return validate_result(result, record.get('max_marks'), rubric=rubric)
