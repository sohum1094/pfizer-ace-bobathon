# IBM ACE + Bob — AI-Assisted Integration Labs

This repository contains hands-on lab materials for using **IBM Bob** as an AI pair-programmer while building and troubleshooting integration flows in **IBM App Connect Enterprise (ACE) 13**.

Labs are split across two days:

- **Day 1** — Setting up Bob inside the ACE 13 Toolkit and connecting the IBM ACE MCP server
- **Day 2** — AI-assisted use cases drawn from integration scenarios

---

## Day 1 — Getting Started with Bob in the ACE Toolkit

Day 1 covers the two foundational integrations you need before working through the use cases.

### Lab A — Bob Shell in the ACE 13 Toolkit

Learn how to launch and use the **IBM Bob Shell** directly inside the ACE Toolkit to generate message flows, analyse existing artifacts, and get guided assistance without leaving your IDE.

👉 See [intro-labs/Bob-Shell-ACE.md](intro-labs/Bob-Shell-ACE.md)

### Lab B — IBM ACE MCP Server in Bob IDE

Learn how to deploy a sample ACE application, configure an **MCP server** from the ACE Web UI, and connect it to Bob IDE so that Bob has live, structured access to your running integration runtime.

👉 See [intro-labs/Bob-IDE-ACE.md](intro-labs/Bob-IDE-ACE.md)

---

## Day 2 — Use Cases

Day 2 moves from setup to practice. Each lab is based on a real-world integration pattern identified and is designed to be worked through with Bob as your AI assistant.

| Lab | Scenario |
|-----|----------|
| **Starter** | Sample MQ App on MQ Container + ACE Toolkit |
| **Lab 01** | SAP Adapter Integration |
| **Lab 02** | Snowflake DB Integration |
| **Lab 03** | Reconciliation & Error Handling |
| **Lab 04** | Pub/Sub Patterns |
| **Lab 05** | Managed File Transfer (MFT) Integration |
| **Lab 06** | File-Based Integration |
| **Lab 07** | REST/SOAP API Exposure |
| **Lab 08** | Exactly-Once Processing |

Each lab comes with a set of **ready-to-paste prompts** organised into three tiers — conceptual, implementation, and troubleshooting — so you can use Bob effectively at every stage.

👉 **Go to [usecases/README.md](usecases/README.md) to browse all labs and prompts.**
