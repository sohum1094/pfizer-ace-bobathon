# IBM Bob Workshop - Advanced MQ Administration | Part 2
## Case Study: Day-2 Operations and Configuration

### Audience
Middleware administrators, Site Reliability Engineers (SREs), and MQ Specialists looking to automate large-scale administration using generative AI.

### Goal of the Workshop
Demonstrate how **IBM Bob* (IDE / Shell) can:
- Perform complex IBM MQ administrative tasks using conversational language
- Execute multi-step object provisioning (Queues, Topics, Channels)
- Interpret and configure MQ Security (CHLAUTH rules)
- Rapidly troubleshoot queue depth issues

We use a local **IBM MQ Queue Manager (QM1)** running in a Podman container, alongside the open-source **IBM MQ MCP Server**.

### Bob IDE Mode
> **Required Mode:** `Code`
>
> Ensure the MQ MCP server is actively running in the background and connected to QM1.

---

## Workshop Flow Overview

1. Provisioning a New Application Environment
2. Pub/Sub Topology Setup
3. Operational Troubleshooting and Remediation
4. Security and Access Control (CHLAUTH)
5. Environment Cleanup and Decommissioning

Each step tackles a specific sub-domain of MQ Administration, ranging from developer onboarding to strict security compliance.

---

## Lab Environment

The following prerequisite components are used in this lab:
- **IBM MQ Container**: Running via Podman (`QM1`). *(See `README.md` for exact container launch commands).*
- **IBM MQ MCP Server**: A customized Python FastMCP application connected via the MQ REST API on port `9443`.

---

## Step A - Provision a New Application Environment

### Why this step?
Application teams frequently request new environments. Instead of handcrafting MQSC scripts, administrators can describe the requirements to Bob, who will generate and execute the provisioning steps.

### Prompt
```
Can you provision a new environment for the 'PaymentGateway' application on QM1? 
They need:
1. A local queue named 'PAYMENT.IN.QL' with a max depth of 100000.
2. A local queue named 'PAYMENT.OUT.QL'.
3. A dead letter queue named 'PAYMENT.DLQ'.
4. A server connection channel named 'PAYMENT.APP.SVRCONN'.
Please execute this for me.
```

### Expected Outcome
Bob should:
- Issue multiple `DEFINE` commands.
- For example: `DEFINE QLOCAL('PAYMENT.IN.QL') MAXDEPTH(100000)`.
- Confirm each object was created successfully.

---

## Step B - Pub/Sub Topology Setup

### Why this step?
Configuring Topics and Administrative Subscriptions requires precise syntax. Bob simplifies this by understanding the conceptual pub/sub relationship and abstracting the complexity.

### Prompt
```
Set up a pub/sub architecture for transactions on QM1.
First, define a topic object named 'TRANSACTIONS.TOPIC' with the topic string 'payments/transactions'. 
Then, create an administrative subscription named 'ANALYTICS.SUB' that forwards all messages from this topic into a new local queue called 'ANALYTICS.DATA.QL'.
Execute these commands via the MCP server.
```

### Expected Outcome
Bob should:
- Issue a `DEFINE TOPIC('TRANSACTIONS.TOPIC') TOPICSTR('payments/transactions')`.
- Issue a `DEFINE QLOCAL('ANALYTICS.DATA.QL')`.
- Issue a `DEFINE SUB('ANALYTICS.SUB') DEST('ANALYTICS.DATA.QL') TOPICOBJ('TRANSACTIONS.TOPIC')`.

---

## Step C - Operational Troubleshooting and Remediation

### Why this step?
When applications fail to process messages, queues fill up triggering Depth High events. Bob can dynamically query queues and alter parameters to restore service while a root cause is found.

### Prompt
```
A developer reports their payment batches are failing, possibly hitting queue depth limits. 
Can you check the current MAXDEPTH and CURDEPTH for 'PAYMENT.IN.QL' on QM1? 
If MAXDEPTH is less than 500000, please alter it to 500000 dynamically to handle the volume spike.
```

### Expected Outcome
Bob should:
- Display the queue attributes using `DISPLAY QLOCAL('PAYMENT.IN.QL') CURDEPTH MAXDEPTH`.
- Reason about the current `MAXDEPTH` value.
- Execute the remediation: `ALTER QLOCAL('PAYMENT.IN.QL') MAXDEPTH(500000)`.

---

## Step D - Security and Access Control (CHLAUTH)

### Why this step?
Implementing MQ Security can be daunting. Channel Authentication (CHLAUTH) records must be configured cautiously to prevent unauthorized access. Bob understands security best practices and can lock down channels based on conversational rules.

### Prompt
```
As per our security policy, we need to lock down the 'PAYMENT.APP.SVRCONN' channel on QM1. 
First, create a CHLAUTH rule to block all IP addresses (ADDRESS('*') USERSRC(NOACCESS)). 
Then, add an overriding CHLAUTH rule to allow connections exclusively from the IP address '192.168.1.100' using the user 'app'.
```

### Expected Outcome
Bob should:
- Issue `SET CHLAUTH('PAYMENT.APP.SVRCONN') TYPE(ADDRESSMAP) ADDRESS('*') USERSRC(NOACCESS) ACTION(REPLACE)`.
- Issue `SET CHLAUTH('PAYMENT.APP.SVRCONN') TYPE(ADDRESSMAP) ADDRESS('192.168.1.100') USERSRC(MAP) MCAUSER('app') ACTION(REPLACE)`.
- Re-verify that the security rules are applied.

---

## Step E - Environment Cleanup and Decommissioning

### Why this step?
Leaving unused objects creates clutter and potential security vulnerabilities. Bob can search for objects by pattern and safely delete them upon confirmation.

### Prompt
```
We are migrating to a centralized Dead Letter Queue. 
Please list all queues on QM1 that start with 'PAYMENT.'. 
After listing them, please delete only the queue named 'PAYMENT.DLQ'.
```

### Expected Outcome
Bob should:
- Issue `DISPLAY QLOCAL('PAYMENT.*')`.
- Confirm the matching queues available on the system.
- Explicitly execute `DELETE QLOCAL('PAYMENT.DLQ')` and confirm the successful deletion.

---

## Expected Outcome Summary

By the end of this lab, you should have a firm grasp of how:
1. Bob translates high-level engineering intents into precise MQSC syntax.
2. Bob executes multi-step transactional logic against MQ without writing scripts.
3. Complex Pub/Sub and CHLAUTH deployments become trivial.
4. Intelligent reasoning allows Bob to check parameters before modifying them automatically.

## Next Steps
You've completed the MQ AI-Ops Workshop! Feel free to extend these scenarios to include clusters, dead-letter rule generation, or SSL/TLS certificate keystore validation.
