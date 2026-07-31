# IBM Bob Workshop - MQ AI-Ops & Dashboard Build | Part 1
## Case Study: IBM MQ AI-Native Management

### Audience
Middleware administrators, Site Reliability Engineers (SREs), and full-stack developers integrating IBM MQ with generative AI workflows.

### Goal of the Workshop
Demonstrate how **IBM Bob** (IDE/ Shell) can:
- Connect securely to an IBM MQ instance via the Model Context Protocol (MCP)
- Understand MQ environments through AI-powered discovery
- Act as an intelligent SRE for natural language troubleshooting
- Generate a modern, premium React-based dashboard for real-time monitoring

We use a local **IBM MQ Queue Manager (QM1)** running in a Podman container, alongside the open-source **IBM MQ MCP Server**.

### Bob IDE Mode
> **Required Mode:** `Agent`
>
> Ensure you have an environment capable of running Node.js and Python for the dashboard and MCP server components.

---

## Workshop Flow Overview

1. Validate the MQ MCP Server connection
2. AI-Powered MQ Discovery and Health Checks
3. Natural Language Troubleshooting
4. Build a Modern MQ Operations Dashboard
5. Test the Dashboard Integration

Each step builds upon the previous one to transition from basic CLI operations to a fully-featured, AI-generated modern application.

---

## Lab Environment

The following prerequisite components are used in this lab:
- **IBM MQ Container**: Running via Podman (`QM1`) exposing ports `1414` and `9443`. *(See `README.md` for exact container launch commands).*
- **IBM MQ MCP Server**: A Python FastMCP application translating LLM tool calls into MQ REST API instructions.
- **Vite React Environment**: For the web dashboard execution.

---

## Step A - Validate MCP Connection & AI Discovery

### Why this step?
Before attempting complex management tasks or building UI dashboards, we must ensure that the AI agent can successfully context-switch into the MQ environment, understand its topology, and execute read-only queries.

### Prompt
```
Can you check the current status of my MQ environment? 
Please list all available queue managers, check if they are running, and show me the ports they are listening on. Start by seeing what tools you have available via the MCP server.
```

### Expected Outcome
Bob should:
- Call the `dspmq` MCP tool or equivalent.
- Parse the JSON response.
- Provide a human-readable summary stating that QM1 is `Running`.

---

## Step B - Natural Language Queue Creation

### Why this step?
Administrators typically write procedural `runmqsc` scripts. This step demonstrates Bob's ability to abstract syntax away, allowing administrators to declare their intent using conversational language while Bob handles the implementation details.

### Prompt
```
I need to create a new local queue for the data engineering team. 
Please create a queue named 'DATA.SCADA.INBOUND.QL' on QM1 with a max depth of 10000. 
Verify that the queue was created successfully.
```

### Expected Outcome
Bob should:
- Formulate the correct MQSC command (`DEFINE QLOCAL('DATA.SCADA.INBOUND.QL') MAXDEPTH(10000)`).
- Execute it using the `runmqsc` MCP tool.
- Confirm success to the user based on the REST API response.

---

## Step C - Intelligent Troubleshooting

### Why this step?
SREs spend significant time diagnosing outages. Bob can dramatically reduce Mean Time To Resolution (MTTR) by interpreting failure states and recommending or executing fixes.

### Setup (Run in terminal)
> Stop the Queue Manager to simulate an outage:
 ```sh 
 podman stop QM1
 ```

### Prompt
```
My application team is reporting that they cannot connect to QM1. 
Can you investigate the issue, check the queue manager status, and if it's down, give me the command to start it back up?
```

### Expected Outcome
Bob should:
- Attempt to check the status using the MCP server.
- Discover that the REST API or QM is unreachable (or in a stopped state).
- Recommend running `podman start QM1` or `strmq` depending on the exact container setup.

*(Note: Don't forget to restart it with `podman start QM1` before continuing!)*

---

## Step D - Generate a Premium MQ Operations Dashboard

### Why this step?
Modern environments demand modern observability. This step showcases Bob's ability to act as a Full-Stack Engineer, writing a React application from scratch that interfaces with the MQ infrastructure.

### Prompt
```
I want to build a modern Web Dashboard to monitor my MQ queues.
Using React, Vite, and tailwind/custom CSS, build a premium "IBM MQ AI-Ops" dashboard.
Requirements:
1. Glassmorphism styling with a dark, premium aesthetic (indigo and slate color palette).
2. Display the Queue Manager status prominently (online/offline indicator).
3. Create a list or grid of Queues showing their current depth vs max depth with a visual progress bar.
4. Add a chat module on the side labeled "Digital AI SRE" where a user could supposedly chat with you.
Create the full frontend application in the 'MQ-intro-labs/dashboard' folder.
```

### Expected Outcome
Bob should:
- Generate the Vite project scaffolding.
- Write a sophisticated `App.jsx` using `lucide-react` and `framer-motion`.
- Provide a `index.css` file with custom animations and glassmorphism tokens.
- Give you instructions on how to start it (`npm install && npm run dev`).

---

## Step E - Test the Dashboard

### Why this step?
Verify the generated application works properly and looks exactly as requested by running the local development server.

### Prompt
```
Please start the development server for the MQ Dashboard. 
Once running, tell me the URL so I can check it out in my browser.
```

### Expected Outcome
Bob should run the standard npm scripts and output the `localhost` link. The UI should display a visually stunning representation of the MQ environment.

---

## Expected Outcome Summary

By the end of this lab, you should have:
1. Validated the IBM MQ MCP Server integration.
2. Successfully managed MQ Objects using natural language.
3. Rapidly diagnosed a simulated outage.
4. Generated and deployed a state-of-the-art Web Application for MQ Observability.

## Next Steps
After completing this lab, proceed to:
- **Part 2**: Advanced MQ Administration and Configuration via AI.
