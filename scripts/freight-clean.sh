#!/bin/bash

# freight-clean - Directory cleaner for Freight NFS migration suite

set -euo pipefail

# Configuration
SCRIPT_NAME="freight-clean"
VERSION="1.0.0"
SCRIPT_DIR="$(dirname "$(realpath "$0")")"

# Source shared libraries
source "$SCRIPT_DIR/freight-lib/logging.sh"
source "$SCRIPT_DIR/freight-lib/json-utils.sh"



usage() {
    cat << EOF
Usage: $SCRIPT_NAME [migration_root] [--confirm]

Deletes configured directories from immediate subdirectory roots.
If no migration_root is provided, uses the root from global config.
By default, runs in dry-run mode to show what would be cleaned.

Options:
    --confirm    Actually perform the cleaning (default is dry-run)

Examples:
    $SCRIPT_NAME                  # Uses global config, dry run (default)
    $SCRIPT_NAME --confirm        # Uses global config, real run
    $SCRIPT_NAME /nfs1/students --confirm   # Uses explicit migration root, real run
EOF
}

# Load directory names from global config
get_clean_directories() {
    local config_file
    config_file=$(get_global_config)
    
    if [ ! -f "$config_file" ]; then
        log_error "Global configuration file not found: $config_file"
        log_info "Please run 'freight.py init' first to create configuration"
        return 1
    fi
    
    local dir_names
    if ! dir_names=$(jq -r '.cleaning.target_directories[]?' "$config_file" 2>/dev/null); then
        log_error "Failed to read directory names from global config file"
        log_info "Please ensure global config.json has a valid cleaning.target_directories array"
        return 1
    fi
    
    if [ -z "$dir_names" ]; then
        log_error "No directory names found in global configuration"
        log_info "Please configure cleaning.target_directories in global config.json"
        return 1
    fi
    
    echo "$dir_names"
}

# Clean a single directory
clean_directory() {
    local target_dir="$1"
    local dry_run="$2"
    shift 2
    local dir_names=("$@")
    
    local freight_dir="$target_dir/.freight"
    mkdir -p "$freight_dir"
    
    local total_cleaned=0
    local cleaned_items=()
    
    # Check each directory name for exact matches
    for dir_name in "${dir_names[@]}"; do
        local target_path="$target_dir/$dir_name"
        
        # Skip if directory doesn't exist
        [ -d "$target_path" ] || continue
        
        local item_size=0
        if command -v gdu >/dev/null 2>&1; then
            # GNU du available
            item_size=$(gdu -sb "$target_path" 2>/dev/null | cut -f1 || echo "0")
        elif du -sb "$target_path" >/dev/null 2>&1; then
            # Linux du with -b flag
            item_size=$(du -sb "$target_path" 2>/dev/null | cut -f1 || echo "0")
        else
            # macOS du, use -k and convert to bytes
            local size_kb
            size_kb=$(du -sk "$target_path" 2>/dev/null | cut -f1 || echo "0")
            item_size=$((size_kb * 1024))
        fi
        
        if [ "$dry_run" = "true" ]; then
            cleaned_items+=("$dir_name ($(bytes_to_human "$item_size"))")
        else
            if rm -rf "$target_path" 2>/dev/null; then
                cleaned_items+=("$dir_name")
            fi
        fi
        
        total_cleaned=$((total_cleaned + item_size))
    done
    
    # Create JSON log
    local cleaned_items_json patterns_json
    if [ ${#cleaned_items[@]} -eq 0 ]; then
        cleaned_items_json='[]'
    else
        cleaned_items_json=$(printf '%s\n' "${cleaned_items[@]}" | jq -R . | jq -s . 2>/dev/null || echo '[]')
    fi
    patterns_json=$(printf '%s\n' "${dir_names[@]}" | jq -R . | jq -s .)
    
    create_clean_json "$target_dir" "$total_cleaned" "${#cleaned_items[@]}" \
        "$cleaned_items_json" "$patterns_json" "$dry_run" "$SCRIPT_NAME" "$VERSION" \
        > "$freight_dir/clean.json"
    
    echo "$total_cleaned"
}

main() {
    local migration_root=""
    local dry_run="true"  # Default to dry run
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --confirm) dry_run="false"; shift ;;
            --help|-h) usage; exit 0 ;;
            -*) log_error "Unknown option: $1"; exit 1 ;;
            *) migration_root="$1"; shift ;;
        esac
    done
    
    # If no migration root provided, get from global config
    if [ -z "$migration_root" ]; then
        if ! migration_root=$(get_migration_root); then
            exit 1
        fi
    fi
    [ -d "$migration_root" ] || { log_error "Directory not found: $migration_root"; exit 1; }
    [ -w "$migration_root" ] || { log_error "Directory not writable: $migration_root"; exit 1; }
    
    command -v jq >/dev/null || { log_error "Missing dependency: jq"; exit 1; }
    
    migration_root=$(realpath "$migration_root")
    
    log_info "Starting clean of: $migration_root"
    if [ "$dry_run" = "true" ]; then
        log_warning "DRY RUN MODE - No files will be deleted (use --confirm to actually clean)"
    else
        log_warning "CLEANING MODE - Files will be permanently deleted"
    fi
    
    # Load directory names and get subdirectories
    local dir_names=()
    local dir_output
    if ! dir_output=$(get_clean_directories); then
        exit 1
    fi
    
    while IFS= read -r dir_name; do
        dir_names+=("$dir_name")
    done <<< "$dir_output"
    
    local subdirs=()
    while IFS= read -r -d '' dir; do
        subdirs+=("$dir")
    done < <(find "$migration_root" -mindepth 1 -maxdepth 1 -type d -print0)
    
    [ ${#subdirs[@]} -gt 0 ] || { log_warning "No subdirectories found"; exit 0; }
    
    log_info "Checking ${#dir_names[@]} directory names across ${#subdirs[@]} subdirectories"
    
    local total_cleaned=0
    local current=0
    
    # Clean each directory
    for dir in "${subdirs[@]}"; do
        current=$((current + 1))
        local dir_name
        dir_name=$(basename "$dir")
        
        show_progress "$current" "${#subdirs[@]}" "Cleaning: $dir_name"
        
        local dir_cleaned
        if dir_cleaned=$(clean_directory "$dir" "$dry_run" "${dir_names[@]}"); then
            total_cleaned=$((total_cleaned + dir_cleaned))
            if [ "$dir_cleaned" -gt 0 ]; then
                printf " ${GREEN}✓ %s${NC}" "$(bytes_to_human "$dir_cleaned")"
            else
                printf " ${YELLOW}∅${NC}"
            fi
        else
            printf " ${RED}✗${NC}"
        fi
    done
    
    finish_progress
    
    # Update global config
    update_global_config "clean" "total_cleaned_bytes=$total_cleaned" "clean_was_dry_run=$dry_run"
    
    local action="cleaned"
    [ "$dry_run" = "true" ] && action="would clean"
    
    log_success "Clean completed!"
    log_info "Total $action: $(bytes_to_human "$total_cleaned") across ${#subdirs[@]} directories"
}

main "$@"