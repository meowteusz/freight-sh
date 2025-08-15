"""
Main CLI entry point for Freight NFS Migration Suite
"""

import argparse
import os
import sys

from .utils import Colors
from .orchestrator import FreightOrchestrator

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
                print(f"{Colors.YELLOW}Global configuration created at {orchestrator.config_manager.global_config_path}{Colors.END}")
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
                print(f"{Colors.YELLOW}Global configuration created at {orchestrator.config_manager.global_config_path}{Colors.END}")
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
                print(f"{Colors.YELLOW}Global configuration created at {orchestrator.config_manager.global_config_path}{Colors.END}")
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
                print(f"{Colors.YELLOW}Global configuration created at {orchestrator.config_manager.global_config_path}{Colors.END}")
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