import queue
import threading
import time
from datetime import datetime
from typing import Dict, Any

from interfaces import BaseLogService, BaseInventoryService, DispatcherInterface
from datacls_models import WorkersConfig, Task

# Константы безопасности
ALLOWED_COMMANDS = {'inventory'}
MAX_QUEUE_SIZE = 100
QUEUE_GET_TIMEOUT = 1

class DispatcherService(DispatcherInterface):
    """Сервис-диспетчер - распределяет задачи по воркерам"""
    
    def __init__(self, workers_config: WorkersConfig, logger: BaseLogService, 
                 inventory_service: BaseInventoryService):
        self.logger = logger
        self.workers_config = workers_config
        
        # Очереди с ограничением размера - защита от переполнения
        self.task_queue = queue.Queue(maxsize=MAX_QUEUE_SIZE)
        self.result_queue = queue.Queue(maxsize=MAX_QUEUE_SIZE)
        
        self.inventory_service = inventory_service
        self.inventory_service.result_queue = self.result_queue
        
        self.is_running = threading.Event()
        self.is_running.set()
        
        self.inventory_workers = []
    
    def start_workers(self):
        """Запускаем воркеров"""
        self.logger.info(f"Запускаем {self.workers_config.inventory_workers} воркеров")
        
        for i in range(self.workers_config.inventory_workers):
            worker = threading.Thread(
                target=self._inventory_worker_loop,
                name=f"Worker-{i+1}",
                daemon=True
            )
            worker.start()
            self.inventory_workers.append(worker)
    
    def _inventory_worker_loop(self):
        """Воркер крутится в цикле и ждёт задачи"""
        while self.is_running.is_set():
            try:
                task_data = self.task_queue.get(timeout=QUEUE_GET_TIMEOUT)
                self.logger.info(f"Воркер {threading.current_thread().name} взял задачу")
                
                # Валидация - только белый список!
                if self.validate_command(task_data.get('command', '')):
                    if task_data['command'] == 'inventory':
                        self.inventory_service.execute_task(task_data)
                    else:
                        self.logger.warning(f"Хм, команда {task_data['command']} не реализована")
                else:
                    self.logger.warning(f"Блокируем нелегитимную команду: {task_data.get('command')}")
                
                self.task_queue.task_done()
                
            except queue.Empty:
                # Нет задач - идём дальше
                continue
            except Exception as e:
                self.logger.error(f"Ошибка в воркере: {e}")
    
    def validate_command(self, command: str) -> bool:
        """Проверяем команду по белому списку"""
        # Оставляем только буквы - защита от инъекций
        command = ''.join(c for c in command if c.isalpha())
        return command in ALLOWED_COMMANDS
    
    def add_task(self, command: str) -> bool:
        """Добавляем задачу в очередь"""
        if not self.validate_command(command):
            self.logger.warning(f"Попытка добавить запрещённую команду: {command}")
            return False
        
        task = Task(
            command=command,
            timestamp=datetime.now().isoformat(),
            id=f"{int(time.time())}_{threading.get_ident()}"
        )
        
        try:
            self.task_queue.put(task.to_dict(), timeout=QUEUE_GET_TIMEOUT)
            self.logger.info(f"Задача {command} добавлена в очередь. В очереди: {self.task_queue.qsize()}")
            return True
        except queue.Full:
            self.logger.error("Очередь задач переполнена! Задача отклонена.")
            return False
    
    def shutdown(self):
        """Корректно завершаем работу"""
        self.logger.info("Останавливаем диспетчер...")
        self.is_running.clear()
        
        for worker in self.inventory_workers:
            worker.join(timeout=5)
        
        self.logger.info("Диспетчер остановлен")
