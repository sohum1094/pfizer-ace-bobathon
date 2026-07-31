# IBM MQ Operations with Bob — Workshop

Welcome to the **IBM MQ AI-Native Management Workshop**! In these labs you will use IBM Bob with the Model Context Protocol (MCP) to manage IBM MQ using natural language.

## What's Included

| File / Folder | Purpose |
|---|---|
| `mq-mcp-server-bob/` | The MCP server that connects Bob to IBM MQ |
| `WORKSHOP-mq-part1-IDE.md` | Part 1: AI-Ops & Dashboard Build |
| `WORKSHOP-mq-part2-IDE.md` | Part 2: Advanced MQ Administration |
| `WORKSHOP-mq-part3-IDE.md` | Part 3: Security, Certificates & Clustering |

## What You Will Learn

1. Connect IBM Bob to IBM MQ via the Model Context Protocol
2. Manage MQ queue managers using natural language
3. Build a modern React dashboard for MQ monitoring
4. Perform advanced MQ administration tasks
5. Configure security and clustering

---

## Prerequisites

Make sure you have the following installed before starting:

| Requirement | Notes |
|---|---|
| **IBM Bob** | Bob IDE |
| **Python 3.10+** | Verify: `python --version` |
| **uv** package manager | Installed in setup step below |
| **Podman Desktop** or **Docker** | For running the MQ container |
| **Node.js 18+** | Required for Part 1 dashboard |

### Platform Support

| Platform | Support |
|---|---|
| Linux | ✅ Full support |
| Windows (WSL2 recommended) | ✅ Full support |
| macOS Apple Silicon (M1/M2/M3/M4) | ✅ Supported via x86_64 emulation — see setup guide |

---

## Step 1: Set Up the MCP Server

Before starting the workshops, you need to configure the MQ MCP Server and connect it to Bob.

> **👉 Follow the full setup guide here: [mq-mcp-server-bob/README.md](./mq-mcp-server-bob/README.md)**

The setup guide will walk you through:
- Starting an IBM MQ container (all platforms including macOS Apple Silicon)
- Installing dependencies
- Configuring and importing the MCP server into Bob
- Verifying everything works

Once you see `QM1` returned with status `Running` in Bob, come back here and continue to Step 2.

---

## Step 2: Start the Workshops

Work through the parts in order:

### [Part 1: AI-Ops & Dashboard Build](./WORKSHOP-mq-part1-IDE.md) 
- Basic MQ operations with Bob using natural language
- Build a modern React monitoring dashboard
- AI-powered troubleshooting

### [Part 2: Advanced MQ Administration](./WORKSHOP-mq-part2-IDE.md) 
- Advanced queue and channel management
- Performance tuning

### [Part 3: Security, Certificates & Clustering](./WORKSHOP-mq-part3-IDE.md) 
- SSL/TLS and certificate setup
- High availability and clustering

---

## Troubleshooting

### MQ container won't start
```bash
podman logs QM1
```

### Port conflict / reset everything
```bash
podman stop QM1 && podman rm QM1 && podman volume rm qm1data
# Then re-run the container command from the setup guide
```

### MCP server issues
See the [MCP server troubleshooting section](./mq-mcp-server-bob/README.md#troubleshooting) in the setup guide.

### Bob — MCP server not showing up
- Restart Bob after importing
- Check Settings → MCP Servers for a red/green indicator
- Verify the path in `bob-mcp-config.json` is an absolute path

### Bob — tools not working
- Ensure you are in **Agent Mode**
- Check the MCP server shows a green connected indicator
- Try disconnecting and reconnecting the server in Settings

---

## Notes for Instructors

- Allow **15–20 minutes** for initial setup before starting Part 1
- Part 1: ~60–90 min · Parts 2 & 3: optional advanced topics (~45–60 min each)
- Default credentials (`admin`/`passw0rd`) are for lab use only — remind students not to use these in production
- Students must use **absolute paths** in `bob-mcp-config.json`

---

## Additional Resources

- [IBM MQ REST API Documentation](https://www.ibm.com/docs/en/ibm-mq/9.4.x?topic=administering-administration-using-rest-api)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [FastMCP Documentation](https://github.com/jlowin/fastmcp)
- [MQ Container Tutorial](https://developer.ibm.com/tutorials/mq-connect-app-queue-manager-containers/)

---

## Security Notice

⚠️ The default credentials in this lab are for educational purposes only. In production:
- Use strong, unique passwords
- Implement certificate-based authentication
- Follow your organisation's security policies
- Never commit credentials to version control

---

## License

Copyright (c) 2025 IBM Corp. Licensed under the [Apache License, Version 2.0](https://www.apache.org/licenses/LICENSE-2.0).
