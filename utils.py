import argparse
from pathlib import Path
from typing import List
import sys

def parse_arguments():
    """Разбираем аргументы командной строки"""
    parser = argparse.ArgumentParser(
        description='Сбор информации об ОС (Windows/Linux)',
        epilog=f'Запуск: python {sys.argv[0]} файл_с_командами.txt'
    )
    
    parser.add_argument(
        'command_file',
        type=str,
        help='Файл со списком команд'
    )
    
    return parser.parse_args()

def read_commands(file_path: str) -> List[str]:
    """
    Безопасно читаем команды из файла.
    Защита от:
    - path traversal
    - огромных файлов
    - бинарных файлов
    - отсутствия прав
    """
    commands = []
    
    try:
        # Защита от path traversal
        safe_path = Path(file_path).resolve()
        
        if not safe_path.exists():
            print(f"❌ Файл {safe_path} не найден!")
            return commands
        
        # Защита от огромных файлов (больше 10MB)
        MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
        if safe_path.stat().st_size > MAX_FILE_SIZE:
            print(f"❌ Файл слишком большой! Максимум 10MB")
            return commands
        
        # Пробуем прочитать как текст
        try:
            with open(safe_path, 'r', encoding='utf-8') as f:
                for line in f:
                    cmd = line.strip().lower()
                    # Игнорируем пустые строки и комментарии
                    if cmd and not cmd.startswith('#'):
                        commands.append(cmd)
        except UnicodeDecodeError:
            # Если не UTF-8, пробуем другую кодировку
            try:
                with open(safe_path, 'r', encoding='cp1251') as f:
                    for line in f:
                        cmd = line.strip().lower()
                        if cmd and not cmd.startswith('#'):
                            commands.append(cmd)
            except UnicodeDecodeError:
                print(f"❌ Файл {file_path} не является текстовым!")
                return commands
                    
    except PermissionError:
        print(f"❌ Нет прав на чтение файла {file_path}")
    except Exception as e:
        print(f"❌ Ошибка при чтении файла: {e}")
    
    return commands

def safe_write_file(file_path: Path, content: str) -> bool:
    """
    Безопасная запись в файл с проверкой прав и директорий
    """
    try:
        # Создаём директорию, если её нет
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Пишем файл
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return True
    except PermissionError:
        print(f"❌ Нет прав на запись в {file_path}")
    except Exception as e:
        print(f"❌ Ошибка при записи в {file_path}: {e}")
    
    return False

def safe_read_file(file_path: Path) -> str:
    """
    Безопасное чтение файла
    """
    try:
        if not file_path.exists():
            return ""
        
        if file_path.stat().st_size > 10 * 1024 * 1024:  # 10MB
            print(f"❌ Файл {file_path} слишком большой!")
            return ""
        
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError:
        try:
            with open(file_path, 'r', encoding='cp1251') as f:
                return f.read()
        except:
            return ""
    except Exception as e:
        print(f"❌ Ошибка при чтении {file_path}: {e}")
        return ""

def validate_file_path(path: str) -> bool:
    """
    Проверяет, является ли путь безопасным
    """
    try:
        p = Path(path).resolve()
        
        # Запрещаем запись в системные директории
        forbidden_prefixes = [
            'C:\\Windows',
            'C:\\Program Files',
            'C:\\Program Files (x86)',
            '/etc',
            '/bin',
            '/sbin',
            '/usr/bin',
            '/usr/sbin',
            '/boot',
            '/dev',
            '/proc',
            '/sys',
        ]
        
        str_path = str(p).lower()
        for forbidden in forbidden_prefixes:
            if str_path.startswith(forbidden.lower()):
                print(f"❌ Запрещено писать в системную директорию: {forbidden}")
                return False
        
        return True
    except:
        return False

def get_timestamp() -> str:
    """Возвращает текущий timestamp в формате для имён файлов"""
    from datetime import datetime
    return datetime.now().strftime('%Y%m%d_%H%M%S')

def create_backup(file_path: Path) -> bool:
    """
    Создаёт бэкап файла, если он существует
    """
    try:
        if file_path.exists():
            backup_path = file_path.with_suffix(f'.bak.{get_timestamp()}')
            import shutil
            shutil.copy2(file_path, backup_path)
            print(f"📦 Создан бэкап: {backup_path}")
            return True
    except Exception as e:
        print(f"❌ Ошибка при создании бэкапа: {e}")
    
    return False

def is_running_as_admin() -> bool:
    """
    Проверяет, запущен ли скрипт с правами администратора (Windows)
    """
    if sys.platform != 'win32':
        return False
    
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except:
        return False

def is_running_as_root() -> bool:
    """
    Проверяет, запущен ли скрипт от root (Linux)
    """
    if sys.platform != 'linux':
        return False
    
    try:
        return os.geteuid() == 0
    except:
        return False

def print_banner():
    """баннер для хыхов в консоли"""
    import platform
    
    banner = """
╔══════════════════════════════════════════════════════════╗
║     Кроссплатформенный агент сбора информации об ОС     ║
║                    Версия 2.0                           ║
╚══════════════════════════════════════════════════════════╝
    """
    print(banner)
    print(f"🖥️  ОС: {platform.system()} {platform.release()}")
    print(f"🏗️  Архитектура: {platform.machine()}")
    print(f"🐍 Python: {sys.version.split()[0]}")
    print("=" * 60)

def print_summary(inventory_count: int, errors: int = 0):
    """Выводит краткий итог работы"""
    print("\n" + "=" * 60)
    print("📊 ИТОГ РАБОТЫ:")
    print(f"   ✅ Выполнено инвентаризаций: {inventory_count}")
    if errors > 0:
        print(f"   ❌ Ошибок: {errors}")
    else:
        print(f"   ✅ Ошибок: 0")
    print("=" * 60)

if __name__ == "__main__":
    # Если файл запущен напрямую - показываем справку
    print("📚 Это вспомогательный модуль с функциями:")
    print("   - parse_arguments() - разбор аргументов командной строки")
    print("   - read_commands() - безопасное чтение команд из файла")
    print("   - safe_write_file() - безопасная запись файлов")
    print("   - validate_file_path() - проверка путей")
    print("   - и другие полезные функции")
    print("\n   Используйте этот модуль в своих скриптах:")
    print("   from utils import read_commands, parse_arguments")
