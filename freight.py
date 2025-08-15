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

# Freight version - used for config version comparison
FREIGHT_VERSION = "1.3"

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
    
    @property
    def bytes_cleaned(self) -> int:
        """Returns bytes that would be cleaned"""
        return self.clean_data.get('bytes_cleaned', 0)
    
    @property
    def has_clean_data(self) -> bool:
        """Returns whether clean data is available"""
        return bool(self.clean_data)
    
    @property
    def problem_directories(self) -> List[Dict[str, Any]]:
        """Returns list of problem directories with their sizes"""
        patterns = self.clean_data.get('patterns', [])
        return [p for p in patterns if p.get('bytes_saved', 0) > 0]
    
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
        
        # Check version compatibility
        self.check_config_version()
    
    def scan_directories(self) -> None:
        """Scan all subdirectories for .freight/scan.json and clean.json files"""
        if not self.migration_root.exists():
            raise FileNotFoundError(f"Directory not found: {self.migration_root}")
        
        if not self.migration_root.is_dir():
            raise NotADirectoryError(f"Path is not a directory: {self.migration_root}")
        
        # Find all immediate subdirectories, excluding .freight
        subdirs = [d for d in self.migration_root.iterdir() if d.is_dir() and d.name != '.freight']
        
        for subdir in sorted(subdirs):
            scan_file = subdir / '.freight' / 'scan.json'
            clean_file = subdir / '.freight' / 'clean.json'
            
            # Load scan data
            scan_data = None
            has_scan = False
            if scan_file.exists():
                try:
                    with open(scan_file, 'r') as f:
                        scan_data = json.load(f)
                    has_scan = True
                except (json.JSONDecodeError, IOError) as e:
                    print(f"Warning: Could not parse {scan_file}: {e}", file=sys.stderr)
            
            # Load clean data
            clean_data = None
            if clean_file.exists():
                try:
                    with open(clean_file, 'r') as f:
                        clean_data = json.load(f)
                except (json.JSONDecodeError, IOError) as e:
                    print(f"Warning: Could not parse {clean_file}: {e}", file=sys.stderr)
            
            result = ScanResult(str(subdir), has_scan, scan_data, clean_data)
            self.scan_results.append(result)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Calculate overall statistics"""
        total_dirs = len(self.scan_results)
        scanned_dirs = sum(1 for r in self.scan_results if r.has_scan)
        total_size = sum(r.size_bytes for r in self.scan_results if r.has_scan)
        total_files = sum(r.file_count for r in self.scan_results if r.has_scan)
        total_cleanable = sum(r.bytes_cleaned for r in self.scan_results if r.has_clean_data)
        
        completion_rate = (scanned_dirs / total_dirs * 100) if total_dirs > 0 else 0
        
        return {
            'total_directories': total_dirs,
            'scanned_directories': scanned_dirs,
            'unscanned_directories': total_dirs - scanned_dirs,
            'completion_rate': completion_rate,
            'total_size_bytes': total_size,
            'total_files': total_files,
            'total_cleanable_bytes': total_cleanable
        }
    
    def format_size(self, size_bytes: int) -> str:
        """Format bytes to human readable format"""
        size = float(size_bytes)
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.1f}{unit}"
            size /= 1024.0
        return f"{size:.1f}PB"
    
    def check_config_version(self) -> None:
        """Check config version compatibility and warn if mismatch"""
        if not self.global_config_path.exists():
            return
        
        try:
            with open(self.global_config_path, 'r') as f:
                config = json.load(f)
            
            config_version = config.get('config_version', config.get('freight_version', 'unknown'))
            
            if config_version != FREIGHT_VERSION:
                print(f"{Colors.YELLOW}⚠️  Version mismatch detected:{Colors.END}")
                print(f"   Script version: {Colors.GREEN}{FREIGHT_VERSION}{Colors.END}")
                print(f"   Config version: {Colors.RED}{config_version}{Colors.END}")
                print(f"   Please update your config or use a compatible script version.\n")
        except (json.JSONDecodeError, IOError):
            print(f"{Colors.YELLOW}⚠️  Could not read config version{Colors.END}\n")
    
    def get_migration_root_from_config(self) -> Optional[str]:
        """Get migration root from global config file"""
        if not self.global_config_path.exists():
            return None
        
        try:
            with open(self.global_config_path, 'r') as f:
                config = json.load(f)
            return config.get('migration_root')
        except (json.JSONDecodeError, IOError):
            return None
    
    def ensure_global_config(self, migration_root: str) -> bool:
        """Ensure global config exists and is properly set up. Returns True if config was created."""
        if self.global_config_path.exists():
            return False
        
        config_skeleton = {
            "config_version": FREIGHT_VERSION,
            "migration_root": migration_root,
            "created_time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "global": {
                "parallel_jobs": 4
            },
            "scan": {
                "last_scan_time": None,
                "total_directories": 0,
                "total_size_bytes": 0
            },
            "clean": {
                "last_clean_time": None,
                "target_directories": [],
                "shared_directory_threshold": 2,
                "shared_directory_ignore": [
                    ".freight",
                    ".ssh"
                ]
            },
            "migrate": {
                "last_migrate_time": None
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
            
            config['scan']['total_directories'] = stats['total_directories']
            config['scan']['total_size_bytes'] = stats['total_size_bytes']
            
            with open(self.global_config_path, 'w') as f:
                json.dump(config, f, indent=2)
        except (json.JSONDecodeError, IOError):
            pass
    
    def display_overview(self) -> None:
        """Display the overview of scan status with grid layout for directories"""
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
            
        # Add cleaning savings if any directories have clean data
        if stats['total_cleanable_bytes'] > 0:
            print(f"  Potential space savings: {Colors.YELLOW}{self.format_size(stats['total_cleanable_bytes'])}{Colors.END}")

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
        
        # Directory status in grid layout
        print(f"\n{Colors.BOLD}Directory Status:{Colors.END}")
        print(f"{Colors.CYAN}{'=' * 60}{Colors.END}")
        
        self._display_directory_grid()
        
        print(f"{Colors.CYAN}{'=' * 60}{Colors.END}")
    
    def _display_directory_grid(self) -> None:
        """Display directories in a grid layout"""
        import os
        
        # Get terminal width, default to 80 if not available
        try:
            terminal_width = os.get_terminal_size().columns
        except (OSError, AttributeError):
            terminal_width = 80
        
        # Calculate grid parameters
        min_block_width = 35  # Minimum width for a directory block
        max_blocks_per_row = max(1, terminal_width // min_block_width)
        
        # Group results into rows
        for i in range(0, len(self.scan_results), max_blocks_per_row):
            row_results = self.scan_results[i:i + max_blocks_per_row]
            
            # Display this row
            self._display_directory_row(row_results, terminal_width)
    
    def _display_directory_row(self, results: List[ScanResult], terminal_width: int) -> None:
        """Display a row of directory blocks side by side"""
        if not results:
            return
        
        block_width = (terminal_width - len(results)) // len(results)  # Account for separators
        block_width = max(30, block_width)  # Minimum block width
        
        # Create formatted blocks for each directory
        blocks = []
        for result in results:
            block_lines = self._format_directory_block(result, block_width)
            blocks.append(block_lines)
        
        # Find max height
        max_height = max(len(block) for block in blocks)
        
        # Pad blocks to same height
        for block in blocks:
            while len(block) < max_height:
                block.append(" " * block_width)
        
        # Print blocks side by side
        for line_idx in range(max_height):
            line_parts = []
            for block in blocks:
                line_parts.append(block[line_idx])
            print(" ".join(line_parts))
        
        # Add separator line
        print()
    
    def _format_directory_block(self, result: ScanResult, width: int) -> List[str]:
        """Format a single directory as a block with fixed width"""
        lines = []
        
        # Directory name with status icon (truncate if too long)
        name_line = f"{result.name} {result.status_icon}"
        if len(result.name) > width - 3:  # Account for status icon
            name_line = f"{result.name[:width-6]}... {result.status_icon}"
        lines.append(name_line.ljust(width))
        
        if result.has_scan:
            # Basic scan stats
            lines.append(f"Size: {result.format_size()}".ljust(width))
            lines.append(f"Files: {result.file_count:,}".ljust(width))
            
            if result.scan_time:
                scan_date = result.scan_time[:10]  # Just date part
                lines.append(f"Scanned: {scan_date}".ljust(width))
            
            # Problem directories if available
            if result.has_clean_data:
                problem_dirs = result.problem_directories
                if problem_dirs:
                    total_savings = sum(p.get('bytes_saved', 0) for p in problem_dirs)
                    lines.append(f"Savings: {self.format_size(total_savings)}".ljust(width))
                    
                    # Show up to 2 problem directories
                    for i, prob_dir in enumerate(problem_dirs[:2]):
                        pattern = prob_dir.get('pattern', 'unknown')
                        size = self.format_size(prob_dir.get('bytes_saved', 0))
                        if len(pattern) > width - 8:  # Account for size display
                            pattern = pattern[:width-11] + "..."
                        lines.append(f"• {pattern} ({size})".ljust(width))
                    
                    if len(problem_dirs) > 2:
                        lines.append(f"+ {len(problem_dirs) - 2} more...".ljust(width))
        else:
            lines.append(f"{Colors.RED}Not scanned{Colors.END}".ljust(width))
        
        return lines
    
    def _display_directory_block(self, result: ScanResult) -> None:
        """Display a single directory as a block with stats (legacy method)"""
        # Directory name with status icon
        print(f"\n{Colors.BOLD}{result.name}{Colors.END} {result.status_icon}")
        
        if result.has_scan:
            # Basic scan stats
            print(f"  Size: {Colors.WHITE}{result.format_size()}{Colors.END}")
            print(f"  Files: {Colors.WHITE}{result.file_count:,}{Colors.END}")
            if result.scan_time:
                scan_date = result.scan_time[:10]  # Just date part
                print(f"  Scanned: {Colors.CYAN}{scan_date}{Colors.END}")
            if result.directory_mtime:
                print(f"  Modified: {Colors.CYAN}{result.directory_mtime}{Colors.END}")
            
            # Problem directories and potential savings
            if result.has_clean_data:
                problem_dirs = result.problem_directories
                if problem_dirs:
                    total_savings = sum(p.get('bytes_saved', 0) for p in problem_dirs)
                    print(f"  Potential savings: {Colors.YELLOW}{self.format_size(total_savings)}{Colors.END}")
                    
                    # Show problem directories
                    for prob_dir in problem_dirs[:3]:  # Show up to 3
                        pattern = prob_dir.get('pattern', 'unknown')
                        size = self.format_size(prob_dir.get('bytes_saved', 0))
                        print(f"    • {Colors.RED}{pattern}{Colors.END}: {Colors.YELLOW}{size}{Colors.END}")
                    
                    if len(problem_dirs) > 3:
                        print(f"    • {Colors.CYAN}+{len(problem_dirs) - 3} more problem directories{Colors.END}")
        else:
            print(f"  {Colors.RED}Not scanned{Colors.END}")
        
        print()
    
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
            print(f"  - clean.target_directories (directories to clean from subdirs)")
            print(f"  - clean.shared_directory_threshold (minimum occurrences for shared dirs)")
        else:
            print(f"{Colors.YELLOW}!{Colors.END} Global config already exists: {self.global_config_path}")
            # Update the root directory in existing config
            try:
                with open(self.global_config_path, 'r') as f:
                    config = json.load(f)
                config['migration_root'] = str(root_dir)
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
    
    def run_script(self, script_name: str, extra_args: Optional[List[str]] = None) -> None:
        """Run a freight script with passthrough arguments"""
        # Path to the script
        script_path = self.script_dir / 'scripts' / f'freight-{script_name}.sh'
        
        if not script_path.exists():
            raise FileNotFoundError(f"Script not found: {script_path}")
        
        # Build command arguments - just pass everything through
        cmd = [str(script_path)]
        if self.migration_root:
            cmd.append(str(self.migration_root))
        if extra_args:
            cmd.extend(extra_args)
        
        print(f"\n{Colors.BOLD}{Colors.CYAN}Running Freight {script_name.title()}{Colors.END}")
        
        try:
            # Run the script
            result = subprocess.run(cmd, check=True)
            print(f"\n{Colors.GREEN}{script_name.title()} completed successfully!{Colors.END}")
        except subprocess.CalledProcessError as e:
            print(f"\n{Colors.RED}{script_name.title()} failed with exit code {e.returncode}{Colors.END}")
            raise
        except FileNotFoundError:
            print(f"{Colors.RED}Error: freight-{script_name}.sh script not found{Colors.END}")
            raise
    
    def run_scan(self, extra_args: Optional[List[str]] = None) -> None:
        """Run the freight-scan.sh script"""
        self.run_script('scan', extra_args=extra_args)

    def analyze_shared_directories(self) -> Dict[str, int]:
        """Analyze shared directories across all subdirectories"""
        if not self.migration_root.exists():
            raise FileNotFoundError(f"Migration root not found: {self.migration_root}")
        
        directory_counts = {}
        ignore_list = self.get_shared_directory_ignore_list()
        
        # Find all immediate subdirectories, excluding .freight
        subdirs = [d for d in self.migration_root.iterdir() if d.is_dir() and d.name != '.freight']
        
        for subdir in subdirs:
            try:
                # Get immediate child directories only (not recursive)
                child_dirs = [d.name for d in subdir.iterdir() if d.is_dir()]
                
                # Count each directory name, excluding ignored directories
                for dir_name in child_dirs:
                    if dir_name not in ignore_list:
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
            return config.get('clean', {}).get('shared_directory_threshold', 2)
        except (json.JSONDecodeError, IOError):
            return 2  # Default threshold
    
    def get_shared_directory_ignore_list(self) -> List[str]:
        """Get shared directory ignore list from config"""
        default_ignore = [".freight", ".ssh"]
        
        if not self.global_config_path.exists():
            return default_ignore
        
        try:
            with open(self.global_config_path, 'r') as f:
                config = json.load(f)
            return config.get('clean', {}).get('shared_directory_ignore', default_ignore)
        except (json.JSONDecodeError, IOError):
            return default_ignore
    
    def display_shared_directories(self) -> None:
        """Display shared directories analysis"""
        print(f"\n{Colors.BOLD}{Colors.CYAN}Freight Shared Directory Analysis{Colors.END}")
        print(f"{Colors.CYAN}{'=' * 60}{Colors.END}")
        print(f"Root: {Colors.WHITE}{self.migration_root}{Colors.END}")
        
        ignore_list = self.get_shared_directory_ignore_list()
        if ignore_list:
            print(f"Ignoring: {Colors.YELLOW}{', '.join(ignore_list)}{Colors.END}")
        
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
  freight.py clean                   # Run clean in dry-run mode (default)
  freight.py clean --confirm         # Run clean with confirmation (actual cleaning)
  freight.py clean /path/to/root --confirm  # Clean specific root with confirmation
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
    scan_parser.add_argument('script_args', nargs='*',
                           help='Arguments to pass to freight-scan.sh')
    
    # Overview command (shows results)
    overview_parser = subparsers.add_parser('overview', help='Show scan overview of migration root')
    overview_parser.add_argument('migration_root', nargs='?', default=None,
                               help='Migration root directory to analyze (default: from global config)')
    
    # Clean command - pass all unknown arguments to script
    clean_parser = subparsers.add_parser('clean', help='Clean directories using freight-clean.sh')
    clean_parser.add_argument('migration_root', nargs='?', default=None,
                            help='Migration root directory to clean (default: from global config)')
    clean_parser.add_argument('script_args', nargs='*',
                            help='Arguments to pass to freight-clean.sh (e.g. --confirm)')
    
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
            
            orchestrator.run_scan(extra_args=args.script_args)
            
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
            
            orchestrator.run_script('clean', extra_args=args.script_args)
            
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