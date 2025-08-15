#!/usr/bin/env python3

"""
Freight Orchestrator - Python tool for managing and monitoring Freight NFS migration suite

This module provides a comprehensive overview of scan status across directories,
displaying progress in a grid-like format with status indicators and statistics.
"""

import argparse
import json
import os
import subprocess
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
    
    def __init__(self, migration_root: Optional[str] = None):
        self.script_dir = Path(__file__).parent.resolve()
        self.global_config_path = self.script_dir / 'config.json'
        
        # If no migration root provided, try to get from global config
        if migration_root is None:
            migration_root = self.get_migration_root_from_config()
            
        if migration_root is None:
            raise ValueError("No migration root specified and no global config found")
            
        self.migration_root = Path(migration_root).resolve()
        self.scan_results: List[ScanResult] = []
    
    def scan_directories(self) -> None:
        """Scan all subdirectories for .freight/scan.json files"""
        if not self.migration_root.exists():
            raise FileNotFoundError(f"Directory not found: {self.migration_root}")
        
        if not self.migration_root.is_dir():
            raise NotADirectoryError(f"Path is not a directory: {self.migration_root}")
        
        # Find all immediate subdirectories, excluding .freight
        subdirs = [d for d in self.migration_root.iterdir() if d.is_dir() and d.name != '.freight']
        
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
    
    def get_migration_root_from_config(self) -> Optional[str]:
        """Get migration root from global config file"""
        if not self.global_config_path.exists():
            return None
        
        try:
            with open(self.global_config_path, 'r') as f:
                config = json.load(f)
            return config.get('root_directory')
        except (json.JSONDecodeError, IOError):
            return None
    
    def ensure_global_config(self, migration_root: str) -> bool:
        """Ensure global config exists and is properly set up. Returns True if config was created."""
        if self.global_config_path.exists():
            return False
        
        config_skeleton = {
            "freight_version": "1.0.0",
            "root_directory": migration_root,
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
                "shared_directory_threshold": 2,
                "exclude_patterns": [
                    ".git",
                    ".svn", 
                    "node_modules",
                    "__pycache__"
                ]
            },
            "cleaning": {
                "target_directories": []
            },
            "metadata": {
                "description": "Freight NFS migration root",
                "contact": "",
                "notes": ""
            }
        }
        
        with open(self.global_config_path, 'w') as f:
            json.dump(config_skeleton, f, indent=2)
        
        return True
    
    def update_config_stats(self, stats: Dict[str, Any]) -> None:
        """Update config.json with calculated statistics"""
        if not self.global_config_path.exists():
            return
        
        try:
            with open(self.global_config_path, 'r') as f:
                config = json.load(f)
            
            config['total_directories'] = stats['total_directories']
            config['total_size_bytes'] = stats['total_size_bytes']
            
            with open(self.global_config_path, 'w') as f:
                json.dump(config, f, indent=2)
        except (json.JSONDecodeError, IOError):
            pass
    
    def display_overview(self) -> None:
        """Display the grid-like overview of scan status"""
        stats = self.get_statistics()
        
        # Update config.json with calculated stats
        self.update_config_stats(stats)
        
        # Header
        print(f"\n{Colors.BOLD}{Colors.CYAN}Freight Scanner Overview{Colors.END}")
        print(f"{Colors.CYAN}{'=' * 60}{Colors.END}")
        print(f"Root: {Colors.WHITE}{self.migration_root}{Colors.END}")
        
        # Statistics summary
        print(f"\n{Colors.BOLD}Summary:{Colors.END}")
        print(f"  Scan status: {Colors.GREEN}{stats['scanned_directories']}{Colors.END}/{Colors.WHITE}{stats['total_directories']}{Colors.END} ({Colors.YELLOW}{stats['completion_rate']:.1f}%{Colors.END})")

        if stats['scanned_directories'] > 0:
            print(f"  Total size: {Colors.WHITE}{self.format_size(stats['total_size_bytes'])}{Colors.END}")
            print(f"  Total files: {Colors.WHITE}{stats['total_files']:,}{Colors.END}")

        # Top three largest directories
        scanned_results = [r for r in self.scan_results if r.has_scan and r.size_bytes > 0]
        if scanned_results:
            scanned_results.sort(key=lambda x: x.size_bytes, reverse=True)
            top_three = scanned_results[:3]
            
            print(f"\n{Colors.BOLD}Largest Directories:{Colors.END}")
            medals = ["🥇", "🥈", "🥉"]
            for i, result in enumerate(top_three):
                medal = medals[i] if i < len(medals) else " "
                print(f"  {medal} {result.name}: {Colors.WHITE}{result.format_size()}{Colors.END}")
        
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
        """Initialize a freight root directory with global config"""
        if root_path is None:
            root_path = os.getcwd()
        
        root_dir = Path(root_path).resolve()
        
        # Check if config.json already exists in the same directory as freight.py
        if self.global_config_path.exists():
            print(f"{Colors.RED}✗{Colors.END} Freight has already been initialized!")
            print(f"Config file exists: {Colors.CYAN}{self.global_config_path}{Colors.END}")
            print(f"\nTo reconfigure your migration:")
            print(f"  • Edit the existing config: {Colors.YELLOW}nano {self.global_config_path}{Colors.END}")
            print(f"  • Or backup and reinitialize:")
            print(f"    {Colors.YELLOW}mv {self.global_config_path} {self.global_config_path}.backup{Colors.END}")
            print(f"    {Colors.YELLOW}freight.py init{Colors.END}")
            sys.exit(1)
        
        # Create .freight-root marker file only
        freight_root_marker = root_dir / '.freight-root'
        freight_root_marker.touch()
        print(f"{Colors.GREEN}✓{Colors.END} Created .freight-root marker: {freight_root_marker}")
        
        # Create/update global config
        config_created = self.ensure_global_config(str(root_dir))
        
        if config_created:
            print(f"{Colors.GREEN}✓{Colors.END} Created global config: {self.global_config_path}")
            print(f"\n{Colors.BOLD}{Colors.YELLOW}Global configuration created!{Colors.END}")
            print(f"Please edit {Colors.CYAN}{self.global_config_path}{Colors.END} to customize your migration settings.")
            print(f"Pay special attention to:")
            print(f"  - cleaning.target_directories (directories to clean from subdirs)")
            print(f"  - settings.exclude_patterns (patterns to exclude from scans)")
        else:
            print(f"{Colors.YELLOW}!{Colors.END} Global config already exists: {self.global_config_path}")
            # Update the root directory in existing config
            try:
                with open(self.global_config_path, 'r') as f:
                    config = json.load(f)
                config['root_directory'] = str(root_dir)
                with open(self.global_config_path, 'w') as f:
                    json.dump(config, f, indent=2)
                print(f"{Colors.GREEN}✓{Colors.END} Updated root directory in global config")
            except (json.JSONDecodeError, IOError) as e:
                print(f"{Colors.RED}✗{Colors.END} Failed to update global config: {e}")
        
        print(f"\n{Colors.BOLD}{Colors.CYAN}Freight root initialized successfully!{Colors.END}")
        print(f"Root directory: {Colors.WHITE}{root_dir}{Colors.END}")
        print(f"\nNext steps:")
        print(f"  1. Edit {Colors.CYAN}{self.global_config_path}{Colors.END} to customize settings")
        print(f"  2. Run {Colors.YELLOW}freight.py scan{Colors.END} to scan directories")
    
    def run_clean(self, dry_run: bool = False) -> None:
        """Run the freight-clean.sh script"""
        if not self.migration_root.exists():
            raise FileNotFoundError(f"Migration root not found: {self.migration_root}")
        
        # Path to the freight-clean.sh script
        clean_script = self.script_dir / 'scripts' / 'freight-clean.sh'
        
        if not clean_script.exists():
            raise FileNotFoundError(f"Clean script not found: {clean_script}")
        
        # Build command arguments
        cmd = [str(clean_script), str(self.migration_root)]
        if dry_run:
            cmd.append('--dry-run')
        
        print(f"\n{Colors.BOLD}{Colors.CYAN}Running Freight Clean{Colors.END}")
        print(f"Root: {Colors.WHITE}{self.migration_root}{Colors.END}")
        if dry_run:
            print(f"Mode: {Colors.YELLOW}DRY RUN{Colors.END}")
        
        try:
            # Run the clean script
            result = subprocess.run(cmd, check=True)
            print(f"\n{Colors.GREEN}Clean completed successfully!{Colors.END}")
        except subprocess.CalledProcessError as e:
            print(f"\n{Colors.RED}Clean failed with exit code {e.returncode}{Colors.END}")
            raise
        except FileNotFoundError:
            print(f"{Colors.RED}Error: freight-clean.sh script not found{Colors.END}")
            raise
    
    def run_scan(self) -> None:
        """Run the freight-scan.sh script"""
        if not self.migration_root.exists():
            raise FileNotFoundError(f"Migration root not found: {self.migration_root}")
        
        # Path to the freight-scan.sh script
        scan_script = self.script_dir / 'scripts' / 'freight-scan.sh'
        
        if not scan_script.exists():
            raise FileNotFoundError(f"Scan script not found: {scan_script}")
        
        # Build command arguments
        cmd = [str(scan_script), str(self.migration_root)]
        
        print(f"\n{Colors.BOLD}{Colors.CYAN}Running Freight Scan{Colors.END}")
        print(f"Root: {Colors.WHITE}{self.migration_root}{Colors.END}")
        
        try:
            # Run the scan script
            result = subprocess.run(cmd, check=True)
            print(f"\n{Colors.GREEN}Scan completed successfully!{Colors.END}")
        except subprocess.CalledProcessError as e:
            print(f"\n{Colors.RED}Scan failed with exit code {e.returncode}{Colors.END}")
            raise
        except FileNotFoundError:
            print(f"{Colors.RED}Error: freight-scan.sh script not found{Colors.END}")
            raise

    def analyze_shared_directories(self) -> Dict[str, int]:
        """Analyze shared directories across all subdirectories"""
        if not self.migration_root.exists():
            raise FileNotFoundError(f"Migration root not found: {self.migration_root}")
        
        directory_counts = {}
        
        # Find all immediate subdirectories, excluding .freight
        subdirs = [d for d in self.migration_root.iterdir() if d.is_dir() and d.name != '.freight']
        
        for subdir in subdirs:
            try:
                # Get immediate child directories only (not recursive)
                child_dirs = [d.name for d in subdir.iterdir() if d.is_dir()]
                
                # Count each directory name
                for dir_name in child_dirs:
                    directory_counts[dir_name] = directory_counts.get(dir_name, 0) + 1
                    
            except (PermissionError, OSError) as e:
                print(f"Warning: Could not access {subdir}: {e}", file=sys.stderr)
                continue
        
        return directory_counts
    
    def get_shared_directory_threshold(self) -> int:
        """Get shared directory threshold from config"""
        if not self.global_config_path.exists():
            return 2  # Default threshold
        
        try:
            with open(self.global_config_path, 'r') as f:
                config = json.load(f)
            return config.get('settings', {}).get('shared_directory_threshold', 2)
        except (json.JSONDecodeError, IOError):
            return 2  # Default threshold
    
    def display_shared_directories(self) -> None:
        """Display shared directories analysis"""
        print(f"\n{Colors.BOLD}{Colors.CYAN}Freight Shared Directory Analysis{Colors.END}")
        print(f"{Colors.CYAN}{'=' * 60}{Colors.END}")
        print(f"Root: {Colors.WHITE}{self.migration_root}{Colors.END}")
        
        directory_counts = self.analyze_shared_directories()
        threshold = self.get_shared_directory_threshold()
        
        if not directory_counts:
            print(f"\n{Colors.YELLOW}No directories found in subdirectories.{Colors.END}")
            return
        
        # Filter directories that meet the threshold
        shared_dirs = {name: count for name, count in directory_counts.items() if count >= threshold}
        
        if not shared_dirs:
            print(f"\n{Colors.YELLOW}No shared directories found with threshold >= {threshold}.{Colors.END}")
            print(f"Total unique directory names: {len(directory_counts)}")
            return
        
        # Sort by count (descending) and then by name
        sorted_shared = sorted(shared_dirs.items(), key=lambda x: (-x[1], x[0]))
        
        print(f"\nThreshold: {Colors.WHITE}{threshold}{Colors.END} or more occurrences")
        print(f"Found {Colors.GREEN}{len(sorted_shared)}{Colors.END} shared directories:")
        print(f"\n{'Directory Name':<30} {'Count':<8} {'Percentage'}")
        print('-' * 50)
        
        total_subdirs = len([d for d in self.migration_root.iterdir() if d.is_dir() and d.name != '.freight'])
        
        for dir_name, count in sorted_shared:
            percentage = (count / total_subdirs * 100) if total_subdirs > 0 else 0
            print(f"{dir_name:<30} {count:<8} {percentage:.1f}%")
        
        print(f"\n{Colors.BOLD}Analysis Summary:{Colors.END}")
        print(f"  Total subdirectories scanned: {Colors.WHITE}{total_subdirs}{Colors.END}")
        print(f"  Unique directory names found: {Colors.WHITE}{len(directory_counts)}{Colors.END}")
        print(f"  Shared directories (>= {threshold}): {Colors.GREEN}{len(sorted_shared)}{Colors.END}")
        
        # Show top candidates for exclusion
        high_frequency = [item for item in sorted_shared if item[1] >= max(3, threshold + 1)]
        if high_frequency:
            print(f"\n{Colors.BOLD}High-frequency directories (potential cleanup candidates):{Colors.END}")
            for dir_name, count in high_frequency[:10]:  # Show top 10
                print(f"  • {Colors.YELLOW}{dir_name}{Colors.END} ({count} occurrences)")
        
        print(f"\n{Colors.CYAN}{'=' * 60}{Colors.END}")

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Freight Orchestrator - Manage and monitor Freight NFS migration suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  freight.py init                    # Initialize current directory as freight root
  freight.py init /path/to/root      # Initialize specific directory as freight root
  freight.py scan                    # Run freight-scan.sh using global config
  freight.py scan /nfs1/students     # Run freight-scan.sh on specific migration root
  freight.py overview                # Show scan overview for current directory
  freight.py overview /nfs1/students # Show scan overview for migration root
  freight.py clean --dry-run         # Show what would be cleaned (dry run)
  freight.py clean                   # Clean directories using global config
  freight.py clean /nfs1/students    # Clean specific migration root
  freight.py shared                  # Analyze shared directories using global config
  freight.py shared /nfs1/students   # Analyze shared directories for specific root
  freight.py shared --threshold 3    # Show directories appearing 3+ times
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Init command
    init_parser = subparsers.add_parser('init', help='Initialize a freight root directory')
    init_parser.add_argument('directory', nargs='?', default=None,
                           help='Directory to initialize (default: current directory)')
    
    # Scan command (runs freight-scan.sh)
    scan_parser = subparsers.add_parser('scan', help='Run freight-scan.sh to scan directories')
    scan_parser.add_argument('migration_root', nargs='?', default=None,
                           help='Migration root directory to scan (default: from global config)')
    
    # Overview command (shows results)
    overview_parser = subparsers.add_parser('overview', help='Show scan overview of migration root')
    overview_parser.add_argument('migration_root', nargs='?', default=None,
                               help='Migration root directory to analyze (default: from global config)')
    
    # Clean command
    clean_parser = subparsers.add_parser('clean', help='Clean directories using freight-clean.sh')
    clean_parser.add_argument('migration_root', nargs='?', default=None,
                            help='Migration root directory to clean (default: from global config)')
    clean_parser.add_argument('--dry-run', action='store_true',
                            help='Show what would be cleaned without deleting files')
    
    # Shared command
    shared_parser = subparsers.add_parser('shared', help='Analyze shared directories across subdirectories')
    shared_parser.add_argument('migration_root', nargs='?', default=None,
                             help='Migration root directory to analyze (default: from global config)')
    shared_parser.add_argument('--threshold', type=int, default=None,
                             help='Minimum occurrences to show (overrides config setting)')
    
    # Parse arguments
    args = parser.parse_args()
    
    if not args.command:
        # Default to overview command when no arguments provided
        args.command = 'overview'
        args.migration_root = None
    
    try:
        if args.command == 'init':
            # Initialize freight root
            orchestrator = FreightOrchestrator(args.directory or os.getcwd())
            orchestrator.init_freight_root(args.directory)
            
        elif args.command == 'scan':
            # Run scan operation
            try:
                orchestrator = FreightOrchestrator(args.migration_root)
            except ValueError as e:
                if "No migration root specified" in str(e):
                    print(f"{Colors.RED}Error:{Colors.END} No migration root found in global config.")
                    print(f"Please run {Colors.YELLOW}freight.py init{Colors.END} first or specify a migration root explicitly.")
                    sys.exit(1)
                raise
            
            # Ensure global config exists
            config_created = orchestrator.ensure_global_config(str(orchestrator.migration_root))
            if config_created:
                print(f"{Colors.YELLOW}Global configuration created at {orchestrator.global_config_path}{Colors.END}")
                print(f"Please edit the config file to customize scanning settings before running scan operations.\n")
            
            orchestrator.run_scan()
            
        elif args.command == 'overview':
            # Show scan overview
            try:
                orchestrator = FreightOrchestrator(args.migration_root)
            except ValueError as e:
                if "No migration root specified" in str(e):
                    print(f"{Colors.RED}Error:{Colors.END} No migration root found in global config.")
                    print(f"Please run {Colors.YELLOW}freight.py init{Colors.END} first or specify a migration root explicitly.")
                    sys.exit(1)
                raise
            
            # Ensure global config exists and alert if created
            config_created = orchestrator.ensure_global_config(str(orchestrator.migration_root))
            if config_created:
                print(f"{Colors.YELLOW}Global configuration created at {orchestrator.global_config_path}{Colors.END}")
                print(f"Please edit the config file to customize settings before running overview operations.\n")
            
            orchestrator.scan_directories()
            orchestrator.display_overview()
            
        elif args.command == 'clean':
            # Run clean operation
            try:
                orchestrator = FreightOrchestrator(args.migration_root)
            except ValueError as e:
                if "No migration root specified" in str(e):
                    print(f"{Colors.RED}Error:{Colors.END} No migration root found in global config.")
                    print(f"Please run {Colors.YELLOW}freight.py init{Colors.END} first or specify a migration root explicitly.")
                    sys.exit(1)
                raise
            
            # Ensure global config exists
            config_created = orchestrator.ensure_global_config(str(orchestrator.migration_root))
            if config_created:
                print(f"{Colors.YELLOW}Global configuration created at {orchestrator.global_config_path}{Colors.END}")
                print(f"Please edit the config file to customize cleaning settings before running clean operations.\n")
            
            orchestrator.run_clean(dry_run=args.dry_run)
            
        elif args.command == 'shared':
            # Show shared directories analysis
            try:
                orchestrator = FreightOrchestrator(args.migration_root)
            except ValueError as e:
                if "No migration root specified" in str(e):
                    print(f"{Colors.RED}Error:{Colors.END} No migration root found in global config.")
                    print(f"Please run {Colors.YELLOW}freight.py init{Colors.END} first or specify a migration root explicitly.")
                    sys.exit(1)
                raise
            
            # Ensure global config exists
            config_created = orchestrator.ensure_global_config(str(orchestrator.migration_root))
            if config_created:
                print(f"{Colors.YELLOW}Global configuration created at {orchestrator.global_config_path}{Colors.END}")
                print(f"Please edit the config file to customize shared directory analysis settings.\n")
            
            # Override threshold if provided
            if args.threshold is not None:
                # Temporarily modify the threshold for this run
                original_get_threshold = orchestrator.get_shared_directory_threshold
                orchestrator.get_shared_directory_threshold = lambda: args.threshold
            
            orchestrator.display_shared_directories()
            
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