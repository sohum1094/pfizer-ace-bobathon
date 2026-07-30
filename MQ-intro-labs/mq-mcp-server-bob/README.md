# IBM MQ MCP Server for Bob

This is a Bob-compatible version of the IBM MQ MCP Server that uses the `stdio` transport protocol, making it easy to import and use within IBM Bob.

## Overview

The MQ MCP Server exposes IBM WebSphere MQ administrative operations through the Model Context Protocol (MCP), allowing Bob to interact with MQ queue managers using natural language.

### Available Tools

1. **dspmq** - List all queue managers and their running status
2. **get_status** - Get MQ status as JSON for dashboards and monitoring
3. **runmqsc** - Execute MQSC commands against a specific queue manager

## Prerequisites

- Python 3.10 or higher
- IBM WebSphere MQ with mqweb server running
- Access to MQ REST API (default port 9443)
- `uv` package manager (recommended) or `pip`

## Installation

### Step 1: Install uv (if not already installed)

**macOS/Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows:**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### Step 2: Navigate to the server directory

```bash
cd mq-mcp-server-bob
```

### Step 3: Install dependencies

```bash
uv pip install httpx fastmcp "mcp[cli]"
```

Or using pip:
```bash
pip install -r requirements.txt
```

## Configuration

The server uses environment variables for configuration:

- `MQ_HOST` - MQ server hostname (default: `localhost`)
- `MQ_PORT` - MQ REST API port (default: `9443`)
- `MQ_USER` - MQ admin username (default: `admin`)
- `MQ_PASSWORD` - MQ admin password (default: `passw0rd`)

### Configuration Options

#### Option 1: Using bob-mcp-config.json (Recommended for Bob)

Edit the `bob-mcp-config.json` file to set your MQ connection details:

```json
{
  "mcpServers": {
    "mq-mcp-server-bob": {
      "command": "uv",
      "args": ["run", "/full/path/to/mq-mcp-server-bob/mqmcpserver_bob.py"],
      "env": {
        "MQ_HOST": "localhost",
        "MQ_PORT": "9443",
        "MQ_USER": "admin",
        "MQ_PASSWORD": "passw0rd"
      }
    }
  }
}
```

**Important:** Replace `/full/path/to/mq-mcp-server-bob/` with the actual absolute path to your `mq-mcp-server-bob` directory.

#### Option 2: Using environment variables

**Local MQ (localhost):**
```bash
uv run mqmcpserver_bob.py
```

**Remote MQ:**
```bash
MQ_HOST=10.0.0.12 MQ_PASSWORD=your_password uv run mqmcpserver_bob.py
```

## Importing into Bob

### Method 1: Using Bob's MCP Import Feature

1. **Edit the configuration file first:**
   - Open `bob-mcp-config.json`
   - Update the path in the `args` array to the absolute path of `mqmcpserver_bob.py`
   - Example: `"/Users/coredump/Desktop/MQ/mq-mcp-server-bob/mqmcpserver_bob.py"`
   - Update MQ credentials in the `env` section if needed

2. **Import into Bob:**
   - Open Bob
   - Switch to **Advance Mode** (if not already in it)
   - Go to MCP Server settings
   - Click "Import MCP Server"
   - Navigate to the `mq-mcp-server-bob` directory
   - Select the `bob-mcp-config.json` file
   - Bob will automatically configure and connect to the MQ MCP Server

### Method 2: Manual Configuration in Bob

1. Open Bob's MCP configuration
2. Add a new MCP server with these settings:
   - **Name:** `mq-mcp-server-bob`
   - **Command:** `uv`
   - **Args:** `["run", "mqmcpserver_bob.py"]`
   - **Working Directory:** Path to `mq-mcp-server-bob` folder
   - **Environment Variables:**
     - `MQ_HOST`: Your MQ host
     - `MQ_PORT`: Your MQ port (usually 9443)
     - `MQ_USER`: Your MQ username
     - `MQ_PASSWORD`: Your MQ password

