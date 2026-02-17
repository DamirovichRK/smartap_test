import logging
from pathlib import Path

from interfaces import BaseLogService

class WindowsLogService(BaseLogService):
    """Логирование под Windows"""
    
    def _setup_logging(self):
        """Настройка логгера для Windows"""
        try:
            level_map = {
                'debug': logging.DEBUG,
                'info': logging.INFO,
                'warning': logging.WARNING,
                'error': logging.ERROR
            }
            
            log_level = level_map.get(self.config.level.lower(), logging.INFO)
            log_dir = Path(self.config.log_path)
            
            if not log_dir.exists():
                log_dir = Path.cwd()
                print(f"Папка для логов не найдена, пишем сюда: {log_dir}")
            
            log_file = log_dir / "log.txt"
            
            logging.basicConfig(
                level=log_level,
                format='%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S',
                handlers=[
                    logging.FileHandler(log_file, encoding='utf-8', mode='a'),
                    logging.StreamHandler()
                ]
            )
            
            self.logger = logging.getLogger('WindowsCollector')
            self.logger.info(f"Логирование поднято. Уровень: {self.config.level}")
            self.logger.info(f"Лог-файл: {log_file}")
            
        except Exception as e:
            print(f"ААА! Логирование сломалось: {e}")
            logging.basicConfig(level=logging.INFO)
            self.logger = logging.getLogger('WindowsCollector')
    
    def debug(self, msg: str):
        self.logger.debug(msg)
    
    def info(self, msg: str):
        self.logger.info(msg)
    
    def warning(self, msg: str):
        self.logger.warning(msg)
    
    def error(self, msg: str):
        self.logger.error(msg)
