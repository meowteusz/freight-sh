#!/usr/bin/env python3

"""
Freight Orchestrator - Python tool for managing and monitoring Freight NFS migration suite

This module provides a comprehensive overview of scan status across directories,
displaying progress in a grid-like format with status indicators and statistics.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

class Colors:
    """ANSI color codes for terminal output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    END = '\033[0m'

class ScanResult:
    """Represents the scan result for a single directory"""
    
    def __init__(self, directory: str, has_scan: bool = False, scan_data: Optional[Dict] = None):
        self.directory = directory
        self.name = os.path.basename(directory)
        self.has_scan = has_scan
        self.scan_data = scan_data or {}
    
    @property
    def status_icon(self) -> str:
        """Returns colored status icon"""
        if self.has_scan:
            return f"{Colors.GREEN}✓{Colors.END}"
        return f"{Colors.RED}✗{Colors.END}"
    
    @property
    def size_bytes(self) -> int:
        """Returns size in bytes"""
        return self.scan_data.get('size_bytes', 0)
    
    @property
    def file_count(self) -> int:
        """Returns number of files"""
        return self.scan_data.get('file_count', 0)
    
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
    
    def format_size(self) -> str:
        """Format bytes to human readable format"""
        if not self.has_scan:
            return "---"
        
        size = self.size_bytes
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.1f}{unit}"
            size /= 1024.0
        return f"{size:.1f}PB"

