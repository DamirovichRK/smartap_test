from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import threading

from datacls_models import InventoryResult, LogConfig

class BaseLogService(ABC):
    """Базовый класс для логирования - синглтон"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self, config: Optional[LogConfig] = None):
        if self._initialized:
            return
        
        self.config = config or LogConfig()
        self._setup_logging()
        self._initialized = True
    
    @abstractmethod
    def _setup_logging(self):
        """Тут каждая ОС настраивает логирование по-своему"""
        pass
    
    @abstractmethod
    def debug(self, msg: str):
        pass
    
    @abstractmethod
    def info(self, msg: str):
        pass
    
    @abstractmethod
    def warning(self, msg: str):
        pass
    
    @abstractmethod
    def error(self, msg: str):
        pass


class BaseInventoryService(ABC):
    """Базовый класс для сбора информации об ОС"""
    
    def __init__(self, logger: BaseLogService):
        self.logger = logger
        self.result_queue = None
    
    @abstractmethod
    def collect_os_info(self) -> InventoryResult:
        """Тут каждая ОС собирает информацию по-своему"""
        pass
    
    @abstractmethod
    def execute_task(self, task_data: Dict[str, Any]):
        """Выполнение задачи инвентаризации"""
        pass


class DispatcherInterface(ABC):
    """Интерфейс сервиса диспетчеризации"""
    
    @abstractmethod
    def start_workers(self):
        """Запускаем пул воркеров"""
        pass
    
    @abstractmethod
    def validate_command(self, command: str) -> bool:
        """Валидация команды по белому списку"""
        pass
    
    @abstractmethod
    def add_task(self, command: str) -> bool:
        """Добавляем задачу в очередь"""
        pass
    
    @abstractmethod
    def shutdown(self):
        """Корректно завершаем работу"""
        pass
