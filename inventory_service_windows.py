import winreg
import sys
from typing import Dict, Any
from datetime import datetime
import json
from pathlib import Path
import queue
import platform

from interfaces import BaseLogService, BaseInventoryService
from datacls_models import WindowsInventoryResult

REGISTRY_TIMEOUT = 5

class WindowsInventoryService(BaseInventoryService):
    """Сбор информации о Windows из реестра"""
    
    REGISTRY_PATHS = [
        r"Software\Microsoft\Windows NT\CurrentVersion",
        r"SOFTWARE\Microsoft\Windows NT\CurrentVersion",
    ]
    
    REGISTRY_HIVES = [
        winreg.HKEY_LOCAL_MACHINE,
        winreg.HKEY_CURRENT_USER,
    ]
    
    def __init__(self, logger: BaseLogService):
        super().__init__(logger)
        import platform
        self.is_64bit = platform.machine().endswith('64')
        self.logger.info(f"Python: {'64-битный' if self.is_64bit else '32-битный'}")
        
        # Проверяем доступ к реестру при инициализации
        self.registry_access = self._check_registry_access()
        self.logger.info(f"Доступ к реестру: {'✅' if self.registry_access else '❌'}")
    
    def _check_registry_access(self) -> bool:
        """
        Реальная проверка доступа к реестру
        Пробует открыть ключ и прочитать значение
        """
        try:
            # Пробуем открыть ключ с минимальными правами
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"Software\Microsoft\Windows NT\CurrentVersion",
                0,
                winreg.KEY_READ
            )
            
            # Пробуем прочитать значение
            try:
                winreg.QueryValueEx(key, "ProductName")
                can_read = True
            except:
                can_read = False
            
            winreg.CloseKey(key)
            return can_read
            
        except PermissionError:
            self.logger.debug("Нет прав на чтение реестра (нужны права администратора)")
            return False
        except FileNotFoundError:
            self.logger.debug("Ключ реестра не найден (странно для Windows)")
            return False
        except Exception as e:
            self.logger.debug(f"Неожиданная ошибка при проверке реестра: {e}")
            return False
    
    def _check_admin(self) -> bool:
        """Проверка прав администратора (отдельно от доступа к реестру)"""
        try:
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except:
            return False
    
    def _check_registry_permissions(self) -> Dict[str, bool]:
        """
        Детальная проверка прав на разные кусты реестра
        Возвращает словарь с правами для каждого пути
        """
        permissions = {}
        
        for hive_name, hive in [
            ("HKLM", winreg.HKEY_LOCAL_MACHINE),
            ("HKCU", winreg.HKEY_CURRENT_USER),
            ("HKCR", winreg.HKEY_CLASSES_ROOT),
        ]:
            try:
                # Пробуем открыть ключ
                test_key = winreg.OpenKey(hive, "", 0, winreg.KEY_READ)
                winreg.CloseKey(test_key)
                permissions[hive_name] = True
            except:
                permissions[hive_name] = False
        
        return permissions
    
    def _try_read_registry(self) -> Dict[str, str]:
        """Пытается прочитать реестр разными способами"""
        result = {}
        
        for hive in self.REGISTRY_HIVES:
            for path in self.REGISTRY_PATHS:
                # Пробуем разные флаги доступа
                for access_flags in [
                    winreg.KEY_READ,
                    winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
                    winreg.KEY_READ | winreg.KEY_WOW64_32KEY,
                ]:
                    try:
                        key = winreg.OpenKey(hive, path, 0, access_flags)
                        
                        # Читаем значения
                        values = {}
                        for value_name in ["ProductName", "CurrentBuild", "DisplayVersion", 
                                         "EditionID", "UBR", "InstallDate"]:
                            try:
                                value, _ = winreg.QueryValueEx(key, value_name)
                                values[value_name] = str(value)
                            except FileNotFoundError:
                                continue
                        
                        winreg.CloseKey(key)
                        
                        if values.get('ProductName'):
                            return values
                            
                    except PermissionError:
                        continue
                    except Exception as e:
                        continue
        
        return result
    
    def _try_wmi(self) -> Dict[str, str]:
        """Запасной вариант: пробуем WMI"""
        result = {}
        
        try:
            import subprocess
            cmd = 'wmic os get Caption,Version,BuildNumber /format:csv'
            output = subprocess.check_output(cmd, shell=True, text=True, timeout=5)
            
            lines = output.strip().split('\n')
            if len(lines) >= 2:
                parts = lines[1].split(',')
                if len(parts) >= 4:
                    result['ProductName'] = parts[1].strip()
                    result['CurrentBuild'] = parts[3].strip()
                    version_parts = parts[2].strip().split('.')
                    if len(version_parts) >= 2:
                        result['DisplayVersion'] = f"{version_parts[0]}.{version_parts[1]}"
                    
            self.logger.info("✅ Получили данные через WMI")
        except Exception as e:
            self.logger.debug(f"WMI не сработал: {e}")
        
        return result
    
    def _try_environment(self) -> Dict[str, str]:
        """Последний шанс: переменные окружения"""
        result = {}
        
        import os
        import platform
        
        if 'OS' in os.environ:
            result['ProductName'] = os.environ.get('OS', 'Windows')
        if 'COMPUTERNAME' in os.environ:
            result['EditionID'] = os.environ.get('COMPUTERNAME', '')
        
        if not result.get('ProductName'):
            result['ProductName'] = f"Windows {platform.release()}"
        if not result.get('CurrentBuild'):
            result['CurrentBuild'] = platform.version()
        
        self.logger.info("✅ Получили данные через environment")
        return result
    
    def collect_os_info(self) -> WindowsInventoryResult:
        """Сбор информации с запасными вариантами"""
        result = WindowsInventoryResult()
        
        try:
            # Обновляем статус доступа к реестру
            self.registry_access = self._check_registry_access()
            
            # Способ 1: Реестр
            if self.registry_access:
                self.logger.info("🔍 Пробуем прочитать реестр...")
                registry_data = self._try_read_registry()
                
                if registry_data:
                    result.ProductName = registry_data.get('ProductName', '')
                    result.CurrentBuild = registry_data.get('CurrentBuild', '')
                    result.DisplayVersion = registry_data.get('DisplayVersion', '')
                    result.EditionID = registry_data.get('EditionID', '')
                    result.UBR = registry_data.get('UBR', '')
                    result.InstallDate = registry_data.get('InstallDate', '')
                    self.logger.info("✅ Данные из реестра получены")
            else:
                self.logger.warning("⚠️ Нет доступа к реестру, пробуем другие источники")
            
            # Способ 2: WMI
            if not result.ProductName:
                self.logger.info("🔍 Пробуем WMI...")
                wmi_data = self._try_wmi()
                if wmi_data:
                    result.ProductName = wmi_data.get('ProductName', result.ProductName)
                    result.CurrentBuild = wmi_data.get('CurrentBuild', result.CurrentBuild)
                    result.DisplayVersion = wmi_data.get('DisplayVersion', result.DisplayVersion)
            
            # Способ 3: Окружение
            if not result.ProductName:
                self.logger.info("🔍 Пробуем переменные окружения...")
                env_data = self._try_environment()
                if env_data:
                    result.ProductName = env_data.get('ProductName', result.ProductName)
                    result.EditionID = env_data.get('EditionID', result.EditionID)
                    result.CurrentBuild = env_data.get('CurrentBuild', result.CurrentBuild)
            
            # Финальное сообщение
            if not result.ProductName:
                result.ProductName = "Windows (доступ запрещён)"
                self.logger.error("❌ Не удалось получить данные ни из одного источника")
            
        except Exception as e:
            self.logger.error(f"❌ Критическая ошибка: {e}")
        
        return result
    
    def execute_task(self, task_data: Dict[str, Any]):
        """Запускаем сбор информации"""
        self.logger.info("🔍 Начинаем сбор информации о Windows...")
        os_info = self.collect_os_info()
        
        if self.result_queue:
            try:
                result = {
                    'status': 'success',
                    'data': os_info.to_dict(),
                    'timestamp': datetime.now().isoformat(),
                    'os': 'windows'
                }
                
                self.result_queue.put(result, timeout=1)
                self.logger.info("✅ Результат в очереди")
            except queue.Full:
                self.logger.error("❌ Очередь забита!")
        
        self._save_to_file(os_info)
        self.logger.info("✅ Сбор информации завершён")
    
    def _save_to_file(self, os_info: WindowsInventoryResult):
        """Сохраняем JSON файл с детальной информацией о правах"""
        try:
            payload = os_info.to_dict()
            
            # Подробная информация о доступе к реестру
            registry_permissions = self._check_registry_permissions()
            
            payload['_diagnostic'] = {
                'timestamp': datetime.now().isoformat(),
                'python': {
                    'version': sys.version.split()[0],
                    'bits': '64' if self.is_64bit else '32',
                    'path': sys.executable
                },
                'windows': {
                    'version': platform.version(),
                    'release': platform.release()
                },
                'permissions': {
                    'registry_access': self.registry_access,  # Реальный доступ к реестру!
                    'is_admin': self._check_admin(),  # Права администратора (отдельно)
                    'registry_hives': registry_permissions,  # Права на каждый куст
                },
                'data_source': 'registry' if self.registry_access else 'fallback'
            }
            
            output_file = Path(__file__).parent / "payload.json"
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            self.logger.info(f"✅ Результат сохранён в {output_file}")
            
            # Логируем статус доступа
            if self.registry_access:
                self.logger.info("📊 Доступ к реестру: РАЗРЕШЁН")
            else:
                self.logger.warning("📊 Доступ к реестру: ЗАПРЕЩЁН (нужны права администратора)")
                
        except Exception as e:
            self.logger.error(f"❌ Ошибка при сохранении: {e}")
