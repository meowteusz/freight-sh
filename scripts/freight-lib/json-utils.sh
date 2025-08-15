#!/bin/bash

# freight-lib/json-utils.sh - JSON utilities for Freight suite

# Create scan JSON log
create_scan_json() {
    local size_bytes="$1"
    local file_count="$2"
    local directory_mtime="$3"
    
    local scan_time
    scan_time=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    
    jq -n \
        --arg scan_time "$scan_time" \
        --argjson size_bytes "$size_bytes" \
        --argjson file_count "$file_count" \
        --arg directory_mtime "$directory_mtime" \
        '{
            scan_time: $scan_time,
            size_bytes: $size_bytes,
            file_count: $file_count,
            directory_mtime: $directory_mtime
        }'
}

# Create clean JSON log
create_clean_json() {
    local bytes_cleaned="$1"
    local items_cleaned="$2"
    local patterns_json="$3"
    
    local clean_time
    clean_time=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    
    jq -n \
        --arg clean_time "$clean_time" \
        --argjson bytes_cleaned "$bytes_cleaned" \
        --argjson items_cleaned "$items_cleaned" \
        --argjson patterns "$patterns_json" \
        '{
            clean_time: $clean_time,
            bytes_cleaned: $bytes_cleaned,
            items_cleaned: $items_cleaned,
            patterns: $patterns
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