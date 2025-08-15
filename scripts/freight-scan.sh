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
    
    # Create JSON log in current directory (always overwrite)
    create_scan_json "$size_bytes" "$file_count" "$dir_mtime" > "./scan.json"
    
    log_success "Scan completed!"
    log_info "Scanned: $(bytes_to_human "$size_bytes") with $file_count files"
    log_info "Results saved to: ./scan.json"
}

main "$@"