class FreightOrchestrator:
    """Main orchestrator class for managing Freight operations"""
    
    def __init__(self, migration_root: str):
        self.migration_root = Path(migration_root).resolve()
        self.scan_results: List[ScanResult] = []
    
    def scan_directories(self) -> None:
        """Scan all subdirectories for .freight/scan.json files"""
        if not self.migration_root.exists():
            raise FileNotFoundError(f"Directory not found: {self.migration_root}")
        
        if not self.migration_root.is_dir():
            raise NotADirectoryError(f"Path is not a directory: {self.migration_root}")
        
        # Find all immediate subdirectories
        subdirs = [d for d in self.migration_root.iterdir() if d.is_dir()]
        
        for subdir in sorted(subdirs):
            scan_file = subdir / '.freight' / 'scan.json'
            
            if scan_file.exists():
                try:
                    with open(scan_file, 'r') as f:
                        scan_data = json.load(f)
                    result = ScanResult(str(subdir), True, scan_data)
                except (json.JSONDecodeError, IOError) as e:
                    print(f"Warning: Could not parse {scan_file}: {e}", file=sys.stderr)
                    result = ScanResult(str(subdir), False)
            else:
                result = ScanResult(str(subdir), False)
            
            self.scan_results.append(result)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Calculate overall statistics"""
        total_dirs = len(self.scan_results)
        scanned_dirs = sum(1 for r in self.scan_results if r.has_scan)
        total_size = sum(r.size_bytes for r in self.scan_results if r.has_scan)
        total_files = sum(r.file_count for r in self.scan_results if r.has_scan)
        
        completion_rate = (scanned_dirs / total_dirs * 100) if total_dirs > 0 else 0
        
        return {
            'total_directories': total_dirs,
            'scanned_directories': scanned_dirs,
            'unscanned_directories': total_dirs - scanned_dirs,
            'completion_rate': completion_rate,
            'total_size_bytes': total_size,
            'total_files': total_files
        }
    
    def format_size(self, size_bytes: int) -> str:
        """Format bytes to human readable format"""
        size = float(size_bytes)
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.1f}{unit}"
            size /= 1024.0
        return f"{size:.1f}PB"
    
    def display_overview(self) -> None:
        """Display the grid-like overview of scan status"""
        stats = self.get_statistics()
        
        # Header
        print(f"\n{Colors.BOLD}{Colors.CYAN}Freight Scanner Overview{Colors.END}")
        print(f"{Colors.CYAN}{'=' * 60}{Colors.END}")
        print(f"Root: {Colors.WHITE}{self.migration_root}{Colors.END}")
        
        # Statistics summary
        print(f"\n{Colors.BOLD}Summary:{Colors.END}")
        print(f"  Total directories: {Colors.WHITE}{stats['total_directories']}{Colors.END}")
        print(f"  Scanned: {Colors.GREEN}{stats['scanned_directories']}{Colors.END}")
        print(f"  Unscanned: {Colors.RED}{stats['unscanned_directories']}{Colors.END}")
        print(f"  Completion: {Colors.YELLOW}{stats['completion_rate']:.1f}%{Colors.END}")
        
        if stats['scanned_directories'] > 0:
            print(f"  Total size: {Colors.WHITE}{self.format_size(stats['total_size_bytes'])}{Colors.END}")
            print(f"  Total files: {Colors.WHITE}{stats['total_files']:,}{Colors.END}")
        
        # Grid header
        print(f"\n{Colors.BOLD}Directory Status:{Colors.END}")
        print(f"{'Directory':<25} {'Status':<8} {'Size':<10} {'Files':<10} {'Scan Time':<12} {'Dir MTime'}")
        print('-' * 85)
        
        # Grid rows
        for result in self.scan_results:
            status = result.status_icon
            size = result.format_size()
            files = f"{result.file_count:,}" if result.has_scan else "---"
            scan_time = result.scan_time[:10] if result.scan_time else "---"  # Just date part
            dir_mtime = result.directory_mtime if result.directory_mtime else "---"
            
            print(f"{result.name:<25} {status:<8} {size:<10} {files:<10} {scan_time:<12} {dir_mtime}")
        
        print(f"\n{Colors.CYAN}{'=' * 85}{Colors.END}")
    
    def init_freight_root(self, root_path: Optional[str] = None) -> None:
        """Initialize a freight root directory with .freight structure"""
        if root_path is None:
            root_path = os.getcwd()
        
        root_dir = Path(root_path).resolve()
        freight_dir = root_dir / '.freight'
        
        # Create .freight directory
        freight_dir.mkdir(exist_ok=True)
        print(f"{Colors.GREEN}✓{Colors.END} Created .freight directory: {freight_dir}")
        
        # Create .freight-root marker file
        freight_root_marker = root_dir / '.freight-root'
        freight_root_marker.touch()
        print(f"{Colors.GREEN}✓{Colors.END} Created .freight-root marker: {freight_root_marker}")
        
        # Create config.json skeleton
        config_file = freight_dir / 'config.json'
        
        config_skeleton = {
            "freight_version": "1.0.0",
            "root_directory": str(root_dir),
            "created_time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "scan_completed": False,
            "clean_completed": False,
            "migrate_completed": False,
            "last_scan_time": None,
            "last_clean_time": None,
            "last_migrate_time": None,
            "total_directories": 0,
            "total_size_bytes": 0,
            "settings": {
                "dry_run": True,
                "verbose": False,
                "parallel_jobs": 4,
                "exclude_patterns": [
                    ".git",
                    ".svn",
                    "node_modules",
                    "__pycache__"
                ]
            },
            "metadata": {
                "description": "Freight NFS migration root",
                "contact": "",
                "notes": ""
            }
        }
        
        with open(config_file, 'w') as f:
            json.dump(config_skeleton, f, indent=2)
        
        print(f"{Colors.GREEN}✓{Colors.END} Created config.json: {config_file}")
        print(f"\n{Colors.BOLD}{Colors.CYAN}Freight root initialized successfully!{Colors.END}")
        print(f"Root directory: {Colors.WHITE}{root_dir}{Colors.END}")
        print(f"\nNext steps:")
        print(f"  1. Edit {Colors.CYAN}.freight/config.json{Colors.END} to customize settings")
        print(f"  2. Run {Colors.YELLOW}freight-orchestrator.py scan{Colors.END} to scan directories")

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Freight Orchestrator - Manage and monitor Freight NFS migration suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  freight-orchestrator.py init                    # Initialize current directory as freight root
  freight-orchestrator.py init /path/to/root      # Initialize specific directory as freight root
  freight-orchestrator.py scan /nfs1/students     # Show scan overview for migration root
  freight-orchestrator.py overview /nfs1/students # Show scan overview for migration root
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Init command
    init_parser = subparsers.add_parser('init', help='Initialize a freight root directory')
    init_parser.add_argument('directory', nargs='?', default=None,
                           help='Directory to initialize (default: current directory)')
    
    # Scan/Overview command
    scan_parser = subparsers.add_parser('scan', help='Show scan overview of migration root')
    scan_parser.add_argument('migration_root', help='Migration root directory to analyze')
    
    overview_parser = subparsers.add_parser('overview', help='Show scan overview of migration root')
    overview_parser.add_argument('migration_root', help='Migration root directory to analyze')
    
    # Parse arguments
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    try:
        if args.command == 'init':
            # Initialize freight root
            orchestrator = FreightOrchestrator(args.directory or os.getcwd())
            orchestrator.init_freight_root(args.directory)
            
        elif args.command in ['scan', 'overview']:
            # Show scan overview
            orchestrator = FreightOrchestrator(args.migration_root)
            orchestrator.scan_directories()
            orchestrator.display_overview()
            
    except (FileNotFoundError, NotADirectoryError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Interrupted by user{Colors.END}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()