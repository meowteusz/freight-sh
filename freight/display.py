"""
Display and formatting functions for Freight NFS Migration Suite
"""

import os
import re
from typing import List, Dict, Any

from .utils import Colors, format_size
from .scan_result import ScanResult

class DisplayManager:
    """Handles all display and formatting operations"""
    
    def __init__(self, migration_root, scan_results: List[ScanResult]):
        self.migration_root = migration_root
        self.scan_results = scan_results
    
    def display_overview(self, stats: Dict[str, Any]) -> None:
        """Display the overview of scan status with grid layout for directories"""
        # Header
        print(f"\n{Colors.BOLD}{Colors.CYAN}Freight Scanner Overview{Colors.END}")
        print(f"{Colors.CYAN}{'=' * 60}{Colors.END}")
        print(f"Root: {Colors.WHITE}{self.migration_root}{Colors.END}")
        
        # Statistics summary
        print(f"\n{Colors.BOLD}Summary:{Colors.END}")
        print(f"  Scan status: {Colors.GREEN}{stats['scanned_directories']}{Colors.END}/{Colors.WHITE}{stats['total_directories']}{Colors.END} ({Colors.YELLOW}{stats['completion_rate']:.1f}%{Colors.END})")

        if stats['scanned_directories'] > 0:
            print(f"  Total size: {Colors.WHITE}{format_size(stats['total_size_bytes'])}{Colors.END}")
            print(f"  Total files: {Colors.WHITE}{stats['total_files']:,}{Colors.END}")
            
        # Add cleaning savings if any directories have clean data
        if stats['total_cleanable_bytes'] > 0:
            print(f"  Potential space savings: {Colors.YELLOW}{format_size(stats['total_cleanable_bytes'])}{Colors.END}")

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
        
        # Calculate consistent spacing
        num_blocks = len(results)
        separator_width = 2  # Fixed 2-space separator between blocks
        total_separator_space = (num_blocks - 1) * separator_width
        available_width = terminal_width - total_separator_space
        block_width = max(30, available_width // num_blocks)
        
        # Create formatted blocks for each directory
        blocks = []
        for result in results:
            block_lines = self._format_directory_block(result, block_width)
            blocks.append(block_lines)
        
        # Find max height
        max_height = max(len(block) for block in blocks) if blocks else 0
        
        # Pad blocks to same height
        for block in blocks:
            while len(block) < max_height:
                block.append(" " * block_width)
        
        # Print blocks side by side with consistent spacing
        for line_idx in range(max_height):
            line_parts = []
            for i, block in enumerate(blocks):
                line_parts.append(block[line_idx])
                # Add separator between blocks (but not after the last one)
                if i < len(blocks) - 1:
                    line_parts.append(" " * separator_width)
            print("".join(line_parts))
        
        # Add separator line
        print()
    
    def _format_directory_block(self, result: ScanResult, width: int) -> List[str]:
        """Format a single directory as a block with fixed width"""
        lines = []
        
        def pad_line(text: str, target_width: int) -> str:
            """Pad a line to target width, accounting for ANSI color codes"""
            # Count visible characters (excluding ANSI codes)
            visible_text = re.sub(r'\x1b\[[0-9;]*m', '', text)
            padding_needed = max(0, target_width - len(visible_text))
            return text + (" " * padding_needed)
        
        # Directory name with status icon (truncate if too long)
        display_name = result.name
        if len(display_name) > width - 3:  # Account for status icon space
            display_name = display_name[:width-6] + "..."
        name_line = f"{display_name} {result.status_icon}"
        lines.append(pad_line(name_line, width))
        
        if result.has_scan:
            # Basic scan stats
            lines.append(pad_line(f"Size: {result.format_size()}", width))
            lines.append(pad_line(f"Files: {result.file_count:,}", width))
            
            if result.scan_time:
                scan_date = result.scan_time[:10]  # Just date part
                lines.append(pad_line(f"Scanned: {scan_date}", width))
            
            # Problem directories if available
            if result.has_clean_data:
                problem_dirs = result.problem_directories
                if problem_dirs:
                    total_savings = sum(p.get('bytes_saved', 0) for p in problem_dirs)
                    lines.append(pad_line(f"Savings: {format_size(total_savings)}", width))
                    
                    # Show up to 2 problem directories
                    for prob_dir in problem_dirs[:2]:
                        pattern = prob_dir.get('pattern', 'unknown')
                        size = format_size(prob_dir.get('bytes_saved', 0))
                        # Truncate pattern if too long
                        max_pattern_len = width - len(size) - 4  # Account for "• " and " ()"
                        if len(pattern) > max_pattern_len:
                            pattern = pattern[:max_pattern_len-3] + "..."
                        line_text = f"• {pattern} ({size})"
                        lines.append(pad_line(line_text, width))
                    
                    if len(problem_dirs) > 2:
                        lines.append(pad_line(f"+ {len(problem_dirs) - 2} more...", width))
        else:
            not_scanned_line = f"{Colors.RED}Not scanned{Colors.END}"
            lines.append(pad_line(not_scanned_line, width))
        
        return lines
    
    def display_shared_directories(self, directory_counts: Dict[str, int], threshold: int, ignore_list: List[str]) -> None:
        """Display shared directories analysis"""
        print(f"\n{Colors.BOLD}{Colors.CYAN}Freight Shared Directory Analysis{Colors.END}")
        print(f"{Colors.CYAN}{'=' * 60}{Colors.END}")
        print(f"Root: {Colors.WHITE}{self.migration_root}{Colors.END}")
        
        if ignore_list:
            print(f"Ignoring: {Colors.YELLOW}{', '.join(ignore_list)}{Colors.END}")
        
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
        
        # Calculate total subdirs (excluding .freight)
        from pathlib import Path
        total_subdirs = len([d for d in Path(self.migration_root).iterdir() if d.is_dir() and d.name != '.freight'])
        
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