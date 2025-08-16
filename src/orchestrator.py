"""
Core orchestrator for Freight NFS Migration Suite
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from .utils import Colors
from .scan_result import ScanResult
from .config import ConfigManager
from .display import DisplayManager

class FreightOrchestrator:
    """Main orchestrator class for managing Freight operations"""
    
    def __init__(self, migration_root: Optional[str] = None):
        self.script_dir = Path(__file__).parent.parent.resolve()
        self.config_manager = ConfigManager(self.script_dir)
        
        # If no migration root provided, try to get from global config
        if migration_root is None:
            migration_root = self.config_manager.get_migration_root_from_config()
            
        if migration_root is None:
            raise ValueError("No migration root specified and no global config found")
            
        self.migration_root = Path(migration_root).resolve()
        self.scan_results: List[ScanResult] = []
        
        # Check version compatibility
        self.config_manager.check_config_version()
    
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
    
    def check_dependencies(self, deps: List[str]) -> None:
        """Check for required system dependencies"""
        missing_deps = []
        
        for dep in deps:
            try:
                result = subprocess.run(['which', dep], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
                if not result.stdout.strip():
                    missing_deps.append(dep)
            except (subprocess.CalledProcessError, FileNotFoundError):
                missing_deps.append(dep)
        
        if missing_deps:
            print(f"{Colors.RED}Error: Missing required dependencies:{Colors.END}")
            for dep in missing_deps:
                print(f"  • {dep}")
            print(f"\nPlease install the missing dependencies and try again.")
            sys.exit(1)
    
    def get_overview_data(self) -> Dict[str, Any]:
        """Get overview data as JSON-serializable dict"""
        stats = self.get_statistics()
        
        # Update config.json with calculated stats
        self.config_manager.update_config_stats(stats)
        
        # Convert scan results to serializable format
        directories = []
        for result in self.scan_results:
            dir_data = {
                'name': result.name,
                'directory': result.directory,
                'has_scan': result.has_scan,
                'size_bytes': result.size_bytes,
                'file_count': result.file_count,
                'has_clean_data': result.has_clean_data,
                'bytes_cleaned': result.bytes_cleaned,
                'scan_time': result.scan_time
            }
            directories.append(dir_data)
        
        return {
            'stats': stats,
            'directories': directories,
            'migration_root': str(self.migration_root)
        }

    def display_overview(self) -> None:
        """Display the overview of scan status with grid layout for directories"""
        stats = self.get_statistics()
        
        # Update config.json with calculated stats
        self.config_manager.update_config_stats(stats)
        
        # Use DisplayManager to show overview
        display_manager = DisplayManager(self.migration_root, self.scan_results)
        display_manager.display_overview(stats)
    
    def init_freight_root(self, root_path: Optional[str] = None) -> None:
        """Initialize a freight root directory with global config"""
        self.config_manager.init_freight_root(root_path)
    
    def run_script(self, script_name: str, extra_args: Optional[List[str]] = None) -> None:
        """Run a freight script with passthrough arguments"""
        # Check dependencies for the specific script
        if script_name == 'clean':
            self.check_dependencies(['jq', 'du', 'find', 'realpath'])
        elif script_name == 'scan':
            self.check_dependencies(['jq', 'du', 'stat', 'find', 'realpath'])
        
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
    
    def run_orchestrated_scan(self) -> None:
        """Run orchestrated scan of all subdirectories with mtime optimization"""
        # Check dependencies needed for scanning
        self.check_dependencies(['jq', 'du', 'stat', 'find', 'realpath'])
        
        if not self.migration_root.exists():
            raise FileNotFoundError(f"Migration root not found: {self.migration_root}")
        
        if not self.migration_root.is_dir():
            raise NotADirectoryError(f"Path is not a directory: {self.migration_root}")
        
        # Find all immediate subdirectories, excluding .freight
        subdirs = [d for d in self.migration_root.iterdir() if d.is_dir() and d.name != '.freight']
        
        if not subdirs:
            print(f"{Colors.YELLOW}No subdirectories found in migration root: {self.migration_root}{Colors.END}")
            return
        
        subdirs.sort()  # Consistent ordering
        total_dirs = len(subdirs)
        successful_scans = 0
        skipped_scans = 0
        failed_scans = 0
        failed_dirs = []
        
        print(f"\n{Colors.BOLD}{Colors.CYAN}Freight Orchestrated Scan{Colors.END}")
        print(f"{Colors.CYAN}{'=' * 60}{Colors.END}")
        print(f"Root: {Colors.WHITE}{self.migration_root}{Colors.END}")
        print(f"Found {Colors.WHITE}{total_dirs}{Colors.END} subdirectories to scan\n")
        
        # Path to freight-scan.sh script
        scan_script = self.script_dir / 'scripts' / 'freight-scan.sh'
        if not scan_script.exists():
            raise FileNotFoundError(f"freight-scan.sh not found: {scan_script}")
        
        for i, subdir in enumerate(subdirs, 1):
            dir_name = subdir.name
            
            # Check if we should skip based on mtime optimization
            should_skip, reason = self._should_skip_scan(subdir)
            
            if should_skip:
                print(f"[{i:3d}/{total_dirs}] Scanning {dir_name}... {Colors.YELLOW}(skipped - {reason}){Colors.END}")
                skipped_scans += 1
                continue
            
            print(f"[{i:3d}/{total_dirs}] Scanning {dir_name}... ", end="", flush=True)
            
            try:
                # Run freight-scan.sh on this subdirectory, suppressing output
                result = subprocess.run(
                    [str(scan_script), str(subdir)], 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE, 
                    universal_newlines=True, 
                    check=True
                )
                print(f"{Colors.GREEN}✓{Colors.END}")
                successful_scans += 1
                
            except subprocess.CalledProcessError as e:
                print(f"{Colors.RED}✗{Colors.END}")
                failed_scans += 1
                failed_dirs.append((dir_name, e.stderr.strip() if e.stderr else "Unknown error"))
                
            except Exception as e:
                print(f"{Colors.RED}✗{Colors.END}")
                failed_scans += 1
                failed_dirs.append((dir_name, str(e)))
        
        # Summary
        print(f"\n{Colors.BOLD}Scan Summary:{Colors.END}")
        print(f"  Successful: {Colors.GREEN}{successful_scans}{Colors.END}")
        print(f"  Skipped: {Colors.YELLOW}{skipped_scans}{Colors.END}")
        print(f"  Failed: {Colors.RED}{failed_scans}{Colors.END}")
        print(f"  Total: {Colors.WHITE}{total_dirs}{Colors.END}")
        
        # Report failed directories
        if failed_dirs:
            print(f"\n{Colors.BOLD}{Colors.RED}Failed Directories:{Colors.END}")
            for dir_name, error in failed_dirs:
                print(f"  • {dir_name}: {error}")
        
        print(f"{Colors.CYAN}{'=' * 60}{Colors.END}")
    
    def _should_skip_scan(self, subdir: Path) -> Tuple[bool, str]:
        """Check if a directory should be skipped based on mtime optimization"""
        scan_file = subdir / '.freight' / 'scan.json'
        
        # If no scan.json exists, don't skip
        if not scan_file.exists():
            return False, ""
        
        try:
            # Get directory mtime
            dir_stat = subdir.stat()
            dir_mtime = int(dir_stat.st_mtime)
            
            # Get scan file mtime from JSON
            with open(scan_file, 'r') as f:
                scan_data = json.load(f)
            
            scan_dir_mtime = scan_data.get('directory_mtime')
            if scan_dir_mtime is None:
                return False, "no mtime in scan data"
            
            scan_dir_mtime = int(scan_dir_mtime)
            
            # Skip if directory hasn't been modified since last scan
            if dir_mtime <= scan_dir_mtime:
                return True, "no changes"
            else:
                return False, "directory modified"
                
        except (json.JSONDecodeError, IOError, ValueError, KeyError) as e:
            # If we can't read the scan file or mtime, don't skip
            return False, f"scan data invalid: {e}"
    
    def run_scan(self, extra_args: Optional[List[str]] = None) -> None:
        """Run the freight-scan.sh script with orchestrator logic"""
        # Run orchestrated scan instead of calling script directly
        self.run_orchestrated_scan()

    def analyze_shared_directories(self) -> Dict[str, int]:
        """Analyze shared directories across all subdirectories"""
        if not self.migration_root.exists():
            raise FileNotFoundError(f"Migration root not found: {self.migration_root}")
        
        directory_counts = {}
        ignore_list = self.config_manager.get_shared_directory_ignore_list()
        
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
    
    def display_shared_directories(self) -> None:
        """Display shared directories analysis"""
        directory_counts = self.analyze_shared_directories()
        threshold = self.config_manager.get_shared_directory_threshold()
        ignore_list = self.config_manager.get_shared_directory_ignore_list()
        
        # Use DisplayManager to show shared directories
        display_manager = DisplayManager(self.migration_root, self.scan_results)
        display_manager.display_shared_directories(directory_counts, threshold, ignore_list)
    
    # Delegate config methods to ConfigManager
    def ensure_global_config(self, migration_root: str) -> bool:
        """Ensure global config exists and is properly set up. Returns True if config was created."""
        return self.config_manager.ensure_global_config(migration_root)
    
    def get_shared_directory_threshold(self) -> int:
        """Get shared directory threshold from config"""
        return self.config_manager.get_shared_directory_threshold()
    
    def get_shared_directory_ignore_list(self) -> List[str]:
        """Get shared directory ignore list from config"""
        return self.config_manager.get_shared_directory_ignore_list()