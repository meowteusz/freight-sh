#!/bin/bash

# freight-lib/json-utils.sh - JSON utilities for Freight suite

# Create scan JSON log
create_scan_json() {
    local target_dir="$1"
    local size_bytes="$2"
    local file_count="$3"
    local tool_name="$4"
    local tool_version="$5"
    local directory_mtime="$6"
    
    local scan_time
    scan_time=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    
    local scan_id
    scan_id=$(date +"%Y%m%d_%H%M%S")
    
    jq -n \
        --arg scan_id "$scan_id" \
        --arg directory "$target_dir" \
        --arg scan_time "$scan_time" \
        --argjson size_bytes "$size_bytes" \
        --argjson file_count "$file_count" \
        --arg status "completed" \
        --arg tool "$tool_name" \
        --arg version "$tool_version" \
        --arg directory_mtime "$directory_mtime" \
        '{
            scan_id: $scan_id,
            directory: $directory,
            scan_time: $scan_time,
            size_bytes: $size_bytes,
            file_count: $file_count,
            directory_mtime: $directory_mtime,
            status: $status,
            tool: $tool,
            version: $version
        }'
}

# Create clean JSON log
create_clean_json() {
    local target_dir="$1"
    local bytes_cleaned="$2"
    local items_cleaned="$3"
    local cleaned_items_json="$4"
    local patterns_json="$5"
    local dry_run="$6"
    local tool_name="$7"
    local tool_version="$8"
    
    local clean_time
    clean_time=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    
    local clean_id
    clean_id=$(date +"%Y%m%d_%H%M%S")
    
    jq -n \
        --arg clean_id "$clean_id" \
        --arg directory "$target_dir" \
        --arg clean_time "$clean_time" \
        --argjson bytes_cleaned "$bytes_cleaned" \
        --argjson items_cleaned "$items_cleaned" \
        --argjson cleaned_items "$cleaned_items_json" \
        --argjson patterns "$patterns_json" \
        --arg status "completed" \
        --arg tool "$tool_name" \
        --arg version "$tool_version" \
        --arg dry_run "$dry_run" \
        '{
            clean_id: $clean_id,
            directory: $directory,
            clean_time: $clean_time,
            bytes_cleaned: $bytes_cleaned,
            items_cleaned: $items_cleaned,
            cleaned_items: $cleaned_items,
            patterns_used: $patterns,
            status: $status,
            tool: $tool,
            version: $version,
            dry_run: ($dry_run == "true")
        }'
}

# Get global config file path
get_global_config() {
    local script_dir
    script_dir="$(dirname "$(dirname "$(realpath "$0")")")"  # Go up two levels to freight.py dir
    echo "$script_dir/config.json"
}

# Update global config with completion status  
# Usage: update_global_config "operation" "key1=value1" "key2=value2" ...
update_global_config() {
    local operation="$1"
    shift 1
    
    local config_file
    config_file=$(get_global_config)
    local completion_time
    completion_time=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    
    # Build jq update command
    local jq_cmd=". | .${operation}_completed = true | .last_${operation}_time = \"$completion_time\""
    
    # Add custom updates from remaining arguments
    for update in "$@"; do
        if [[ "$update" == *"="* ]]; then
            local key="${update%%=*}"
            local value="${update#*=}"
            
            if [[ "$value" =~ ^[0-9]+$ ]]; then
                # Numeric value
                jq_cmd="$jq_cmd | .$key = $value"
            elif [[ "$value" == "true" || "$value" == "false" ]]; then
                # Boolean value
                jq_cmd="$jq_cmd | .$key = $value"
            else
                # String value
                jq_cmd="$jq_cmd | .$key = \"$value\""
            fi
        fi
    done
    
    if [ -f "$config_file" ]; then
        # Update existing config
        jq "$jq_cmd" "$config_file" > "$config_file.tmp" && mv "$config_file.tmp" "$config_file"
    else
        # Config should exist by now, but create basic one if needed
        echo '{}' | jq "$jq_cmd" > "$config_file"
    fi
}

# Get migration root from global config
get_migration_root() {
    local config_file
    config_file=$(get_global_config)
    
    if [ ! -f "$config_file" ]; then
        echo "Error: Global config not found: $config_file" >&2
        echo "Please run 'freight.py init' first" >&2
        return 1
    fi
    
    local migration_root
    migration_root=$(jq -r '.root_directory // empty' "$config_file" 2>/dev/null)
    
    if [ -z "$migration_root" ]; then
        echo "Error: No root_directory found in global config" >&2
        return 1
    fi
    
    echo "$migration_root"
}

# Convert bytes to human readable format
bytes_to_human() {
    local bytes="$1"
    numfmt --to=iec-i --suffix=B "$bytes" 2>/dev/null || echo "$bytes bytes"
}