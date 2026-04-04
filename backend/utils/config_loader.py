import json
import os
import logging

logger = logging.getLogger(__name__)


class ConfigLoader:
    @staticmethod
    def load_root_config(root_directory):
        """Load config.json from root directory and extract max_marks."""
        config_path = os.path.join(root_directory, 'config.json')

        if not os.path.exists(config_path):
            raise FileNotFoundError(f"config.json not found in {root_directory}")

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                max_marks = config.get('max_marks')

                if max_marks is None:
                    raise ValueError("max_marks not defined in config.json")

                return {
                    'max_marks': int(max_marks),
                    'metadata': config.get('metadata', {}),
                    'evaluation_date': config.get('evaluation_date', ''),
                    'institution': config.get('institution', '')
                }
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in config.json: {str(e)}")
