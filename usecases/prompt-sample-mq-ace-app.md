# Prompts — Sample IBM MQ Application on MQ Container + ACE Toolkit

> Copy any prompt below and paste it into your AI assistant.
> Replace values in `<angle brackets>` with your own details.

---

## 🔵 Conceptual Prompts

### C1 — Understanding the MQ Container + ACE Toolkit Architecture

```
I am building a sample IBM MQ application that runs on an IBM MQ container
and is developed using the IBM ACE (App Connect Enterprise) Toolkit.

Explain the overall architecture:
- What the IBM MQ container image is and how it differs from a traditional
  MQ installation (ibm-mqadvanced-server-dev Docker image, license, defaults)
- What the IBM ACE Toolkit is, how it relates to the ACE integration server,
  and how a flow developed in the Toolkit gets deployed to a running ACE server
- How ACE connects to MQ: the MQ policy, server.conf.yaml, and the MQInput /
  MQOutput nodes
- How the three components (MQ container, ACE integration server, ACE Toolkit)
  interact during development, testing, and production
Keep the explanation beginner-friendly with a diagram described in ASCII art.
```

---

### C2 — IBM MQ Key Concepts for a Starter Application

```
I am new to IBM MQ. Before building a sample application, explain these
key concepts in plain language:
- Queue Manager: what it is and why it is the central broker
- Local Queue: where messages are stored, difference between persistent and
  non-persistent messages
- Channel: the connection path between a client (ACE) and the queue manager,
  and the role of SVRCONN vs CLNTCONN
- MQ Message: structure (MQMD descriptor + body), and what persistence,
  priority, and expiry mean
- Dead Letter Queue (DLQ): why it exists and what happens when a message
  cannot be delivered
Use a simple "order submission" analogy throughout.
```

---

### C3 — ACE Toolkit Flow Types for MQ

```
In IBM ACE Toolkit, explain the different message flow node types commonly
used for IBM MQ integration:
- MQInput node: how it reads messages from a queue, transaction modes,
  and how to configure the queue name and connection policy
- MQOutput node: how it writes messages to a queue or topic, and the
  Destination mode options (fixed queue, list of queues, topic)
- MQGet node: how it differs from MQInput (pull vs event-driven)
- Compute node (ESQL): how it transforms the message between input and output

Also explain the concept of a subflow and when you would use one in a
real-world MQ integration.
```

---

## 🟡 Implementation Prompts

### I1 — Run IBM MQ Container Locally

```
Generate the complete Docker commands to run an IBM MQ developer container
locally for a sample lab. Requirements:
- Use the official image: icr.io/ibm-messaging/mq:latest
- Queue manager name: MQLAB
- MQ admin password: passw0rd
- App password: passw0rd
- Expose ports: 1414 (MQ listener) and 9443 (MQ Console)
- Named volume: qm_data mapped to /mnt/mqm

Also show:
1. How to verify the container is running (docker ps, docker logs)
2. How to open the MQ Web Console URL and log in
3. How to exec into the container and run runmqsc to confirm the
   queue manager is active (DISPLAY QMGR)
```

---

### I2 — MQSC Setup for Sample Application Queues

```
Write the MQSC script to set up IBM MQ objects for a simple order-processing
sample application on queue manager MQLAB. I need:

Queues:
- APP.ORDERS.IN      — inbound orders, persistent, MAXDEPTH 100000
- APP.ORDERS.OUT     — processed orders output, persistent, MAXDEPTH 100000
- APP.ORDERS.DLQ     — dead letter queue for failed messages, MAXDEPTH 50000
- APP.ORDERS.AUDIT   — audit trail queue, non-persistent, MAXDEPTH 50000

Dead letter handling:
- Set BOTHRESH(3) and BOQNAME(APP.ORDERS.DLQ) on APP.ORDERS.IN
- Set the queue manager DLQ to APP.ORDERS.DLQ

Channel and authentication:
- Server-connection channel: ACE.SVRCONN, no SSL for dev, MCAUSER 'app'
- CHLAUTH rule to allow the ACE service user

Also show how to run this script inside the container using:
  docker exec -i <container_name> runmqsc MQLAB < setup.mqsc
```

---

### I3 — ACE MQ Policy and server.conf.yaml

```
Generate the IBM ACE 13 configuration files needed to connect an ACE
integration server to the MQ container from prompts I1 and I2.

1. MQEndpoint policy XML (MQPolicy.policyxml) with:
   - Policy name: MQ_LOCAL
   - Queue manager: MQLAB
   - Host: localhost (or the Docker container hostname)
   - Port: 1414
   - Channel: ACE.SVRCONN
   - Credentials: username 'app', password stored via mqsisetdbparms

2. server.conf.yaml additions for:
   - Default policy project pointing to the policy folder
   - Tracing level for MQ connections (Statistics, Accounting)

3. The mqsisetdbparms command to store the MQ app password securely.

4. The mqsideploy or ibmint deploy command to deploy a BAR file to the
   integration server.
```

