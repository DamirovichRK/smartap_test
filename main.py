import argparse
import platform
import sys

# Наши модули
from config_loader import ConfigLoader
from service_factory import ServiceFactory
from dispatcher import DispatcherService
from utils import read_commands, parse_arguments, print_banner, print_summary

# Определяем ОС при старте
CURRENT_OS = platform.system().lower()

def main():
    """Тут всё начинается"""
    print_banner()
    
    try:
        # Загружаем конфиг
        log_config, workers_config = ConfigLoader.load_config()
        
        # Создаём сервисы через фабрику
        logger = ServiceFactory.create_log_service(log_config)
        inventory_service = ServiceFactory.create_inventory_service(logger)
        
        logger.info("="*50)
        logger.info(f"🚀 Запуск на {platform.system()}")
        logger.info("="*50)
        
        # Парсим аргументы
        try:
            args = parse_arguments()
            logger.info(f"📄 Файл с командами: {args.command_file}")
        except SystemExit:
            logger.error("❌ Неправильные аргументы командной строки")
            return
        except Exception as e:
            logger.error(f"❌ Ошибка при разборе аргументов: {e}")
            return
        
        # Читаем команды
        commands = read_commands(args.command_file)
        logger.info(f"📋 Прочитано команд: {len(commands)}")
        
        if not commands:
            logger.warning("⚠️ Нет команд для выполнения")
            return
        
        # Запускаем диспетчер
        dispatcher = DispatcherService(workers_config, logger, inventory_service)
        dispatcher.start_workers()
        
        # Обрабатываем команды
        inventory_count = 0
        for cmd in commands:
            if cmd == 'inventory':
                if dispatcher.add_task(cmd):
                    inventory_count += 1
            else:
                logger.info(f"⏭️  Команда '{cmd}' проигнорирована (не inventory)")
        
        logger.info(f"➕ Добавлено задач: {inventory_count}")
        
        # Ждём выполнения
        if inventory_count > 0:
            logger.info("⏳ Ждём выполнения задач...")
            try:
                dispatcher.task_queue.join()
            except KeyboardInterrupt:
                logger.warning("🛑 Прервано пользователем")
            except Exception as e:
                logger.error(f"❌ Ошибка при ожидании: {e}")
            finally:
                dispatcher.shutdown()
        
        print_summary(inventory_count)
        logger.info("✅ Работа завершена")
        
    except OSError as e:
        print(f"❌ ОШИБКА: {e}")
        print("   Программа работает только на Windows и Linux")
        sys.exit(1)
    except Exception as e:
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
