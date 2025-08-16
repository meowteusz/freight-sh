#!/bin/bash

# freight-scan - Directory size scanner for Freight NFS migration suite

set -euo pipefail

# Configuration
SCRIPT_NAME="freight-scan"
VERSION="1.0.0"
SCRIPT_DIR="$(dirname "$(realpath "$0")")"

# Source shared libraries
source "$SCRIPT_DIR/utils/logging.sh"
source "$SCRIPT_DIR/utils/json-utils.sh"

usage() {
    cat << EOF
Usage: $SCRIPT_NAME <target_directory>

Scans a directory and creates scan.json in target_directory/.freight/scan.json.
Assumes Linux environment.

Examples:
    $SCRIPT_NAME /path/to/scan  # Scans specified directory
EOF
}





scan_directory() {
    local target_dir="$1"
    
    # Get directory mtime (Linux only)
    local dir_mtime
    dir_mtime=$(stat -c %Y "$target_dir")
    
    # Get directory size and file count (Linux only)
    local size_bytes
    size_bytes=$(du -sb "$target_dir" | cut -f1)
    
    local file_count
    file_count=$(find "$target_dir" -type f | wc -l)
    
    # Create .freight directory if it doesn't exist
    local freight_dir="$target_dir/.freight"
    mkdir -p "$freight_dir"
    
    # Create JSON log in .freight directory
    create_scan_json "$size_bytes" "$file_count" "$dir_mtime" > "$freight_dir/scan.json"
    
    # Brief summary
    echo "Scanned $(basename "$target_dir"): $(bytes_to_human "$size_bytes") with $file_count files"
    echo "Results written to: $freight_dir/scan.json"
}



main() {
    # Check if target directory was provided
    if [ $# -ne 1 ]; then
        usage
        exit 1
    fi
    
    local target_dir="$1"
    
    # Validate directory
    [ -d "$target_dir" ] || { log_error "Directory not found: $target_dir"; exit 1; }
    [ -r "$target_dir" ] || { log_error "Directory not readable: $target_dir"; exit 1; }
    
    target_dir=$(realpath "$target_dir")
    
    # Scan the directory
    scan_directory "$target_dir"
}

main "$@"