# IBM Bob Workshop - Security, Certificates & Clustering | Part 3
## Case Study: Advanced Enterprise MQ Operations

### Audience
Senior Middleware Administrators, Secure Infrastructure Engineers, and MQ Architects managing highly available and encrypted environments.

### Goal of the Workshop
Demonstrate how **IBM Bob** (IDE / Shell) can:
- Reason about and parse IBM MQ error logs dynamically via a new MCP tool.
- Assist in setting up and diagnosing SSL/TLS Keystores and Certificates.
- Guide the configuration and validation of MQ Clusters.
- Perform advanced message debugging and browse messages on queues securely.

### Bob IDE Mode
> **Required Mode:** `Agent`
>
> Ensure the MQ MCP server is running and you have access to the extended tools from Part 1.

---

## Workshop Flow Overview

1. Extending the MCP Server with File Reading Capabilities
2. AI-Powered Error Log Diagnostics (`AMQERR01.LOG`)
3. SSL/TLS Certificate Diagnostics
4. Clustering and Workload Balancing
5. Advanced Message Inspection

---

## Step A - Extend the MCP Server (Log Reader)

### Why this step?
To diagnose deep MQ issues (like cluster problems or SSL handshakes), the standard MQ REST API is often not enough. We need Bob to read the `AMQERR01.LOG`. This step teaches the audience how to add a simple Python function to `mqmcpserver.py` that allows Bob to retrieve log tails.

### Prompt
```
I need you to be able to read my MQ error logs. 
Look at the `mqmcpserver.py` file and add a new FastMCP tool called `read_mq_logs`. It should execute `podman exec QM1 tail -n 50 /var/mqm/qmgrs/QM1/errors/AMQERR01.LOG` or equivalent depending on your environment, and return the string.
```

### Expected Outcome
Bob should seamlessly rewrite the Python server code, adding the `@mcp.tool()` wrapper and instructing the user to restart the server.

Ensure that Bob edited the `.bob/mcp.json` file and not just the example `MQ-intro-labs/mq-mcp-server-bob/bob-mcp-config.json` file.

**Restart the MCP** through Bob IDE's UI by going to `Bob Settings` from the Bob side panel -> `MCP` -> Click the `Refresh icon`

---

## Step B - AI-Powered Error Log Diagnostics

### Why this step?
MQ error codes (e.g., `AMQ9999`) can be cryptic. By combining the MCP log reader with Bob's base knowledge of IBM MQ documentation, Bob can translate raw errors into human-readable action plans.

### Prompt
```
I suspect there is an issue with my recent changes. 
Please read the latest MQ error logs using your new tool. Translate any `AMQ` error codes you find into simple English and tell me the recommended remediation step.
```

### Expected Outcome
Bob discovers errors in the log, cross-references them with its trained knowledge of IBM MQ, and produces a highly-accurate summary without the user having to Google the error code.

---

## Step C - SSL/TLS Certificate Diagnostics

### Why this step?
Certificate expiration and mismatched CipherSpecs are the biggest cause of MQ outages. While we won't provision real certs in this lab, we will ask Bob to validate the current Keystore configuration.

### Prompt
```
We need to audit our SSL configuration on QM1. 
Can you verify what the `SSLKEYR` (Key Repository) attribute is currently set to on the Queue Manager? 
After that, explain what steps I would take next if I needed to apply a new certificate matching the label 'ibmwebspheremqqm1'.
```

### Expected Outcome
Bob will execute a `DISPLAY QMGR SSLKEYR` command using the `runmqsc` tool. It will interpret the response and then provide the exact `runmqsc` commands (e.g., `ALTER QMGR SSLKEYR...` and `REFRESH SECURITY TYPE(SSL)`) required to rotate certificates.

---

## Step D - Clustering and Workload Balancing

### Why this step?
MQ Clusters are notoriously complex to set up manually, requiring precise naming conventions for Cluster Sender and Cluster Receiver channels. Bob can be instructed to generate or validate a cluster topology.

### Prompt
```
I am planning to expand QM1 into a new cluster named 'EU.CLUSTER'. 
Please define a Cluster Receiver channel named 'TO.QM1.EU' specifically designed for this cluster on QM1.
What else do I need to do to allow another Queue Manager (QM2) to join this cluster?
```

### Expected Outcome
Bob executes `DEFINE CHANNEL('TO.QM1.EU') CHLTYPE(CLUSRCVR) CLUSTER('EU.CLUSTER') CONNAME('localhost(1414)')`. Then, it generates the architectural steps for adding `QM2`.

---

## Step E - Advanced Message Inspection

### Why this step?
Developers often ask admins: *"Is my message on the queue?"* Browsing queues without consuming the messages can be difficult. This step explores Bob's ability to browse message headers if an advanced REST tool is available.

### Prompt
```
Developers claim they sent messages to 'PAYMENT.IN.QL' but they aren't processing.
Assuming we have message browse capabilities via the REST API, how would you check if there are poison messages stuck at the top of the queue?
```

### Expected Outcome
Bob will discuss the REST API strategy for reading message headers, specifically identifying `BackoutCount`, avoiding destructive `GET` operations, and potentially suggesting the setup of a Dead Letter Queue handler rule.

---

## Next Steps
Congratulations! You've mastered Advanced Enterprise MQ Operations using AI. You can apply these concepts to write custom MCP servers for your organizations specific CI/CD pipelines!
