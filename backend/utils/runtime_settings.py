"""MongoDB-backed controls shared by the API and evaluation workers."""
import os

DEFAULT_PARALLELISM = int(os.getenv('VLLM_MAX_CONCURRENT_REQUESTS', os.getenv('BATCH_PROCESSING_MAX_WORKERS', '3')))
if not 1 <= DEFAULT_PARALLELISM <= 5:
    raise ValueError('Default evaluation concurrency must be between 1 and 5')
MAX_PARALLELISM = 5


def parallelism(db):
    record = db.settings.find_one({'_id': 'evaluation'}) or {}
    value = record.get('parallelism', DEFAULT_PARALLELISM)
    return value if type(value) is int and 1 <= value <= MAX_PARALLELISM else DEFAULT_PARALLELISM
