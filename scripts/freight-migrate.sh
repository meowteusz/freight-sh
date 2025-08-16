#!/bin/bash
set -euo pipefail

# freight-migrate.sh - Migrate a single directory using rsync
# Usage: freight-migrate.sh <source_dir> <dest_dir> [migration_root]

# Configuration
SCRIPT_NAME="freight-migrate"
VERSION="1.0.0"
SCRIPT_DIR="$(dirname "$(realpath "$0")")"

# Source shared libraries  
source "$SCRIPT_DIR/utils/logging.sh"
source "$SCRIPT_DIR/utils/json-utils.sh"

# Function to create migration JSON log
create_migrate_json() {
    local status="$1"
    local bytes_transferred="$2"
    local files_transferred="$3"
    local start_time="$4"
    local end_time="$5"
    local error_message="${6:-}"
    
    jq -n \
        --arg start_time "$start_time" \
        --arg end_time "$end_time" \
        --argjson bytes_transferred "$bytes_transferred" \
        --argjson files_transferred "$files_transferred" \
        --arg status "$status" \
        --arg error_message "$error_message" \
        --arg version "$VERSION" \
        '{
            start_time: $start_time,
            end_time: $end_time,
            bytes_transferred: $bytes_transferred,
            files_transferred: $files_transferred,
            status: $status,
            error_message: $error_message,
            version: $version
        }'
}

# Function to parse rsync stats from output
parse_rsync_stats() {
    local rsync_output="$1"
    local bytes_transferred=0
    local files_transferred=0
    
    # Extract stats from rsync output
    if echo "$rsync_output" | grep -q "Total transferred file size:"; then
        bytes_transferred=$(echo "$rsync_output" | grep "Total transferred file size:" | awk '{print $5}' | tr -d ',')
    fi
    
    if echo "$rsync_output" | grep -q "Number of files transferred:"; then
        files_transferred=$(echo "$rsync_output" | grep "Number of files transferred:" | awk '{print $5}' | tr -d ',')
    fi
    
    echo "$bytes_transferred $files_transferred"
}

# Main migration function
migrate_directory() {
    local source_dir="$1"
    local dest_dir="$2"
    local migration_root="${3:-}"
    
    # Validate inputs
    if [[ ! -d "$source_dir" ]]; then
        log_error "Source directory does not exist: $source_dir"
        exit 1
    fi
    
    # Check that .freight directory exists in source (required for proper orchestration)
    local freight_dir="$source_dir/.freight"
    if [[ ! -d "$freight_dir" ]]; then
        log_error "Source directory missing .freight metadata: $source_dir"
        log_error "This indicates the directory was not properly scanned. Run 'freight.py scan' first."
        exit 1
    fi
    
    # Ensure destination parent directory exists
    local dest_parent
    dest_parent="$(dirname "$dest_dir")"
    if [[ ! -d "$dest_parent" ]]; then
        log_error "Destination parent directory does not exist: $dest_parent"
        exit 1
    fi
    
    log_info "Starting migration of $(basename "$source_dir")"
    log_info "Source: $source_dir"
    log_info "Destination: $dest_dir"
    
    # Migration metadata
    local start_time
    start_time=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    local end_time
    local status="failed"
    local bytes_transferred=0
    local files_transferred=0
    local error_message=""
    
    # Default rsync flags (can be overridden from config)
    local rsync_flags="-avxHAX --numeric-ids --compress --partial --progress --stats"
    
    # Try to read rsync flags from migration root config if available
    if [[ -n "$migration_root" && -f "$migration_root/.freight/config.json" ]]; then
        local config_flags
        config_flags=$(jq -r '.migrate.rsync_flags // "-avxHAX --numeric-ids --compress --partial --progress --stats"' "$migration_root/.freight/config.json" 2>/dev/null || echo "")
        if [[ -n "$config_flags" ]]; then
            rsync_flags="$config_flags --stats"
        fi
    fi
    
    # Execute rsync with progress display
    local rsync_output=""
    local rsync_temp_file
    rsync_temp_file=$(mktemp)
    
    log_info "Executing rsync with flags: $rsync_flags"
    
    if rsync $rsync_flags "$source_dir/" "$dest_dir/" 2>&1 | tee "$rsync_temp_file"; then
        status="completed"
        log_success "Migration completed successfully"
        
        # Parse rsync statistics
        rsync_output=$(cat "$rsync_temp_file")
        read -r bytes_transferred files_transferred <<< "$(parse_rsync_stats "$rsync_output")"
        
    else
        status="failed"
        error_message="rsync command failed"
        rsync_output=$(cat "$rsync_temp_file")
        log_error "Migration failed: $error_message"
    fi
    
    rm -f "$rsync_temp_file"
    
    end_time=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    
    # Create migration log
    local migrate_json
    migrate_json=$(create_migrate_json "$status" "$bytes_transferred" "$files_transferred" "$start_time" "$end_time" "$error_message")
    
    # Save migration log
    local migrate_log="$freight_dir/migrate.json"
    echo "$migrate_json" > "$migrate_log"
    
    log_info "Migration log saved: $migrate_log"
    
    # Display summary
    echo
    log_info "Migration Summary:"
    log_info "  Status: $status"
    log_info "  Files transferred: $files_transferred"
    log_info "  Bytes transferred: $bytes_transferred"
    log_info "  Duration: $start_time to $end_time"
    
    # Exit with appropriate code
    if [[ "$status" == "completed" ]]; then
        exit 0
    else
        exit 1
    fi
}

# Main script execution
main() {
    if [[ $# -lt 2 ]]; then
        echo "Usage: $0 <source_dir> <dest_dir> [migration_root]"
        echo
        echo "Arguments:"
        echo "  source_dir      Source directory to migrate"
        echo "  dest_dir        Destination directory for migration"
        echo "  migration_root  Optional migration root for config lookup"
        echo
        echo "Example:"
        echo "  $0 /nfs1/students/alice /nfs2/students/alice /nfs1/students"
        exit 1
    fi
    
    local source_dir="$1"
    local dest_dir="$2"
    local migration_root="${3:-}"
    
    # Resolve paths
    source_dir=$(realpath "$source_dir")
    dest_dir=$(realpath "$dest_dir")
    if [[ -n "$migration_root" ]]; then
        migration_root=$(realpath "$migration_root")
    fi
    
    migrate_directory "$source_dir" "$dest_dir" "$migration_root"
}

main "$@"