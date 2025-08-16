"""
ScanResult data model for representing directory scan results
"""

import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from .utils import Colors, format_size

class ScanResult:
    """Represents the scan result for a single directory"""
    
    def __init__(self, directory: str, has_scan: bool = False, scan_data: Optional[Dict] = None, clean_data: Optional[Dict] = None):
        self.directory = directory
        self.name = os.path.basename(directory)
        self.has_scan = has_scan
        self.scan_data = scan_data or {}
        self.clean_data = clean_data or {}
    
    @property
    def status_icon(self) -> str:
        """Returns colored status icon"""
        if self.has_scan:
            return f"{Colors.GREEN}✓{Colors.END}"
        return f"{Colors.RED}✗{Colors.END}"
    
    @property
    def size_bytes(self) -> int:
        """Returns size in bytes, 0 if no scan data available"""
        if not self.has_scan:
            return 0
        size = self.scan_data.get('size_bytes')
        return size if size is not None else 0
    
    @property
    def file_count(self) -> int:
        """Returns number of files, 0 if no scan data available"""
        if not self.has_scan:
            return 0
        count = self.scan_data.get('file_count')
        return count if count is not None else 0
    
    @property
    def scan_time(self) -> Optional[str]:
        """Returns scan timestamp"""
        return self.scan_data.get('scan_time')
    
    @property
    def directory_mtime(self) -> Optional[str]:
        """Returns directory modification time"""
        mtime_epoch = self.scan_data.get('directory_mtime')
        if mtime_epoch:
            try:
                return datetime.fromtimestamp(int(mtime_epoch), timezone.utc).strftime('%Y-%m-%d')
            except (ValueError, TypeError):
                return None
        return None
    
    @property
    def bytes_cleaned(self) -> int:
        """Returns bytes that would be cleaned, 0 if no clean data available"""
        if not self.has_clean_data:
            return 0
        cleaned = self.clean_data.get('bytes_cleaned')
        return cleaned if cleaned is not None else 0
    
    @property
    def has_clean_data(self) -> bool:
        """Returns whether clean data is available"""
        return bool(self.clean_data)
    
    @property
    def problem_directories(self) -> List[Dict[str, Any]]:
        """Returns list of problem directories with their sizes"""
        if not self.has_clean_data:
            return []
        patterns = self.clean_data.get('patterns')
        if patterns is None:
            return []
        return [p for p in patterns if p.get('bytes_saved', 0) > 0]
    
    def format_size(self) -> str:
        """Format bytes to human readable format"""
        if not self.has_scan:
            return "---"
        return format_size(self.size_bytes)