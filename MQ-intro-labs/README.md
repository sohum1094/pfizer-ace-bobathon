# IBM MQ Operations with Bob - Workshop LAB

Welcome to the **IBM MQ AI-Native Management Workshop**! This LAB contains all the materials you need to learn how to use IBM Bob with the Model Context Protocol (MCP) to manage IBM MQ using natural language.

## What's Included

This LAB folder contains:
- **mq-mcp-server-bob/** - The MCP server that connects Bob to IBM MQ
- **WORKSHOP-mq-part1-IDE.md** - Part 1: AI-Ops & Dashboard Build
- **WORKSHOP-mq-part2-IDE.md** - Part 2: Advanced MQ Administration
- **WORKSHOP-mq-part3-IDE.md** - Part 3: Security, Certificates & Clustering

## LAB Overview

In these workshops, you will:
1. Connect IBM Bob to IBM MQ via the Model Context Protocol
2. Manage MQ queue managers using natural language
3. Build a modern React dashboard for MQ monitoring
4. Perform advanced MQ administration tasks
5. Configure security and clustering

## Prerequisites

Before starting, ensure you have:

### Required Software
- **IBM Bob** (Antigravity IDE) installed
- **Python 3.11+** installed
- **uv** package manager installed
- **Podman Desktop** or **Docker** (for running MQ container)
- **Node.js 18+** (for dashboard development)

### Platform Support
- **Windows** (with WSL2 recommended)
- **Linux**
- ⚠️ **macOS** (MQ container may have limitations, better to try to use one more podman instance running on another port on another student laptop that has Windows or Linux)

## Quick Start Guide

### Step 1: Set Up IBM MQ Container

1. **Install Podman Desktop**
   - Download from: https://podman-desktop.io/

2. **Pull the IBM MQ Image**
   ```bash
   podman pull icr.io/ibm-messaging/mq:latest
   ```

3. **Create a Data Volume**
   ```bash
   podman volume create qm1data
   ```

4. **Run the Queue Manager Container**
   ```bash
   podman run \
     --env LICENSE=accept \
     --env MQ_QMGR_NAME=QM1 \
     --env MQ_APP_USER=app \
     --env MQ_APP_PASSWORD=passw0rd \
     --env MQ_ADMIN_USER=admin \
     --env MQ_ADMIN_PASSWORD=passw0rd \
     --volume qm1data:/mnt/mqm \
     --publish 1414:1414 \
     --publish 9443:9443 \
     --detach \
     --name QM1 \
     icr.io/ibm-messaging/mq:latest
   ```

5. **Verify MQ is Running**
   ```bash
   podman ps
   ```
   You should see the QM1 container running.

6. **Test MQ REST API**
   ```bash
   curl -k https://localhost:9443/ibmmq/rest/v3/admin/qmgr/
   ```
   You should receive a JSON response (authentication error is OK at this stage).

### Step 2: Install uv Package Manager

**macOS/Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

After installation, restart your terminal or run:
```bash
source $HOME/.cargo/env  # macOS/Linux
```

### Step 3: Set Up the MCP Server

1. **Navigate to the MCP Server Directory**
   ```bash
   cd LAB/mq-mcp-server-bob
   ```

2. **Install Dependencies**
   ```bash
   uv pip install httpx fastmcp "mcp[cli]"
   ```

3. **Configure Your MQ Connection**
   
   Edit the `bob-mcp-config.json` file:
   
   ```json
   {
     "mcpServers": {
       "mq-mcp-server-bob": {
         "command": "uv",
         "args": [
           "run",
           "--directory",
           "/FULL/PATH/TO/mq-operations-with-bob/mq-mcp-server-bob",
           "mqmcpserver_bob.py"
         ],
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

   **Important:** Replace `/FULL/PATH/TO/mq-operations-with-bob/mq-mcp-server-bob` with the actual absolute path to this directory.
   
   **Examples:**
   - macOS/Linux: `/Users/yourname/Desktop/MQ/mq-operations-with-bob/mq-mcp-server-bob`
   - Windows: `C:/Users/yourname/Desktop/MQ/mq-operations-with-bob/mq-mcp-server-bob`

4. **Test the MCP Server (Optional)**
   
   Test the server standalone:
   ```bash
   uv run mqmcpserver_bob.py
   ```
   
   Or use the FastMCP inspector:
   ```bash
   uv run fastmcp dev mqmcpserver_bob.py
   ```

### Step 4: Import MCP Server into Bob

1. **Open IBM Bob**

2. **Switch to Advanced Mode**
   - Click on the mode selector
   - Choose "🛠️ Advanced" mode

3. **Import the MCP Server**
   - Go to Settings → MCP Servers
   - Click "Import MCP Server"
   - Navigate to `mq-operations-with-bob/mq-mcp-server-bob/`
   - Select `bob-mcp-config.json`
   - Click "Import"

4. **Verify Connection**
   
   In Bob, type:
   ```
   List all MQ queue managers and their status
   ```
   
   Bob should respond with information about your QM1 queue manager.

### Step 5: Start the Workshops

Once your setup is complete, proceed to the workshops in order:

1. **[Part 1: AI-Ops & Dashboard Build](./WORKSHOP-mq-part1-IDE.md)**
   - Learn basic MQ operations with Bob
   - Build a modern React dashboard
   - Perform AI-powered troubleshooting

2. **[Part 2: Advanced MQ Administration](./WORKSHOP-mq-part2-IDE.md)**
   - Advanced queue management
   - Channel configuration
   - Performance tuning

3. **[Part 3: Security, Certificates & Clustering](./WORKSHOP-mq-part3-IDE.md)**
   - Security configuration
   - SSL/TLS setup
   - Clustering and high availability

## 🔧 Troubleshooting

### MQ Container Issues

**Container won't start:**
```bash
podman logs QM1
```

**Port conflicts:**
```bash
podman ps -a
podman rm -f QM1
# Then re-run the container command
```

**Reset everything:**
```bash
podman stop QM1
podman rm QM1
podman volume rm qm1data
# Then start from Step 1.3
```

### MCP Server Issues

**"Cannot connect to MQ":**
- Verify MQ is running: `podman ps`
- Test REST API: `curl -k https://localhost:9443/ibmmq/rest/v3/admin/qmgr/`
- Check firewall settings for port 9443

**"Authentication failed":**
- Verify credentials in `bob-mcp-config.json`
- Default credentials are `admin`/`passw0rd`

**"Module not found":**
```bash
cd mq-operations-with-bob/mq-mcp-server-bob
uv sync
# or
pip install -r requirements.txt
```

**Path issues in bob-mcp-config.json:**
- Use absolute paths, not relative paths
- Use forward slashes `/` even on Windows
- Verify the path exists: `ls /your/path/to/mq-operations-with-bob/mq-mcp-server-bob`

### Bob Issues

**MCP Server not showing up:**
- Restart Bob after importing
- Check Bob's MCP server logs in Settings
- Verify the path in `bob-mcp-config.json` is correct

**Tools not working:**
- Ensure you're in "Advanced" mode
- Check that the MCP server is connected (green indicator)
- Try disconnecting and reconnecting the server

## Additional Resources

- **MQ REST API Documentation:** https://www.ibm.com/docs/en/ibm-mq/9.4.x?topic=administering-administration-using-rest-api
- **Model Context Protocol:** https://modelcontextprotocol.io/
- **FastMCP Documentation:** https://github.com/jlowin/fastmcp
- **IBM Bob Documentation:** https://www.ibm.com/products/bob
- **MQ Container Tutorial:** https://developer.ibm.com/tutorials/mq-connect-app-queue-manager-containers/

## Getting Help

If you encounter issues:

1. Check the troubleshooting section above
2. Review the MCP server logs
3. Verify all prerequisites are installed
4. Ensure MQ container is running and accessible
5. Check the workshop-specific instructions

## Notes for Instructors

- Ensure students have completed all prerequisites before starting
- The default credentials (`admin`/`passw0rd`) are for lab use only
- Students should use absolute paths in configuration files
- Allow 15-20 minutes for initial setup
- Part 1 takes approximately 60-90 minutes
- Parts 2 and 3 are optional advanced topics

## Security Notice

⚠️ **Important:** The default credentials in this LAB are for educational purposes only. In production environments:
- Use strong, unique passwords
- Implement certificate-based authentication
- Follow your organization's security policies
- Never commit credentials to version control

## License

Copyright (c) 2025 IBM Corp.

Licensed under the Apache License, Version 2.0.