"""Offline audit probes. Uses fake PDFs, mocked inference and mongomock only.

Run with backend dependencies plus backend/requirements-test.txt installed:
    python audit/reliability_probes.py
These report current behavior; they are not production acceptance tests.
"""
import io
import json
import sys
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import mongomock
from flask import Flask, request
from werkzeug.datastructures import MultiDict
from utils.workspace import Workspace, now
from utils.result_validation import validate_result
from utils import gemini_service


def run():
    findings = {}
    app = Flask(__name__)

    @app.post('/probe')
    def upload():
        return {'files': len(request.files.getlist('files'))}

    for n in (500, 501):
        data = MultiDict()
        for i in range(n):
            data.add('files', (io.BytesIO(b'fake pdf'), f'{i}.pdf'))
            data.add(f'path_{i}', f'FS3401/{i}.pdf')
        findings[f'multipart_{n}_files_status'] = app.test_client().post('/probe', data=data).status_code

    arbitrary = {'marks_awarded': 65, 'feedback': 'test', 'strengths': [], 'missing_points': [],
                 'question_scores': [{'question_id': 'INVENTED', 'max_marks': 100, 'marks_awarded': 65}]}
    findings['unknown_question_accepted'] = validate_result(arbitrary, 100, require_questions=True)['status']

    response = Mock(status_code=200)
    response.json.return_value = {'choices': [{'finish_reason': 'stop', 'message': {'content': '{}'}}]}
    with patch.object(gemini_service, 'VLLM_TOKENIZE_URL', ''), patch.object(gemini_service, 'inference_slot'), patch.object(gemini_service.requests, 'post', return_value=response) as post:
        gemini_service._call_vllm([], require_json=True)
        findings['json_request_has_schema_constraint'] = any(k in post.call_args.kwargs['json'] for k in ('response_format', 'structured_outputs', 'guided_json'))

    with tempfile.TemporaryDirectory() as temp:
        course = Path(temp) / 'FS3401'
        course.mkdir()
        for name in ('model_answer.pdf', 'question_paper.pdf', '101.pdf', '102.pdf'):
            (course / name).write_bytes(b'original fake pdf')
        db = mongomock.MongoClient().db
        service = Workspace(db)
        ids = service.prepare(temp, 'audit', 'end_sem', 100, 'audit')
        pdf = Mock()
        pdf.extract_text_from_pdf.return_value = 'extracted text'
        llm = Mock()
        llm.evaluate_answer.return_value = arbitrary
        (course / 'question_paper.pdf').write_bytes(b'changed after preparation')
        for sid in ids:
            service.enqueue(sid, 'audit')
            service.process(service.claim('owner'), pdf, llm, 'owner')
        findings['changed_question_paper_jobs'] = [j['state'] for j in db.jobs.find()]
        findings['answer_key_extractions_for_two_students'] = sum(c.args[0] == str(course / 'model_answer.pdf') for c in pdf.extract_text_from_pdf.call_args_list)

        with patch.object(db.attempts, 'find', wraps=db.attempts.find) as attempts, patch.object(db.jobs, 'find_one', wraps=db.jobs.find_one) as jobs, patch.object(db.sheets, 'find', wraps=db.sheets.find) as sheets:
            service.snapshot()
            findings['snapshot_collection_reads_for_two_sheets'] = attempts.call_count + jobs.call_count + sheets.call_count

        db.worker_leases.insert_one({'_id': 'inference', 'owner': 'owner', 'expires': now() + timedelta(seconds=90)})
        service.enqueue(ids[0], 'audit', force=True)
        job = service.claim('owner')
        original_update = db.attempts.update_one

        def lose_lease_at_save(query, update, **kwargs):
            if update.get('$set', {}).get('status') == 'completed':
                db.worker_leases.update_one({'_id': 'inference'}, {'$set': {'owner': 'replacement'}})
            return original_update(query, update, **kwargs)

        with patch.object(db.attempts, 'update_one', side_effect=lose_lease_at_save):
            service.process(job, pdf, llm, 'owner')
        findings['published_after_lease_changed_during_save'] = db.sheets.find_one({'_id': ids[0]})['active_attempt'] == job['attempt_id']

    return findings


if __name__ == '__main__':
    print(json.dumps(run(), indent=2))
