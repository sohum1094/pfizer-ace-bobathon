# Quick Start Guide - MQ MCP Server for Bob

Get up and running with the IBM MQ MCP Server in Bob in just a few minutes!

## Prerequisites Checklist

- [ ] IBM WebSphere MQ running (container or local installation)
- [ ] Python 3.10+ installed
- [ ] IBM Bob installed
- [ ] `uv` package manager installed

## 5-Minute Setup

### Step 1: Install uv (if needed)

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### Step 2: Install Dependencies

```bash
cd mq-mcp-server-bob
uv pip install httpx fastmcp "mcp[cli]"
```

### Step 3: Configure Your MQ Connection

Edit `bob-mcp-config.json` and update these values:

1. **Update the script path** (line 7):
   ```json
   "args": ["run", "/full/path/to/mq-mcp-server-bob/mqmcpserver_bob.py"]
   ```
   Replace with your actual absolute path, for example:
   - macOS/Linux: `"/Users/yourname/Desktop/MQ/mq-mcp-server-bob/mqmcpserver_bob.py"`
   - Windows: `"C:/Users/yourname/Desktop/MQ/mq-mcp-server-bob/mqmcpserver_bob.py"`

2. **Update MQ credentials** (env section):
   ```json
   "env": {
     "MQ_HOST": "localhost",      // Your MQ host
     "MQ_PORT": "9443",           // Your MQ REST API port
     "MQ_USER": "admin",          // Your MQ username
     "MQ_PASSWORD": "passw0rd"    // Your MQ password
   }
   ```

### Step 4: Import into Bob

**Option A: Using Bob UI**
1. Open Bob
2. Switch to **Advance Mode**
3. Go to Settings → MCP Servers
4. Click "Import MCP Server"
5. Select `bob-mcp-config.json`
6. Click "Import"

**Option B: Using Bob CLI**
```bash
bob mcp import bob-mcp-config.json
```

### Step 5: Test It!

In Bob, try:
```
List all MQ queue managers
```

## Common Issues

### "Cannot connect to MQ"
- Check if MQ is running: `podman ps` or `docker ps`
- Verify REST API: `curl -k https://localhost:9443/ibmmq/rest/v3/admin/qmgr/`

### "Authentication failed"
- Double-check username and password in `bob-mcp-config.json`
- Ensure user has MQWebAdmin or MQWebUser role

### "Module not found"
- Run: `uv sync` or `pip install -r requirements.txt`

## Next Steps

Once working, try these Bob prompts:

1. **List queues:**
   ```
   Show me all local queues on QM1
   ```

2. **Check queue depth:**
   ```
   Display queue depth for all queues on QM1
   ```

3. **Create a queue:**
   ```
   Create a local queue called MY.NEW.QUEUE on QM1
   ```

4. **Display channels:**
   ```
   Show all channels on QM1
   ```

## Need Help?

See the full [README.md](README.md) for detailed documentation and troubleshooting.