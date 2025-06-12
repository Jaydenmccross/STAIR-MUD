import json
import logging
import os
import threading

lock = threading.Lock()

def load_json(file_path):
    if not os.path.exists(file_path):
        logging.warning(f"File {file_path} does not exist. Returning empty data structure.")
        if file_path.endswith('.json') and 'rooms' not in file_path:
            return {}
        return []

    try:
        with lock:
            with open(file_path, 'r') as f:
                data = json.load(f)
        logging.debug(f"Loaded data from {file_path}.")
        return data
    except json.JSONDecodeError as e:
        logging.error(f"JSON decode error in {file_path}: {e}")
        if file_path.endswith('.json') and 'rooms' not in file_path:
            return {}
        return []
    except Exception as e:
        logging.error(f"Error loading JSON from {file_path}: {e}")
        if file_path.endswith('.json') and 'rooms' not in file_path:
            return {}

def save_json(file_path, data):
    try:
        with lock:
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=4)
        logging.debug(f"Saved data to {file_path}.")
    except Exception as e:
        logging.error(f"Error saving JSON to {file_path}: {e}")
