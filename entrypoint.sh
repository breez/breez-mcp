#!/bin/bash

# Docker entrypoint for Breez MCP Server
# This script ensures proper MCP server initialization and signal handling

set -euo pipefail

log() {
    >&2 echo "$*"
}

# Function to handle shutdown signals
cleanup() {
    log "Received shutdown signal, stopping MCP server..."
    # The FastMCP server will handle cleanup through the lifespan manager
    exit 0
}

# Register signal handlers
trap cleanup SIGINT SIGTERM

# Optionally load environment variables from file (when mounted as secret)
if [[ -n "${BREEZ_ENV_FILE:-}" && -f "${BREEZ_ENV_FILE}" ]]; then
    log "Loading environment variables from ${BREEZ_ENV_FILE}"
    set -a
    # shellcheck disable=SC1090
    source "${BREEZ_ENV_FILE}"
    set +a
fi

log "Starting Breez MCP Server in Docker..."

# Check if required environment variables are set
if [[ -z "${BREEZ_API_KEY:-}" ]]; then
    log "Error: BREEZ_API_KEY environment variable is required"
    exit 1
fi

if [[ -z "${BREEZ_MNEMONIC:-}" ]]; then
    log "Error: BREEZ_MNEMONIC environment variable is required"
    exit 1
fi

# Ensure data directory exists with default value
BREEZ_DATA_DIR="${BREEZ_DATA_DIR:-/app/data}"
mkdir -p "${BREEZ_DATA_DIR}"

log "Environment validation passed"
log "Data directory: ${BREEZ_DATA_DIR}"
log "Network: ${BREEZ_NETWORK:-mainnet}"

# Override with command line arguments if provided
if [[ $# -gt 0 ]]; then
    CMD=("$@")
else
    # Use the unified main.py that supports both modes
    log "Starting unified Breez MCP server..."
    CMD=("python" "-m" "src.main")
fi

exec "${CMD[@]}"
