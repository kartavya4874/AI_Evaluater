"""Offline audit demonstrations. Synthetic inputs only; no database or model calls.

Run from the project root:
    backend/venv/Scripts/python.exe audit/production_readiness_probes.py

These are diagnostic probes, not grading-accuracy measurements. A True value
identifies a weakness in the audited implementation, rather than desired behavior.
"""
import ast
import inspect
import json
from pathlib import Path
import re
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from utils import structured_grading as grading


def wrong_allocation_accepted():
    source = 'Q1 5 marks. Correct answer'
    candidate = {'questions': [{'question_id': '1', 'max_marks': 10,
                  'source_quote': 'Q1 5 marks', 'answer': 'Correct answer'}], 'choice_groups': []}
    try:
        grading.validate_rubric(candidate, source, 10)
        return True
    except grading.NeedsReview:
        return False


def own_header_rejected():
    return not grading.administrative_text('Page 1:')


def incorrect_mapping_can_produce_false_zero():
    student = 'Q1 First answer. Q2 Second answer.'
    rubric = {'questions': [
        {'question_id': '1', 'max_marks': 5, 'source_quote': 'Q1 5 marks', 'answer': 'First reference'},
        {'question_id': '2', 'max_marks': 5, 'source_quote': 'Q2 5 marks', 'answer': 'Second reference'}],
        'choice_groups': []}
    # Deliberately wrong mapping assigns BOTH explicit questions to Q1. No text
    # is lost. This simulates an AI error; it does not assert its real frequency.
    replies = iter([
        {'segments': [{'question_id': '1', 'text': student}]},
        {'marks_awarded': 2, 'feedback': 'Synthetic score', 'strengths': [], 'missing_points': [],
         'question_scores': [{'question_id': '1', 'max_marks': 5, 'marks_awarded': 2}]},
    ])
    provider = SimpleNamespace(question_workers=1,
        _generate_with_retry=lambda *args, **kwargs: SimpleNamespace(text=json.dumps(next(replies))))
    try:
        result = grading.evaluate(provider, student, 'References', 10, rubric=rubric)
    except grading.NeedsReview:
        return False
    return any(q['question_id'] == '2' and q['marks_awarded'] == 0 for q in result['question_scores'])


if __name__ == '__main__':
    print(json.dumps({
        'wrong_numeric_allocation_accepted': wrong_allocation_accepted(),
        'generated_page_header_rejected': own_header_rejected(),
        'incorrect_mapping_can_produce_false_zero': incorrect_mapping_can_produce_false_zero(),
        'synthetic_inputs_only': True,
        'accuracy_benchmark': False,
    }, indent=2))
