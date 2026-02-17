""" ВНИМАНИЕ: код я тестировал исключительно на ubuntu 16.04, просто потому что она у меня установлена
проверки под все остальные ОС мне предложил github-copilot и я НЕ ЗНАЮ сработают ли они, или нет
по идее, ядро одно у них одно и то же, просто отличается путь к ос-папкам
"""
import os
import platform
import subprocess
import re
import json
from pathlib import Path
from typing import Dict, Any
from datetime import datetime
import queue
import sys
import pwd
import grp
import shutil

from interfaces import BaseInventoryService, BaseLogService
from datacls_models import LinuxInventoryResult

SUBPROCESS_TIMEOUT = 3


class LinuxInventoryService(BaseInventoryService):
    """Сбор информации о Linux с проверкой прав доступа к файлам"""
    
    OS_RELEASE_PATH = "/etc/os-release"
    DEBIAN_VERSION_PATH = "/etc/debian_version"
    ASTRA_RELEASE_PATH = "/etc/astra-release"
    ASTRA_VERSION_PATH = "/etc/astra/version"
    REDOS_RELEASE_PATH = "/etc/redos-release"
    LSB_RELEASE_PATH = "/etc/lsb-release"
    
    def __init__(self, logger: BaseLogService):
        super().__init__(logger)
        
        # Проверяем права на чтение системных файлов
        self.file_permissions = self._check_file_permissions()
        self.logger.info(f"Доступ к системным файлам: {self._format_permissions()}")
    
    def _check_file_permissions(self) -> Dict[str, bool]:
        """
        Проверяет, есть ли у текущего пользователя доступ к системным файлам
        """
        permissions = {}
        files_to_check = [
            self.OS_RELEASE_PATH,
            self.DEBIAN_VERSION_PATH,
            self.ASTRA_RELEASE_PATH,
            self.ASTRA_VERSION_PATH,
            self.REDOS_RELEASE_PATH,
            self.LSB_RELEASE_PATH,
            "/proc/version",
        ]
        
        for file_path in files_to_check:
            if os.path.exists(file_path):
                # Проверяем доступ на чтение
                can_read = os.access(file_path, os.R_OK)
                permissions[file_path] = can_read
                
                # Дополнительная информация о файле
                try:
                    stat = os.stat(file_path)
                    file_owner = pwd.getpwuid(stat.st_uid).pw_name
                    file_group = grp.getgrgid(stat.st_gid).gr_name
                    file_mode = oct(stat.st_mode)[-3:]
                    
                    self.logger.debug(f"Файл {file_path}: владелец={file_owner}, группа={file_group}, права={file_mode}, доступ={'✅' if can_read else '❌'}")
                except:
                    pass
            else:
                permissions[file_path] = False
        
        return permissions
    
    def _format_permissions(self) -> str:
        """Красиво форматирует статус прав доступа"""
        accessible = sum(1 for v in self.file_permissions.values() if v)
        total = len(self.file_permissions)
        return f"{accessible}/{total} файлов доступно"
    
    def _check_root(self) -> bool:
        """Проверяет, запущен ли процесс от root"""
        try:
            return os.geteuid() == 0
        except:
            return False
    
    def _get_process_info(self) -> Dict[str, Any]:
        """Информация о текущем процессе"""
        try:
            uid = os.getuid()
            euid = os.geteuid()
            gid = os.getgid()
            egid = os.getegid()
            
            return {
                'uid': uid,
                'euid': euid,
                'gid': gid,
                'egid': egid,
                'user': pwd.getpwuid(uid).pw_name,
                'effective_user': pwd.getpwuid(euid).pw_name if euid != uid else 'same',
                'is_root': self._check_root(),
            }
        except:
            return {}
    
    def collect_os_info(self) -> LinuxInventoryResult:
        """Определяем дистрибутив и собираем информацию"""
        result = LinuxInventoryResult()
        
        try:
            # Обновляем информацию о правах
            self.file_permissions = self._check_file_permissions()
            
            # Пробуем читать файлы в зависимости от прав
            os_release_info = self._safe_read_os_release()
            
            if not os_release_info or not self._is_supported_distro(os_release_info):
                os_release_info = self._detect_specific_distro()
            
            kernel_version = self._get_kernel_version()
            result.KernelVersion = kernel_version
            result.CurrentBuild = kernel_version.split('-')[0] if kernel_version else ""
            
            if os_release_info:
                result.ProductName = os_release_info.get('PRETTY_NAME', 
                                    os_release_info.get('NAME', 'Linux'))
                result.DisplayVersion = os_release_info.get('VERSION_ID', 'Unknown')
                result.EditionID = os_release_info.get('ID', 'linux')
                result.Distribution = os_release_info.get('ID', 'linux')
                
                if not result.CurrentBuild:
                    result.CurrentBuild = os_release_info.get('VERSION_ID', '')
            else:
                result.ProductName = f"Linux {platform.release()}"
                result.DisplayVersion = platform.release()
                result.EditionID = "linux"
                result.CurrentBuild = platform.release()
                result.Distribution = "unknown"
                self.logger.warning("Не удалось определить дистрибутив")
            
            self.logger.info(f"Нашли ОС: {result.ProductName}")
            self.logger.info(f"Ядро: {result.KernelVersion}")
            
        except Exception as e:
            self.logger.error(f"Ошибка при сборе информации: {e}")
        
        return result
    
    def _safe_read_os_release(self) -> Dict[str, str]:
        """Безопасно читает os-release с проверкой прав"""
        result = {}
        
        if not os.path.exists(self.OS_RELEASE_PATH):
            return result
        
        # Проверяем права на чтение
        if not self.file_permissions.get(self.OS_RELEASE_PATH, False):
            self.logger.warning(f"Нет прав на чтение {self.OS_RELEASE_PATH}")
            return result
        
        try:
            with open(self.OS_RELEASE_PATH, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and '=' in line and not line.startswith('#'):
                        key, value = line.split('=', 1)
                        value = value.strip('"\'')
                        result[key] = value
                        
        except Exception as e:
            self.logger.error(f"Не смогли прочитать os-release: {e}")
        
        return result
    
    def _is_supported_distro(self, distro_info: Dict[str, str]) -> bool:
        """Проверяет, поддерживается ли дистрибутив"""
        distro_id = distro_info.get('ID', '').lower()
        supported = ['debian', 'ubuntu', 'redos', 'astra']
        
        for supported_distro in supported:
            if supported_distro in distro_id:
                return True
        
        distro_name = distro_info.get('NAME', '').lower()
        for supported_distro in supported:
            if supported_distro in distro_name:
                return True
                
        return False
    
    def _detect_specific_distro(self) -> Dict[str, str]:
        """Определяет конкретные дистрибутивы по их файлам"""
        result = {}
        
        if self.file_permissions.get(self.ASTRA_RELEASE_PATH, False) or \
           self.file_permissions.get(self.ASTRA_VERSION_PATH, False):
            result = self._detect_astra_linux()
            self.logger.info("Определили Astra Linux")
        
        elif self.file_permissions.get(self.REDOS_RELEASE_PATH, False):
            result = self._detect_redos()
            self.logger.info("Определили RedOS")
        
        elif self.file_permissions.get(self.DEBIAN_VERSION_PATH, False):
            result = self._detect_debian_based()
            self.logger.info("Определили Debian/Ubuntu")
        
        return result
    
    def _detect_astra_linux(self) -> Dict[str, str]:
        """Определяет Astra Linux"""
        result = {
            'ID': 'astra',
            'NAME': 'Astra Linux',
            'PRETTY_NAME': 'Astra Linux'
        }
        
        try:
            if self.file_permissions.get(self.ASTRA_VERSION_PATH, False):
                with open(self.ASTRA_VERSION_PATH, 'r', encoding='utf-8') as f:
                    version = f.read().strip()
                    result['VERSION_ID'] = version
                    result['PRETTY_NAME'] = f"Astra Linux {version}"
            elif self.file_permissions.get(self.ASTRA_RELEASE_PATH, False):
                with open(self.ASTRA_RELEASE_PATH, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    result['PRETTY_NAME'] = content
                    version_match = re.search(r'(\d+\.?\d*)', content)
                    if version_match:
                        result['VERSION_ID'] = version_match.group(1)
        except Exception as e:
            self.logger.error(f"Ошибка при определении Astra Linux: {e}")
        
        return result
    
    def _detect_redos(self) -> Dict[str, str]:
        """Определяет RedOS"""
        result = {
            'ID': 'redos',
            'NAME': 'RedOS',
            'PRETTY_NAME': 'RedOS'
        }
        
        try:
            if self.file_permissions.get(self.REDOS_RELEASE_PATH, False):
                with open(self.REDOS_RELEASE_PATH, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    result['PRETTY_NAME'] = content
                    version_match = re.search(r'(\d+\.?\d*)', content)
                    if version_match:
                        result['VERSION_ID'] = version_match.group(1)
        except Exception as e:
            self.logger.error(f"Ошибка при определении RedOS: {e}")
        
        return result
    
    def _detect_debian_based(self) -> Dict[str, str]:
        """Определяет Debian и Ubuntu"""
        result = {}
        
        try:
            if self.file_permissions.get(self.LSB_RELEASE_PATH, False):
                with open(self.LSB_RELEASE_PATH, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if '=' in line:
                            key, value = line.split('=', 1)
                            value = value.strip('"\'')
                            if key == 'DISTRIB_ID':
                                if 'ubuntu' in value.lower():
                                    result['ID'] = 'ubuntu'
                                    result['NAME'] = 'Ubuntu'
                                else:
                                    result['ID'] = 'debian'
                                    result['NAME'] = 'Debian'
                            elif key == 'DISTRIB_RELEASE':
                                result['VERSION_ID'] = value
                            elif key == 'DISTRIB_DESCRIPTION':
                                result['PRETTY_NAME'] = value
            
            if not result and self.file_permissions.get(self.DEBIAN_VERSION_PATH, False):
                with open(self.DEBIAN_VERSION_PATH, 'r', encoding='utf-8') as f:
                    version = f.read().strip()
                    result['ID'] = 'debian'
                    result['NAME'] = 'Debian'
                    result['VERSION_ID'] = version
                    result['PRETTY_NAME'] = f"Debian GNU/Linux {version}"
                    
        except Exception as e:
            self.logger.error(f"Ошибка при определении Debian/Ubuntu: {e}")
        
        return result
    
    def _get_kernel_version(self) -> str:
        """Узнаёт версию ядра"""
        # Пробуем /proc/version
        if os.path.exists('/proc/version') and os.access('/proc/version', os.R_OK):
            try:
                with open('/proc/version', 'r', encoding='utf-8') as f:
                    version_line = f.read().strip()
                    version_match = re.search(r'version\s+([^\s]+)', version_line)
                    if version_match:
                        return version_match.group(1)
            except Exception as e:
                self.logger.error(f"Не смогли прочитать /proc/version: {e}")
        
        # Пробуем uname
        try:
            # В теории, возможна инъекция кода вместо uname, по этому закроем его на проверку 
            uname_path = shutil.which('uname')
            if uname_path and uname_path.startswith('/bin/'):
                result = subprocess.run(['uname', '-r'], 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=SUBPROCESS_TIMEOUT,
                                  check=False)
                if result.returncode == 0:
                    return result.stdout.strip()
        except Exception as e:
            self.logger.error(f"uname не работает: {e}")
        
        return platform.release()
    
    def execute_task(self, task_data: Dict[str, Any]):
        """Запускает сбор информации"""
        self.logger.info("Собираем информацию о Linux...")
        os_info = self.collect_os_info()
        
        if self.result_queue:
            try:
                result = {
                    'status': 'success',
                    'data': os_info.to_dict(),
                    'timestamp': datetime.now().isoformat(),
                    'os': 'linux'
                }
                
                self.result_queue.put(result, timeout=1)
                self.logger.info("Результат в очереди")
            except queue.Full:
                self.logger.error("Очередь забита!")
        
        self._save_to_file(os_info)
        self.logger.info("Информация о Linux собрана")
    
    def _save_to_file(self, os_info: LinuxInventoryResult):
        """Сохраняет JSON с информацией о правах доступа"""
        try:
            payload = os_info.to_dict()
            
            # Информация о правах доступа
            process_info = self._get_process_info()
            
            payload['_diagnostic'] = {
                'timestamp': datetime.now().isoformat(),
                'python': {
                    'version': sys.version.split()[0],
                    'path': sys.executable
                },
                'linux': {
                    'distribution': platform.freedesktop_os_release().get('NAME', 'unknown') if hasattr(platform, 'freedesktop_os_release') else 'unknown',
                    'kernel': platform.release()
                },
                'permissions': {
                    'is_root': self._check_root(),
                    'process': process_info,
                    'file_access': self.file_permissions,  # Реальный доступ к файлам!
                    'accessible_files': self._format_permissions()
                }
            }
            
            output_file = Path(__file__).parent / "payload.json"
            
            try:
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(payload, f, ensure_ascii=False, indent=2)
                self.logger.info(f"Результат сохранён в {output_file}")
            except (PermissionError, OSError):
                temp_file = Path("/tmp") / "payload.json"
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(payload, f, ensure_ascii=False, indent=2)
                self.logger.warning(f"Нет прав на запись, сохранили в {temp_file}")
                    
        except Exception as e:
            self.logger.error(f"Ошибка при сохранении файла: {e}")
