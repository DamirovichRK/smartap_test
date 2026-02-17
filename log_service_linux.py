import logging
import os
from pathlib import Path

from interfaces import BaseLogService

class LinuxLogService(BaseLogService):
    """Логирование под Linux"""
    
    def _setup_logging(self):
        """Настройка логгера для Linux"""
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
                log_dir = Path.home() / ".cache" / "os-collector"
                log_dir.mkdir(parents=True, exist_ok=True)
                print(f"Папки для логов нет, создали: {log_dir}")
            
            if not os.access(log_dir, os.W_OK):
                log_dir = Path.home() / ".cache" / "os-collector"
                log_dir.mkdir(parents=True, exist_ok=True)
                print(f"Нет прав на запись, пишем сюда: {log_dir}")
            
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
            
            self.logger = logging.getLogger('LinuxCollector')
            self.logger.info(f"Логирование поднято. Уровень: {self.config.level}")
            self.logger.info(f"Лог-файл: {log_file}")
            
        except Exception as e:
            print(f"Не смогли настроить логирование: {e}")
            logging.basicConfig(level=logging.INFO)
            self.logger = logging.getLogger('LinuxCollector')
    
    def debug(self, msg: str):
        self.logger.debug(msg)
    
    def info(self, msg: str):
        self.logger.info(msg)
    
    def warning(self, msg: str):
        self.logger.warning(msg)
    
    def error(self, msg: str):
        self.logger.error(msg)
