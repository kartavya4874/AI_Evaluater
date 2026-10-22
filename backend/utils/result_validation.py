"""Shared contract for academic results. Failures are never academic zeroes."""
import math


class ReviewRequired(ValueError):
    pass


def validate_result(result, max_marks, require_questions=False, rubric=None):
    if not isinstance(result, dict):
        raise ValueError('Grading response must be an object')
    if result.get('needs_review') or result.get('status') == 'error':
        raise ReviewRequired(result.get('feedback') or 'Grading needs review')
    feedback = result.get('feedback', '')
    if not isinstance(feedback, str) or feedback.startswith(('Error during evaluation:', 'Evaluation error')):
        raise ValueError('Invalid grading feedback')
    marks = result.get('marks_awarded')
    if isinstance(marks, bool) or not isinstance(marks, (int, float)):
        raise ValueError('Grading response requires numeric marks_awarded')
    if not math.isfinite(marks) or not 0 <= marks <= max_marks or max_marks <= 0:
        raise ValueError('Marks must be finite and within the rubric maximum')
    if require_questions or 'question_scores' in result:
        questions = result.get('question_scores')
        if not isinstance(questions, list) or not questions:
            raise ValueError('Question-level scores are required')
        seen, awarded_total, maximum_total = set(), 0, 0
        for question in questions:
            if not isinstance(question, dict):
                raise ValueError('Invalid question score')
            identifier = question.get('question_id')
            awarded, maximum = question.get('marks_awarded'), question.get('max_marks')
            if not isinstance(identifier, str) or not identifier.strip() or identifier in seen:
                raise ValueError('Question identifiers must be present and unique')
            if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in (awarded, maximum)):
                raise ValueError('Question marks must be finite numbers')
            if not 0 <= awarded <= maximum or maximum <= 0:
                raise ValueError('Question marks exceed their allocation')
            seen.add(identifier)
            awarded_total += awarded
            maximum_total += maximum
        if not math.isclose(awarded_total, marks, abs_tol=0.001) or not math.isclose(maximum_total, max_marks, abs_tol=0.001):
            raise ValueError('Question totals do not match the awarded marks or examination maximum')
    if rubric is not None:
        expected = {q['question_id']: q['max_marks'] for q in rubric}
        actual = {q['question_id']: q['max_marks'] for q in result.get('question_scores', [])}
        if expected != actual:
            raise ReviewRequired('Question identities or allocations disagree with the marking scheme')
    for field in ('strengths', 'missing_points'):
        if not isinstance(result.get(field), list) or not all(isinstance(x, str) for x in result[field]):
            raise ValueError(f'Grading response requires a list of strings: {field}')
    percentage = round(marks / max_marks * 100, 2)
    grade = next(label for threshold, label in [(90, 'A+'), (80, 'A'), (70, 'B+'), (60, 'B'), (50, 'C'), (40, 'D'), (0, 'F')] if percentage >= threshold)
    return {**result, 'marks_awarded': marks, 'percentage': percentage, 'grade': grade,
            'status': 'completed', 'needs_review': False}


def valid_record(record):
    return (record.get('status') in ('completed', 'completed_manually')
            and not record.get('needs_review')
            and record.get('marks') is not None
            and not str(record.get('feedback', '')).startswith(('Error during evaluation:', 'Evaluation error')))