### Method 3: Using Bob's Settings File

Add the following to Bob's MCP configuration file (usually in `~/.bob/mcp-servers.json` or similar):

```json
{
  "mq-mcp-server-bob": {
    "command": "uv",
    "args": ["run", "/full/path/to/mq-mcp-server-bob/mqmcpserver_bob.py"],
    "env": {
      "MQ_HOST": "localhost",
      "MQ_PORT": "9443",
      "MQ_USER": "admin",
      "MQ_PASSWORD": "passw0rd"
    }
  }
}
```

## Testing the Server

### Test 1: Standalone Test

Run the server directly to verify it starts correctly:

```bash
uv run mqmcpserver_bob.py
```

The server should start and wait for stdio input from Bob.

### Test 2: Using FastMCP Inspector

Test the tools interactively without Bob:

```bash
uv run fastmcp dev mqmcpserver_bob.py
```

This opens a web interface where you can manually test the `dspmq`, `get_status`, and `runmqsc` tools.

### Test 3: Test with Bob

Once imported into Bob, try these prompts:

1. **List queue managers:**
   ```
   List all MQ queue managers and their status
   ```

2. **Get detailed status:**
   ```
   Get the current MQ status as JSON
   ```

3. **Run MQSC command:**
   ```
   Display all local queues on queue manager QM1
   ```

## Usage Examples with Bob

### Example 1: Check Queue Manager Status
```
Bob, can you check if my MQ queue managers are running?
```

### Example 2: Display Queue Information
```
Bob, show me all local queues on QM1
```

### Example 3: Create a New Queue
```
Bob, create a local queue called MY.TEST.QUEUE on QM1
```

### Example 4: Display Channel Status
```
Bob, display all channels on queue manager QM1
```

## Differences from Original MQ MCP Server

This Bob-compatible version has the following changes:

1. **Transport Protocol:** Uses `stdio` instead of `streamable-http` for Bob compatibility
2. **Enhanced Error Handling:** Better error messages and logging
3. **Improved Documentation:** More detailed docstrings for each tool
4. **Bob Configuration:** Includes ready-to-use configuration files
5. **Security:** Uses JSON encoding for MQSC commands instead of string concatenation

## Troubleshooting

### Connection Issues

If Bob cannot connect to the MQ server:

1. Verify MQ is running: `podman ps` (if using container)
2. Check MQ REST API is accessible: `curl -k https://localhost:9443/ibmmq/rest/v3/admin/qmgr/`
3. Verify credentials in the configuration
4. Check firewall settings for port 9443

### Permission Issues

If you get authentication errors:

1. Ensure the MQ user has appropriate permissions
2. For testing, use a user in the `MQWebAdmin` role
3. Check MQ security settings in `mqwebuser.xml`

### Server Not Starting

If the server fails to start:

1. Verify Python version: `python --version` (should be 3.10+)
2. Reinstall dependencies: `uv sync` or `pip install -r requirements.txt`
3. Check for port conflicts
4. Review logs for specific error messages

## Security Considerations

⚠️ **Important Security Notes:**

- The default credentials (`admin`/`passw0rd`) are for testing only
- Always use strong passwords in production
- Consider using certificate-based authentication
- Restrict MQ user permissions to minimum required
- Use HTTPS/TLS for MQ REST API connections
- Store credentials securely (use environment variables or secrets management)

## Support and Documentation

- **MQ REST API Documentation:** [IBM MQ REST API](https://www.ibm.com/docs/en/ibm-mq/9.4.x?topic=administering-administration-using-rest-api)
- **MCP Protocol:** [Model Context Protocol](https://modelcontextprotocol.io/)
- **FastMCP Documentation:** [FastMCP GitHub](https://github.com/jlowin/fastmcp)
- **IBM Bob:** [IBM Bob Product Page](https://www.ibm.com/products/bob)

## License

Copyright (c) 2025 IBM Corp.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.