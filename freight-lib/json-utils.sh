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

# Update root config with completion status
update_root_config() {
    local migration_root="$1"
    local operation="$2"  # scan, clean, migrate, etc
    shift 2
    local -n updates_ref=$1  # associative array of key=value updates
    
    local root_freight_dir="$migration_root/.freight"
    mkdir -p "$root_freight_dir"
    
    local config_file="$root_freight_dir/config.json"
    local completion_time
    completion_time=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    
    # Build jq update command
    local jq_cmd=". | .${operation}_completed = true | .last_${operation}_time = \"$completion_time\""
    
    # Add custom updates
    for key in "${!updates_ref}"; do
        local value="${updates_ref[$key]}"
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
    done
    
    if [ -f "$config_file" ]; then
        # Update existing config
        jq "$jq_cmd" "$config_file" > "$config_file.tmp" && mv "$config_file.tmp" "$config_file"
    else
        # Create new config
        echo '{}' | jq "$jq_cmd" > "$config_file"
    fi
}

# Convert bytes to human readable format
bytes_to_human() {
    local bytes="$1"
    numfmt --to=iec-i --suffix=B "$bytes" 2>/dev/null || echo "$bytes bytes"
}