---

### I4 — ACE Toolkit: Build a Simple Order Processing Flow

```
Describe step-by-step how to build a simple IBM ACE order-processing
message flow in the IBM ACE Toolkit (GUI). The flow should:
- Read a JSON order message from APP.ORDERS.IN
- Validate that the required fields (orderId, customerId, product, quantity)
  are present
- Transform the message: add a processedAt timestamp and an orderStatus of
  'ACCEPTED' or 'REJECTED' based on quantity > 0
- Write the transformed message to APP.ORDERS.OUT
- On validation failure, route to APP.ORDERS.DLQ with an error reason field

Cover:
- Which project type to create (Application vs Integration Service)
- Which nodes to add and in what order (MQInput → Compute → MQOutput)
- How to set the MQ policy on MQInput and MQOutput nodes
- How to create a Compute node and open the ESQL editor
- How to deploy the flow as a BAR file to a local integration server
```

---

### I5 — ESQL for Order Processing Compute Node

```
Write the complete ESQL compute module OrderProcessor for the IBM ACE
order-processing flow described in I4. Requirements:

1. Parse the inbound JSON from InputRoot.JSON.Data
2. Validate: orderId, customerId, product must be non-empty strings;
   quantity must be an integer > 0
3. On validation failure:
   - Set OutputRoot.JSON.Data.orderId, .errorReason, .orderStatus = 'REJECTED'
   - Set OutputRoot.JSON.Data.processedAt to current ISO 8601 timestamp
   - PROPAGATE to 'failure' terminal (routes to APP.ORDERS.DLQ)
   - RETURN FALSE
4. On success:
   - Copy all input fields to OutputRoot.JSON.Data
   - Add orderStatus = 'ACCEPTED'
   - Add processedAt = current ISO 8601 timestamp
   - Add a generated confirmationId (combine orderId + timestamp)
   - PROPAGATE to 'out' terminal (routes to APP.ORDERS.OUT)
   - RETURN FALSE

Use correct ACE 13 ESQL syntax with inline comments explaining each step.
Also show how to reference the MQ_LOCAL policy in the MQInput node using
the policyProject() function in ESQL if needed.
```

---

### I6 — Docker Compose for Full MQ + ACE Local Environment

```
Write a docker-compose.yml that runs a complete local IBM MQ + ACE
developer environment for the sample order-processing application.

Services:
1. mq:
   - Image: icr.io/ibm-messaging/mq:latest
   - Queue manager: MQLAB
   - Ports: 1414:1414, 9443:9443
   - Volume: qm_data:/mnt/mqm
   - Environment: MQ_ADMIN_PASSWORD, MQ_APP_PASSWORD, LICENSE=accept,
     MQ_QMGR_NAME=MQLAB

2. ace:
   - Image: icr.io/appc/ace:13.0.1.0 (or appropriate ACE developer image)
   - Depends on: mq (with health check)
   - Ports: 7600:7600 (admin REST), 7800:7800 (HTTP listener)
   - Volume: mount ./ace-work/bars to /home/aceuser/ace-server/run/
   - Environment: LICENSE=accept, ACE_SERVER_NAME=ORDERSERVER,
     MQ_HOST=mq, MQ_PORT=1414

Also show:
- A health check for the MQ service using `dspmq -m MQLAB`
- The ACE startup command to auto-deploy a BAR file on container start
- How to verify both services are connected using docker compose logs
```

---

### I7 — Test the Application End-to-End

```
Describe how to test the IBM MQ + ACE order-processing sample application
end-to-end without writing a client application. I want to use:

1. IBM MQ Web Console (port 9443):
   - How to browse APP.ORDERS.IN and APP.ORDERS.OUT queues
   - How to put a test message manually from the console

2. MQ command-line tools inside the container:
   - amqsput: put a test JSON order message to APP.ORDERS.IN
   - amqsget: read a processed message from APP.ORDERS.OUT
   Show the exact commands with the sample JSON payload:
   {"orderId":"ORD-001","customerId":"CUST-100","product":"Widget-X","quantity":5}

3. ACE Integration Server REST API:
   - How to check the flow is deployed and running via GET /apiv2/applications
   - How to check flow statistics via the admin REST API

4. Expected result: show what the output message should look like after the
   ESQL OrderProcessor transforms it.
```

---

### I8 — Package and Deploy BAR File from ACE Toolkit

```
Describe the steps to package and deploy an IBM ACE message flow as a
BAR (Broker Archive) file using the IBM ACE Toolkit.

Cover:
1. How to create a new BAR file in the ACE Toolkit (File → New → BAR File)
2. How to add the application and its flows to the BAR file
3. BAR file build options: compile ESQL, validate flow, override properties
4. How to override the MQ queue name and policy at deploy time without
   recompiling (BAR override properties / policy override)
5. How to deploy the BAR file to a local integration server using:
   a. The ACE Toolkit drag-and-drop (Integration Explorer)
   b. The ibmint deploy CLI command
   c. The ACE Admin REST API (curl command)

Also explain the difference between a full BAR deploy and an incremental
BAR deploy, and when each should be used.
```

