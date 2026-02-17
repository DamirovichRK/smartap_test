import platform

from interfaces import BaseLogService, BaseInventoryService
from datacls_models import LogConfig

# Определяем текущую ОС один раз при импорте
CURRENT_OS = platform.system().lower()

class ServiceFactory:
    """Фабрика - создаёт нужные сервисы под конкретную ОС"""
    
    @staticmethod
    def create_log_service(config: LogConfig) -> BaseLogService:
        """Создаём логгер под текущую ОС"""
        if CURRENT_OS == 'windows':
            from log_service_windows import WindowsLogService
            return WindowsLogService(config)
        elif CURRENT_OS == 'linux':
            from log_service_linux import LinuxLogService
            return LinuxLogService(config)
        else:
            raise OSError(f"ОС {CURRENT_OS} не поддерживается. Нужен Windows или Linux.")
    
    @staticmethod
    def create_inventory_service(logger: BaseLogService) -> BaseInventoryService:
        """Создаём сборщик информации под текущую ОС"""
        if CURRENT_OS == 'windows':
            from inventory_service_windows import WindowsInventoryService
            return WindowsInventoryService(logger)
        elif CURRENT_OS == 'linux':
            from inventory_service_linux import LinuxInventoryService
            return LinuxInventoryService(logger)
        else:
            raise OSError(f"ОС {CURRENT_OS} не поддерживается. Нужен Windows или Linux.")
    
    @staticmethod
    def get_current_os() -> str:
        """Возвращает название текущей ОС"""
        return CURRENT_OS
    
    @staticmethod
    def is_windows() -> bool:
        """Проверка: текущая ОС - Windows"""
        return CURRENT_OS == 'windows'
    
    @staticmethod
    def is_linux() -> bool:
        """Проверка: текущая ОС - Linux"""
        return CURRENT_OS == 'linux'
