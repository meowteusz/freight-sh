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
Usage: $SCRIPT_NAME <migration_root>

Scans all immediate subdirectories and creates .freight/scan.json files.

Examples:
    $SCRIPT_NAME /nfs1/students
EOF
}



# Check if directory needs scanning based on mtime
needs_scan() {
    local target_dir="$1"
    local scan_file="$target_dir/.freight/scan.json"
    
    # Always scan if no previous scan exists
    [ ! -f "$scan_file" ] && return 0
    
    # Get directory mtime (in seconds since epoch)
    local dir_mtime
    dir_mtime=$(stat -c %Y "$target_dir" 2>/dev/null || stat -f %m "$target_dir" 2>/dev/null || echo "0")
    
    # Get last scan's directory mtime from JSON
    local last_dir_mtime
    last_dir_mtime=$(jq -r '.directory_mtime // empty' "$scan_file" 2>/dev/null || echo "")
    
    # If no mtime in scan file, assume we need to rescan
    [ -z "$last_dir_mtime" ] && return 0
    
    # Compare mtimes - if directory is newer, we need to scan
    [ "$dir_mtime" -gt "$last_dir_mtime" ] && return 0
    
    # Directory unchanged
    return 1
}

# Scan a single directory
scan_directory() {
    local target_dir="$1"
    local freight_dir="$target_dir/.freight"
    
    mkdir -p "$freight_dir"
    
    # Get directory mtime
    local dir_mtime
    dir_mtime=$(stat -c %Y "$target_dir" 2>/dev/null || stat -f %m "$target_dir" 2>/dev/null || echo "0")
    
    # Get directory size and file count
    local size_bytes
    size_bytes=$(du -sb "$target_dir" | cut -f1)
    
    local file_count
    file_count=$(find "$target_dir" -type f -not -path "$freight_dir/*" | wc -l)
    
    # Create JSON log with mtime
    create_scan_json "$target_dir" "$size_bytes" "$file_count" "$SCRIPT_NAME" "$VERSION" "$dir_mtime" \
        > "$freight_dir/scan.json"
    
    echo "$size_bytes"
}

main() {
    # Validate arguments
    [ $# -eq 1 ] || { usage; exit 1; }
    
    local migration_root="$1"
    
    # Validate directory
    [ -d "$migration_root" ] || { log_error "Directory not found: $migration_root"; exit 1; }
    [ -r "$migration_root" ] || { log_error "Directory not readable: $migration_root"; exit 1; }
    
    # Check dependencies
    command -v du >/dev/null || { log_error "Missing dependency: du"; exit 1; }
    command -v jq >/dev/null || { log_error "Missing dependency: jq"; exit 1; }
    
    migration_root=$(realpath "$migration_root")
    
    log_info "Starting scan of: $migration_root"
    
    # Get subdirectories
    local subdirs=()
    while IFS= read -r -d '' dir; do
        subdirs+=("$dir")
    done < <(find "$migration_root" -mindepth 1 -maxdepth 1 -type d -print0)
    
    [ ${#subdirs[@]} -gt 0 ] || { log_warning "No subdirectories found"; exit 0; }
    
    log_info "Found ${#subdirs[@]} directories to scan"
    
    local total_bytes=0
    local current=0
    
    # Scan each directory
    local skipped=0
    for dir in "${subdirs[@]}"; do
        current=$((current + 1))
        local dir_name
        dir_name=$(basename "$dir")
        
        show_progress "$current" "${#subdirs[@]}" "Checking: $dir_name"
        
        # Check if directory needs scanning
        if needs_scan "$dir"; then
            printf " [SCAN]"
            local dir_size
            if dir_size=$(scan_directory "$dir"); then
                total_bytes=$((total_bytes + dir_size))
                printf " ${GREEN}✓${NC}"
            else
                printf " ${RED}✗${NC}"
            fi
        else
            # Directory unchanged, get size from existing scan
            local existing_size
            existing_size=$(jq -r '.size_bytes // 0' "$dir/.freight/scan.json" 2>/dev/null || echo "0")
            total_bytes=$((total_bytes + existing_size))
            skipped=$((skipped + 1))
            printf " ${YELLOW}↻${NC}"
        fi
    done
    
    finish_progress
    
    # Update root config
    declare -A updates=(
        ["total_size_bytes"]="$total_bytes"
        ["total_directories"]="${#subdirs[@]}"
    )
    update_root_config "$migration_root" "scan" updates
    
    log_success "Scan completed!"
    log_info "Total: $(bytes_to_human "$total_bytes") across ${#subdirs[@]} directories"
    if [ "$skipped" -gt 0 ]; then
        log_info "Skipped $skipped unchanged directories (mtime optimization)"
    fi
}

main "$@"