---

## 🔴 Troubleshooting Prompts

### T1 — ACE Cannot Connect to MQ Container

```
My IBM ACE integration server is running locally and tries to connect to an
IBM MQ container on localhost:1414 using channel ACE.SVRCONN.
The flow fails to start with a BIP2628E error similar to:
  BIP2628E: The connection to queue manager 'MQLAB' was refused.
  MQRC 2538: MQRC_HOST_NOT_AVAILABLE

What are the most common causes and how do I diagnose each:
1. The MQ container is not running or the port 1414 is not exposed correctly
2. The SVRCONN channel ACE.SVRCONN does not exist on the queue manager
3. CHLAUTH rules are blocking the ACE connection user
4. The MQEndpoint policy has the wrong hostname, port, or queue manager name
5. The MQ listener is not started (STRMQM vs STRLSR)

Show the runmqsc and Docker commands to verify each cause and the fix.
```

---

### T2 — Message Stuck on APP.ORDERS.IN (Not Being Consumed)

```
I put a test message on APP.ORDERS.IN using amqsput but it stays on the
queue and is never consumed by my ACE flow. DISPLAY QSTATUS(APP.ORDERS.IN)
shows IPPROCS(0). My ACE flow is deployed and shows as running in the
Integration Explorer.

Walk me through diagnosing why the MQInput node is not reading the queue:
1. How to verify the MQInput node queue name matches exactly (case-sensitive)
2. How to check the MQ policy binding (wrong queue manager name in policy)
3. How to check ACE integration server logs for BIP errors related to MQInput
4. Whether the flow trigger is set correctly (Message Arrival vs Time-based)
5. How to use the ACE Flow Exerciser to inject a test message directly
   and bypass the MQInput node to isolate the problem
```

---

### T3 — ESQL Compute Node Throws BIP5400E at Runtime

```
My ESQL compute module OrderProcessor compiles without errors in the ACE
Toolkit but throws a BIP5400E exception at runtime when processing a
message. The error message references line 23 of my ESQL file.

How do I debug ESQL runtime errors in IBM ACE:
1. How to enable user trace on the integration server for my flow:
   ibmint trace start --name OrderProcessing --level normal
2. How to read the trace output to find the exact ESQL line and variable
   state at the point of failure
3. Common ESQL mistakes that cause runtime errors (referencing a field that
   doesn't exist, wrong tree path, type cast issues with JSON numbers)
4. How to use the ACE Flow Exerciser to step through the flow and inspect
   the message tree at each node
5. How to write defensive ESQL: check FIELDTYPE() before accessing a field,
   use COALESCE() to handle missing fields safely
```

---

### T4 — Messages Going to DLQ Instead of APP.ORDERS.OUT

```
All messages from APP.ORDERS.IN are ending up in APP.ORDERS.DLQ instead
of APP.ORDERS.OUT. The messages have BackoutCount = 1 in the MQMD.
My ESQL OrderProcessor does not seem to be routing them to the failure terminal.

What should I check:
1. Whether the Compute node 'failure' terminal is actually connected to
   the MQOutput node pointing to APP.ORDERS.DLQ
   (vs messages failing silently before reaching the Compute node)
2. Whether the MQOutput node for APP.ORDERS.OUT has PUT(DISABLED)
   (use DISPLAY QSTATUS(APP.ORDERS.OUT) TYPE(HANDLE))
3. Whether my ESQL PROPAGATE TO TERMINAL 'failure' is spelled correctly
   and whether the terminal name is case-sensitive in ACE
4. Whether the MQ BOTHRESH(3) is triggering before the application
   even processes the message (check BackoutCount value)
5. How to read DLQ messages using amqsbcg to inspect the MQMD and
   understand why they were dead-lettered
```

---

### T5 — ACE BAR Deployment Fails with BIP0832E

```
When I try to deploy my BAR file to the integration server I get:
  BIP0832E: The BAR file '<name>.bar' cannot be deployed because it
  contains a flow that references policy 'MQ_LOCAL' which does not exist
  in the default policy project.

My MQPolicy.policyxml is in the folder ~/ace-work/policies/ but the server
does not find it.

Walk me through fixing the policy resolution error:
1. How to configure the defaultPolicyProject in server.conf.yaml
   to point to my policy folder
2. The required directory structure for ACE to discover policy files
   (must be under a named policy project folder, not directly in policies/)
3. How to verify the policy is visible to the integration server using:
   ibmint list policyprojects --work-directory ~/ace-work
4. Whether the policy project name in the ESQL (policy 'MQ_LOCAL') must
   match the folder name exactly
5. How to package the policy project inside the BAR file itself to avoid
   the external folder dependency in production deployments
```
