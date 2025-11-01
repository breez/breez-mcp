# Breez MCP Server — FastMCP Implementation

A unified MCP server that exposes Lightning functionality through the Breez SDK (Spark implementation) using FastMCP. Supports both stdio and HTTP transport modes.

## Prerequisites

- Python 3.11+ (for local development or `uvx`)
- [Docker](https://docs.docker.com/get-docker/) (optional, for container workflows)
- [uv](https://github.com/astral-sh/uv) (optional, for ephemeral environments)
- Breez API key which you can request [here](https://breez.technology/request-api-key/#contact-us-form-sdk)

## Configure Credentials

```bash
cp .env.example .env
```

Edit `.env` with your secrets. Required variables:

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `BREEZ_API_KEY` | ✅ | – | Breez Spark API key |
| `BREEZ_MNEMONIC` | ✅ | – | 12-word mnemonic controlling the wallet |
| `BREEZ_NETWORK` | ❌ | `mainnet` | Set to `testnet` for sandbox usage |
| `BREEZ_DATA_DIR` | ❌ | `./data` | Wallet storage directory |
| `BREEZ_TRANSPORT_MODE` | ❌ | `stdio` | Transport mode: `stdio`, `http`, or `asgi` |
| `BREEZ_HTTP_HOST` | ❌ | `0.0.0.0` | HTTP server host (HTTP mode only) |
| `BREEZ_HTTP_PORT` | ❌ | `8000` | HTTP server port (HTTP mode only) |
| `BREEZ_HTTP_PATH` | ❌ | `/mcp` | HTTP endpoint path (HTTP mode only) |

## Run the Server

Choose the runtime that transport mode that fits your workflow.

### STDIO Mode (Default for MCP clients)

For use with Claude Desktop and other MCP clients:

```bash
# Local virtualenv
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m src.main

# Or with uvx (no persistent venv)
uvx --from . breez-mcp
```

### HTTP Mode (for web API access)

For accessing the MCP server via HTTP API:

```bash
# Set environment variable
export BREEZ_TRANSPORT_MODE=http

# Or add to .env file
echo "BREEZ_TRANSPORT_MODE=http" >> .env

# Run the server
python -m src.main
```

The server will be available at `http://localhost:8000/mcp`

### ASGI Mode (for external ASGI servers)

For deployment with external ASGI servers like Gunicorn:

```bash
# Set environment variable
export BREEZ_TRANSPORT_MODE=asgi

# Run with uvicorn
uvicorn src.main:app --host 0.0.0.0 --port 8000

# Or with Gunicorn (production)
gunicorn src.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

### Docker Compose

Run both modes simultaneously:

```bash
# STDIO mode
docker compose --profile stdio up -d
docker compose logs -f breez-mcp-stdio

# HTTP mode
docker compose --profile http up -d
docker compose logs -f breez-mcp-http

# Stop
docker compose --profile http down
docker compose --profile stdio down
```

### Docker (direct)

```bash
# Build image
docker build -t breez-mcp .

# STDIO mode (default)
docker run --rm \
  -e BREEZ_API_KEY="$BREEZ_API_KEY" \
  -e BREEZ_MNEMONIC="$BREEZ_MNEMONIC" \
  -v $(pwd)/data:/app/data \
  breez-mcp

# HTTP mode
docker run --rm -p 8000:8000 \
  -e BREEZ_TRANSPORT_MODE=http \
  -e BREEZ_API_KEY="$BREEZ_API_KEY" \
  -e BREEZ_MNEMONIC="$BREEZ_MNEMONIC" \
  -v $(pwd)/data:/app/data \
  breez-mcp
```

To keep STDIN/STDOUT attached for Claude Desktop, add `-i` to the `docker run` command.


## Claude Desktop Integration

### Quick install

```bash
mcp install src.main --name "breez-mcp"
```

Use `-f .env` or `-v KEY=value` to supply credentials during installation if desired.


### Docker from Claude Desktop

Ensure the image exists (`docker build -t breez-mcp .`), then configure:

```json
{
  "mcpServers": {
    "breez": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-e", "BREEZ_API_KEY",
        "-e", "BREEZ_MNEMONIC",
        "-e", "BREEZ_TRANSPORT_MODE=stdio",
        "-v", "/absolute/path/to/breez-mcp/data:/app/data",
        "breez-mcp"
      ],
      "cwd": "/absolute/path/to/breez-mcp",
      "env": {
        "BREEZ_API_KEY": "${env:BREEZ_API_KEY}",
        "BREEZ_MNEMONIC": "${env:BREEZ_MNEMONIC}",
        "BREEZ_NETWORK": "mainnet"
      }
    }
  }
}
```

Docker's `-e VAR` syntax reads the value of `VAR` from the environment supplied via the `env` block.

### uvx from Claude Desktop

```json
{
  "mcpServers": {
    "breez": {
      "command": "uvx",
      "args": ["--from", ".", "breez-mcp"],
      "cwd": "/absolute/path/to/breez-mcp",
      "env": {
        "BREEZ_API_KEY": "${env:BREEZ_API_KEY}",
        "BREEZ_MNEMONIC": "${env:BREEZ_MNEMONIC}",
      }
    }
  }
}
```

### Verification

- Restart Claude Desktop after adding the configuration.
- Run `mcp list` to ensure the server registered.
- Ask Claude prompts like “Check my wallet balance” or “Create an invoice for 1000 sats” to validate tool routing.

## Available Tools

- `get_balance` — comprehensive wallet balance with limits and formatted amounts
- `get_node_info` — detailed node information including capabilities and sync status
- `send_payment` — send a Lightning payment with complete transaction details
- `create_invoice` — generate a BOLT11 invoice with all invoice data
- `list_payments` — comprehensive payment history with full details

## Example Prompts

- "Check my wallet balance"
- "Create an invoice for 1000 sats for coffee"
- "Send payment to lnbc1…"
- "Show me my recent payments"

## HTTP API Usage (HTTP Mode)

When running in HTTP mode, you can interact with the MCP server via HTTP requests:

### Health Check
```bash
curl http://localhost:8000/health
```

### List Available Tools
```bash
curl http://localhost:8000/mcp/tools/list
```

### Call a Tool (MCP Protocol)
The HTTP mode follows the MCP protocol over HTTP. You'll need to send properly formatted MCP JSON-RPC requests to `http://localhost:8000/mcp`.

Example using MCP Inspector or other MCP clients:
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "get_balance",
    "arguments": {}
  },
  "id": 1
}
```

Send to:
```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"get_balance","arguments":{}},"id":1}'
```

## Security Notes

- Never commit `.env`; keep secrets in your shell or a secrets manager.
- Treat the mnemonic as the wallet’s private key. Rotate immediately if leaked.
- Default network is `mainnet`. For experimentation, explicitly set `BREEZ_NETWORK=testnet`.
- When using containers, mount `./data` to preserve state between runs and prevent secret leakage in container layers.

## Troubleshooting

- **Missing environment variables** — ensure `.env` exists or export the required variables before starting.
- **SDK connection failures** — verify required env vars, try `python list_payments_cli.py --limit 1 --verbose` to confirm SDK connectivity, and check `http://localhost:8000/health` in HTTP mode.
- **Claude Desktop cannot find the server** — double-check absolute paths in `cwd` and restart the application after configuration changes.
