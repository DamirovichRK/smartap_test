from dataclasses import dataclass
from typing import Dict, Optional

@dataclass
class InventoryResult:
    """Базовый результат инвентаризации"""
    ProductName: str = ""
    CurrentBuild: str = ""
    DisplayVersion: str = ""
    EditionID: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "os": {
                "ProductName": self.ProductName,
                "CurrentBuild": self.CurrentBuild,
                "DisplayVersion": self.DisplayVersion,
                "EditionID": self.EditionID
            }
        }

@dataclass
class WindowsInventoryResult(InventoryResult):
    """Расширение для Windows - добавляем специфичные поля"""
    InstallDate: Optional[str] = None
    UBR: str = ""
    
    def to_dict(self) -> Dict:
        data = super().to_dict()
        if self.UBR:
            data["os"]["UBR"] = self.UBR
        return data

@dataclass
class LinuxInventoryResult(InventoryResult):
    """Расширение для Linux - версия ядра и дистрибутив"""
    KernelVersion: str = ""
    Distribution: str = ""
    
    def to_dict(self) -> Dict:
        data = super().to_dict()
        data["os"]["KernelVersion"] = self.KernelVersion
        data["os"]["Distribution"] = self.Distribution
        return data

@dataclass
class LogConfig:
    """Настройки логирования"""
    level: str = "info"
    log_path: str = "."
    
@dataclass
class WorkersConfig:
    """Настройки воркеров"""
    inventory_workers: int = 1

@dataclass
class Task:
    """Задача для выполнения"""
    command: str
    timestamp: str
    id: str
    
    def to_dict(self) -> Dict:
        return {
            'command': self.command,
            'timestamp': self.timestamp,
            'id': self.id
        }

@dataclass
class TaskResult:
    """Результат выполнения задачи"""
    status: str
    data: Dict
    timestamp: str
    os: str
    
    def to_dict(self) -> Dict:
        return {
            'status': self.status,
            'data': self.data,
            'timestamp': self.timestamp,
            'os': self.os
        }
