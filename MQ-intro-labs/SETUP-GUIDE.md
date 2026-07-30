# Quick Setup Guide - IBM MQ Operations with Bob

This guide will get you up and running with the IBM MQ MCP Server and Bob in under 30 minutes.

## ✅ Pre-Flight Checklist

Before you begin, verify you have:

- [ ] IBM Bob installed and running
- [ ] Python 3.10 or higher (`python --version`)
- [ ] Podman Desktop or Docker installed
- [ ] Terminal/Command Prompt access
- [ ] Internet connection for downloading images

## 🚀 5-Step Setup Process

### Step 1: Start IBM MQ Container (5 minutes)

Open your terminal and run these commands:

```bash
# Pull the MQ image
podman pull icr.io/ibm-messaging/mq:latest

# Create storage volume
podman volume create qm1data

# Start the queue manager
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

**Verify it's running:**
```bash
podman ps
```
You should see QM1 in the list.

---

### Step 2: Install uv Package Manager (2 minutes)

**macOS/Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.cargo/env
```

**Windows (PowerShell as Administrator):**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Verify installation:**
```bash
uv --version
```

---

### Step 3: Configure MCP Server (5 minutes)

1. **Navigate to the MCP server directory:**
   ```bash
   cd LAB/mq-mcp-server-bob
   ```

2. **Install dependencies:**
   ```bash
   uv pip install httpx fastmcp "mcp[cli]"
   ```

3. **Get the absolute path to this directory:**
   
   **macOS/Linux:**
   ```bash
   pwd
   ```
   
   **Windows:**
   ```cmd
   cd
   ```
   
   Copy this path - you'll need it in the next step!

4. **Edit the configuration file:**
   
   Open `bob-mcp-config.json` in your favorite text editor and update line 7:
   
   **Before:**
   ```json
   "/FULL/PATH/TO/LAB/mq-mcp-server-bob",
   ```
   
   **After (example):**
   ```json
   "/Users/student/Desktop/mq-operations-with-bob/mq-mcp-server-bob",
   ```
   
   **Important:** Use the absolute path you copied in step 3!

5. **Save the file**

---

### Step 4: Test MCP Server (Optional - 3 minutes)

Before connecting to Bob, verify the server works:

```bash
# Test standalone
uv run mqmcpserver_bob.py
```

Press `Ctrl+C` to stop.

Or test with the interactive inspector:
```bash
uv run fastmcp dev mqmcpserver_bob.py
```

This opens a web interface where you can test the tools manually.

---

### Step 5: Connect to Bob (5 minutes)

1. **Open IBM Bob**

2. **Switch to Advanced Mode:**
   - Click the mode selector in the top-right
   - Select "🛠️ Advanced"

3. **Import the MCP Server:**
   - Click the Settings icon (⚙️)
   - Navigate to "MCP Servers"
   - Click "Import MCP Server" or "Add Server"
   - Browse to `mq-operations-with-bob/mq-mcp-server-bob/bob-mcp-config.json`
   - Click "Import" or "Open"

4. **Verify Connection:**
   - Look for a green indicator next to "mq-mcp-server-bob"
   - If red, check the logs for errors

5. **Test with Bob:**
   
   In the Bob chat, type:
   ```
   List all MQ queue managers and their status
   ```
   
   Bob should respond with information about QM1!

---

## 🎉 Success!

If Bob successfully listed your queue managers, you're ready to start the workshops!

**Next Steps:**
1. Open [WORKSHOP-mq-part1-IDE.md](./WORKSHOP-mq-part1-IDE.md)
2. Follow the exercises step by step
3. Have fun learning AI-powered MQ management!

---

## 🔧 Quick Troubleshooting

### "Cannot connect to MQ"
```bash
# Check if container is running
podman ps

# Check MQ REST API
curl -k https://localhost:9443/ibmmq/rest/v3/admin/qmgr/
```

### "Authentication failed"
- Verify credentials in `bob-mcp-config.json` are `admin`/`passw0rd`
- Restart the MQ container if needed

### "Module not found"
```bash
cd mq-operations-with-bob/mq-mcp-server-bob
uv sync
```

### "Path not found" in Bob
- Double-check the path in `bob-mcp-config.json` is absolute
- Use forward slashes `/` even on Windows
- No trailing slash at the end

### Bob shows red indicator
- Check Bob's MCP server logs in Settings
- Verify the path in config is correct
- Try restarting Bob

---

## 📞 Need More Help?

- See the full [README.md](./README.md) for detailed documentation
- Check the [Troubleshooting section](./README.md#-troubleshooting)
- Review the MCP server [README](./mq-mcp-server-bob/README.md)

---

## 🎓 Workshop Structure

Once setup is complete:

1. **Part 1** (60-90 min): AI-Ops & Dashboard Build
   - Basic MQ operations
   - Natural language management
   - Build a React dashboard

2. **Part 2** (45-60 min): Advanced Administration
   - Complex queue configurations
   - Channel management
   - Performance tuning

3. **Part 3** (45-60 min): Security & Clustering
   - SSL/TLS configuration
   - Certificate management
   - High availability setup

Total workshop time: 2.5 - 4 hours

---

**Ready to begin?** Head to [Part 1](./WORKSHOP-mq-part1-IDE.md)!