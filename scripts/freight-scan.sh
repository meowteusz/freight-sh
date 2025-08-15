#!/bin/bash

# freight-scan - Directory size scanner for Freight NFS migration suite

set -euo pipefail

# Configuration
SCRIPT_NAME="freight-scan"
VERSION="1.0.0"
SCRIPT_DIR="$(dirname "$(realpath "$0")")"

# Source shared libraries
source "$SCRIPT_DIR/freight-lib/logging.sh"
source "$SCRIPT_DIR/freight-lib/json-utils.sh"

# Import color codes from logging.sh for use in this script
BLUE='\033[0;34m'
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

usage() {
    cat << EOF
Usage: $SCRIPT_NAME [target_directory]

Scans a directory and creates scan.json in the current directory.
If no target_directory is provided, scans the current directory.

Examples:
    $SCRIPT_NAME                # Scans current directory
    $SCRIPT_NAME /path/to/scan  # Scans specified directory
EOF
}





scan_single_directory() {
    local target_dir="$1"
    local output_dir="${2:-.}"
    
    log_info "Scanning directory: $target_dir"
    
    # Get directory mtime (cross-platform)
    local dir_mtime  
    if stat -c %Y "$target_dir" >/dev/null 2>&1; then
        # Linux stat
        dir_mtime=$(stat -c %Y "$target_dir")
    elif stat -f %m "$target_dir" >/dev/null 2>&1; then
        # macOS stat
        dir_mtime=$(stat -f %m "$target_dir")
    else
        dir_mtime="0"
    fi
    
    # Get directory size and file count (cross-platform)
    local size_bytes
    if command -v gdu >/dev/null 2>&1; then
        # GNU du available
        size_bytes=$(gdu -sb "$target_dir" | cut -f1)
    elif du -sb "$target_dir" >/dev/null 2>&1; then
        # Linux du with -b flag
        size_bytes=$(du -sb "$target_dir" | cut -f1)
    else
        # macOS du, use -k and convert to bytes
        local size_kb
        size_kb=$(du -sk "$target_dir" | cut -f1)
        size_bytes=$((size_kb * 1024))
    fi
    
    local file_count
    file_count=$(find "$target_dir" -type f | wc -l)
    
    # Create JSON log in specified output directory
    create_scan_json "$size_bytes" "$file_count" "$dir_mtime" > "$output_dir/scan.json"
    
    log_success "Scan completed: $(bytes_to_human "$size_bytes") with $file_count files"
}

scan_migration_root() {
    local migration_root="$1"
    
    log_info "Starting scan of migration root: $migration_root"
    log_info "Scanning subdirectories individually..."
    
    # Find all subdirectories, excluding .freight
    local subdirs=()
    while IFS= read -r -d '' subdir; do
        subdirs+=("$subdir")
    done < <(find "$migration_root" -mindepth 1 -maxdepth 1 -type d -not -name '.freight' -print0)
    
    if [ ${#subdirs[@]} -eq 0 ]; then
        log_error "No subdirectories found in migration root: $migration_root"
        exit 1
    fi
    
    local total_dirs=${#subdirs[@]}
    local successful_scans=0
    local failed_scans=0
    
    log_info "Found $total_dirs subdirectories to scan"
    echo
    
    local i=0
    for subdir in "${subdirs[@]}"; do
        ((i++))
        local dirname=$(basename "$subdir")
        
        printf "${BLUE}[%d/%d]${NC} Scanning %s... " "$i" "$total_dirs" "$dirname"
        
        # Create .freight directory if it doesn't exist
        local freight_dir="$subdir/.freight"
        mkdir -p "$freight_dir"
        
        # Scan this subdirectory
        if scan_single_directory "$subdir" "$freight_dir" >/dev/null 2>&1; then
            printf "${GREEN}✓${NC}\n"
            ((successful_scans++))
        else
            printf "${RED}✗${NC}\n"
            ((failed_scans++))
        fi
    done
    
    echo
    log_success "Migration root scan completed!"
    log_info "Successful: $successful_scans, Failed: $failed_scans, Total: $total_dirs"
    
    if [ $failed_scans -gt 0 ]; then
        log_warning "Some scans failed. Check individual directory permissions and disk space."
    fi
}

main() {
    local target_dir=""
    
    # Check if target directory was provided
    if [ $# -eq 1 ]; then
        target_dir="$1"
    elif [ $# -eq 0 ]; then
        target_dir="."
    else
        usage
        exit 1
    fi
    
    # Validate directory
    [ -d "$target_dir" ] || { log_error "Directory not found: $target_dir"; exit 1; }
    [ -r "$target_dir" ] || { log_error "Directory not readable: $target_dir"; exit 1; }
    
    # Check dependencies
    command -v du >/dev/null || { log_error "Missing dependency: du"; exit 1; }
    command -v jq >/dev/null || { log_error "Missing dependency: jq"; exit 1; }
    
    target_dir=$(realpath "$target_dir")
    
    log_info "Starting scan of: $target_dir"
    
    # Check if this is a migration root by looking for .freight-root marker
    if [ -f "$target_dir/.freight-root" ]; then
        log_info "Detected migration root (.freight-root marker found)"
        scan_migration_root "$target_dir"
    else
        # Single directory scan (original behavior)
        scan_single_directory "$target_dir" "."
        log_info "Results saved to: ./scan.json"
    fi
}

main "$@"