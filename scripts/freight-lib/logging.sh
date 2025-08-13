#!/bin/bash

# freight-lib/logging.sh - Shared logging utilities for Freight suite

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

# Progress display function
show_progress() {
    local current="$1"
    local total="$2" 
    local item="$3"
    local status="${4:-}"
    
    printf "\r${BLUE}[%d/%d]${NC} %-40s %s" "$current" "$total" "$item" "$status"
}

# Finish progress line
finish_progress() {
    echo # New line after progress
}