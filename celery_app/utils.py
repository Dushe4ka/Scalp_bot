import sys
from pathlib import Path
from functools import wraps

def setup_project_path():
    """
    Добавляет корневую директорию проекта в PYTHONPATH
    Вызывается внутри задач Celery для работы в форкнутых процессах
    """
    project_root = Path(__file__).parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
