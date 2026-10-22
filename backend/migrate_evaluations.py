"""Non-destructive legacy failure classification. Dry run unless --apply is passed."""
import argparse
from utils.db_connection import db_connection
from utils.result_validation import valid_record


def classify(record):
    if valid_record(record):
        return None
    feedback = str(record.get('feedback', ''))
    if record.get('needs_review') or record.get('status') == 'error' or feedback.startswith(('Error during evaluation:', 'Evaluation error')):
        return {'status': 'error', 'needs_review': True, 'marks': None, 'percentage': None,
                'grade': None, 'error': {'type': 'LEGACY_FAILURE', 'message': feedback}}
    if record.get('status') is None:
        return {'status': 'needs_review', 'needs_review': True}
    return None


def run(apply=False):
    collection = db_connection.get_collection('evaluations')
    count = 0
    for record in collection.find():
        changes = classify(record)
        if changes:
            count += 1
            if apply:
                # Preserve previous fields for audit/recovery, even for invalid zeroes.
                original = {key: record.get(key) for key in changes}
                collection.update_one({'_id': record['_id'], 'updated_at': record.get('updated_at')},
                    {'$set': {**changes, 'migration_original': original}})
    print(f'{count} legacy records {"classified" if apply else "would be classified (dry run)"}. No records deleted.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    run(parser.parse_args().apply)
