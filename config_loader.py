import configparser
import contextlib
from pathlib import Path
import platform

from datacls_models import LogConfig, WorkersConfig

CURRENT_OS = platform.system().lower()

class ConfigLoader:
    """Загружаем конфиг, если он есть"""
    
    @staticmethod
    def load_config() -> tuple[LogConfig, WorkersConfig]:
        config_path = Path(__file__).parent / "config.ini"

        log_config = LogConfig()
        workers_config = WorkersConfig()

        # Пути по умолчанию для разных ОС
        if CURRENT_OS == 'windows':
            log_config.log_path = r"C:\Program Files (x86)\TestCollector"
        else:
            log_config.log_path = str(Path.home() / ".cache" / "os-collector")

        if not config_path.exists():
            print(f"Конфиг {config_path} не найден, используем значения по умолчанию")
            return log_config, workers_config

        try:
            config = configparser.ConfigParser()
            config.read(config_path, encoding='utf-8')

            if 'logging' in config:
                if 'level' in config['logging']:
                    level = config['logging']['level'].lower()
                    if level in ['debug', 'info', 'warning', 'error']:
                        log_config.level = level

                if 'log_path' in config['logging']:
                    log_config.log_path = config['logging']['log_path']
            
            if 'workers' in config and 'InventoryWorkers' in config['workers']:
                with contextlib.suppress(ValueError):
                    workers = int(config['workers']['InventoryWorkers'])
                    # Ограничиваем разумными пределами
                    workers_config.inventory_workers = max(1, min(workers, 10))
        except Exception as e:
            print(f"Ошибка при чтении конфига: {e}")

        return log_config, workers_config
