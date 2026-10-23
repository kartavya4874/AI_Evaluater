"""Administrator-authored fallback allocations, isolated by course and exam type."""
import math
from access import course_code


def validate_scheme(data):
    code = course_code(data.get('course_code', ''))
    exam_type = data.get('exam_type')
    if exam_type not in ('mst', 'end_sem'):
        raise ValueError('Choose MST or End Sem')
    maximum = data.get('max_marks')
    if type(maximum) not in (int, float) or not math.isfinite(maximum) or not 0 < maximum <= 1000:
        raise ValueError('Maximum marks must be between 0 and 1000')
    rows = data.get('questions')
    if not isinstance(rows, list) or not 1 <= len(rows) <= 200:
        raise ValueError('Enter 1 to 200 question allocations')
    questions, groups, seen = [], {}, set()
    for row in rows:
        raw_id = row.get('question_id') if isinstance(row, dict) else None
        identifier = str(raw_id).strip() if isinstance(raw_id, (str, int)) and not isinstance(raw_id, bool) else ''
        if not identifier or len(identifier) > 60 or identifier in seen:
            raise ValueError('Question IDs must be nonempty and unique')
        seen.add(identifier)
        marks = row.get('max_marks')
        if type(marks) not in (int, float) or not math.isfinite(marks) or not 0 < marks <= maximum:
            raise ValueError(f'Invalid marks for question {identifier}')
        group = str(row.get('group') or '').strip()
        question = {'question_id': identifier, 'max_marks': marks, 'group': group}
        if group:
            count, selection = row.get('choose'), row.get('selection', 'exact')
            if type(count) is not int or count < 1 or selection not in ('exact', 'best', 'first'):
                raise ValueError('Optional groups need a positive choose count and exact, best or first selection')
            rule = groups.setdefault(group, {'question_ids': [], 'count': count, 'selection': selection, 'marks': marks})
            if (rule['count'], rule['selection'], rule['marks']) != (count, selection, marks):
                raise ValueError('Rows in an optional group must have the same marks, choose count and selection')
            rule['question_ids'].append(identifier)
            question.update(choose=count, selection=selection)
        questions.append(question)
    total = sum(q['max_marks'] for q in questions)
    choices = []
    for name, rule in groups.items():
        if rule['count'] > len(rule['question_ids']):
            raise ValueError('Choose count exceeds the number of questions in its group')
        total -= (len(rule['question_ids']) - rule['count']) * rule['marks']
        choices.append({k: v for k, v in rule.items() if k != 'marks'})
    if not math.isclose(total, maximum, abs_tol=0.001):
        raise ValueError('Question allocations after optional rules must equal maximum marks')
    return {'course_code': code, 'exam_type': exam_type, 'max_marks': maximum,
            'questions': questions, 'choice_groups': choices}


def scheme_id(code, exam_type):
    return f'{course_code(code)}:{exam_type}'
