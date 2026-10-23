"""Run-level limits are persisted and do not reset when a worker reclaims a job."""
from datetime import datetime, timedelta, timezone
from config import Config
import hashlib
from pathlib import Path


class RunPaused(TimeoutError):
    pass


class ModelOutputError(ValueError):
    """Generation/schema failure, rather than evidence of an invalid source."""


_stage_sources = b''.join((Path(__file__).parent / name).read_bytes().replace(b'\r\n', b'\n')
                         for name in ('structured_grading.py', 'gemini_service.py', 'pdf_processor.py', 'result_validation.py'))
_model_versions = f'{Config.VLLM_MODEL_REVISION}:{Config.VLLM_TOKENIZER_REVISION}'.encode()
PIPELINE_REVISION = 'stabilization-v1:' + hashlib.sha256(_stage_sources + _model_versions).hexdigest()


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def run_deadline(job):
    return job.get('deadline_at') or ((job.get('run_started_at') or job.get('created_at') or utcnow())
                                      + timedelta(seconds=Config.EVALUATION_RUN_TIMEOUT_SECONDS))


def remaining_budget(job):
    seconds = (run_deadline(job) - utcnow()).total_seconds()
    if seconds <= 0:
        raise RunPaused('Run deadline reached. Saved progress is retained; explicitly retry after reviewing the cause.')
    return seconds
