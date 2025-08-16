"""
Configuration management for Freight NFS Migration Suite
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any

from .utils import Colors, FREIGHT_VERSION

class ConfigManager:
    """Handles all configuration-related operations"""
    
    def __init__(self, script_dir: Path):
        self.script_dir = script_dir
        self.global_config_path = script_dir / 'config.json'
    
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
    
    def ensure_global_config(self, migration_root: str, dest_path: Optional[str] = None) -> bool:
        """Ensure global config exists and is properly set up. Returns True if config was created."""
        if self.global_config_path.exists():
            return False
        
        config_skeleton = {
            "config_version": FREIGHT_VERSION,
            "migration_root": migration_root,
            "dest_path": dest_path,
            "created_time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),

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
                "last_migrate_time": None,
                "rsync_flags": "-avxHAX --numeric-ids --compress --partial --info=progress2",

                "large_dir_threshold_bytes": 3221225472
            }
        }
        
        with open(self.global_config_path, 'w') as f:
            json.dump(config_skeleton, f, indent=2)
        
        return True
    
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
    
    def get_destination_path(self) -> Optional[str]:
        """Get destination path from global config"""
        if not self.global_config_path.exists():
            return None
        
        try:
            with open(self.global_config_path, 'r') as f:
                config = json.load(f)
            return config.get('dest_path')
        except (json.JSONDecodeError, IOError):
            return None
    
    def init_freight_root(self, root_path: Optional[str] = None) -> None:
        """Initialize a freight root directory with global config"""
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
        
        print(f"\n{Colors.BOLD}{Colors.CYAN}Initializing Freight Migration{Colors.END}")
        
        # Get source directory
        if root_path is None:
            current_dir = os.getcwd()
            source_input = input(f"\n{Colors.YELLOW}Enter source directory (press Enter for current directory):{Colors.END} ").strip()
            if source_input == "":
                root_dir = Path(current_dir).resolve()
            else:
                root_dir = Path(source_input).resolve()
        else:
            root_dir = Path(root_path).resolve()
        
        # Verify source directory exists
        if not root_dir.exists():
            print(f"{Colors.RED}Error: Source directory does not exist: {root_dir}{Colors.END}")
            sys.exit(1)
        
        if not root_dir.is_dir():
            print(f"{Colors.RED}Error: Source path is not a directory: {root_dir}{Colors.END}")
            sys.exit(1)
        
        # Get destination directory
        dest_input = input(f"{Colors.YELLOW}Enter destination directory:{Colors.END} ").strip()
        if not dest_input:
            print(f"{Colors.RED}Destination directory is required.{Colors.END}")
            sys.exit(1)
        
        dest_path = Path(dest_input).resolve()
        
        # Create/update global config with destination path
        config_created = self.ensure_global_config(str(root_dir), str(dest_path))
        
        if config_created:
            print(f"\n{Colors.GREEN}✓{Colors.END} Created global config: {self.global_config_path}")
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
                config['dest_path'] = str(dest_path)
                with open(self.global_config_path, 'w') as f:
                    json.dump(config, f, indent=2)
                print(f"{Colors.GREEN}✓{Colors.END} Updated root and destination in global config")
            except (json.JSONDecodeError, IOError) as e:
                print(f"{Colors.RED}✗{Colors.END} Failed to update global config: {e}")
        
        print(f"\n{Colors.BOLD}{Colors.CYAN}Freight root initialized successfully!{Colors.END}")
        print(f"Source directory: {Colors.WHITE}{root_dir}{Colors.END}")
        print(f"Destination directory: {Colors.WHITE}{dest_path}{Colors.END}")
        print(f"\nNext steps:")
        print(f"  1. Edit {Colors.CYAN}{self.global_config_path}{Colors.END} to customize settings")
        print(f"  2. Run {Colors.YELLOW}freight.py scan{Colors.END} to scan directories")