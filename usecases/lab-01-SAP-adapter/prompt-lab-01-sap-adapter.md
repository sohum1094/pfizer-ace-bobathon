# Prompts — Lab 01: SAP Adapter Integration (Push / Pull)

> Copy any prompt below and paste it into your AI assistant.
> Replace values in `<angle brackets>` with your own details.

---

## 🔵 Conceptual Prompts

### C1 — Understanding JCo and the SAP Adapter in ACE

```
I am working through an IBM ACE lab on SAP integration.
Explain in plain language how the SAP Java Connector (JCo) works inside
IBM App Connect Enterprise 13. Cover:
- What JCo is and why ACE needs the native library
- The difference between a SAPRequest node (pull / outbound) and a SAPInput node (push / inbound)
- How SAP BAPIs differ from plain RFCs, and when you would use each from ACE
- What a Program ID is and why both the SAP RFC destination (SM59) and the ACE SAPInput node must use the same value
Keep the explanation beginner-friendly with a short analogy.
```

---

### C2 — IDoc Basics

```
I am integrating IBM ACE with SAP using IDocs.
Explain what an IDoc is, how it differs from a BAPI call, and walk me through
the lifecycle of an ORDERS05 IDoc from the moment SAP triggers it to the moment
ACE places a JSON message on an IBM MQ queue.
Include the roles of: WE20 (partner profile), WE21 (IDoc port), SM59 (RFC destination),
and the ACE SAPInput node with its Program ID and Gateway service settings.
```

---

### C3 — Push vs Pull Trade-offs

```
In an IBM ACE + SAP integration, when should I use the PULL pattern
(ACE calls a SAP BAPI on demand) versus the PUSH pattern (SAP sends
IDocs to ACE)? Discuss:
- Latency and real-time requirements
- SAP system load implications
- Error handling differences (negative ACK for IDocs vs HTTP error for BAPI calls)
- Which pattern suits order processing, customer data sync, and inventory updates
```

---

## 🟡 Implementation Prompts

### I1 — Generate JCo Setup Script

```
Generate a bash script for macOS that:
1. Creates the directory ~/ace-work/shared-classes if it does not exist
2. Copies sapjco3.jar and libsapjco3.dylib from ~/Downloads/ into that directory
3. Verifies the JCo version by running: java -cp ~/ace-work/shared-classes/sapjco3.jar com.sap.conn.jco.rt.JCoRuntimeFactory
4. Prints a success or failure message

Also show the equivalent commands for Linux (libsapjco3.so).
```

---

### I2 — Generate SAPEndpointPolicy XML

```
Generate a complete ACE 13 SAPEndpoint policy XML file named SAPEndpointPolicy.policyxml
for a SAP development system with these details:
- Policy name: SAP_DEV
- SAP application server host: sap-dev.example.com
- System number: 00
- Client: 100
- Language: EN
- Username: ACEUSER (password stored separately via mqsisetdbparms)
- Connection pool capacity: 5, peak limit: 10
- Retry on connection failure: true, max retries: 3, delay: 5000ms, backoff multiplier: 2.0

Also show the mqsisetdbparms command to store the password securely.
```

---

### I3 — ESQL for BAPI_CUSTOMER_GETLIST Pull

```
Write the ESQL compute modules for an IBM ACE pull flow that calls the SAP BAPI
BAPI_CUSTOMER_GETLIST. The HTTP request body JSON looks like:
  { "fromCustomer": "0000100000", "toCustomer": "0000199999", "maxResults": 50 }

I need two modules:
1. SAPRequestMapper — maps the JSON body to the SAP BAPI import parameter structure
   (MAXROWS and CUSTOMRANGE table with SIGN='I', OPTION='BT', LOW, HIGH)
2. SAPResponseMapper — iterates the ADDRESSDATA table in the SAP response and
   builds a JSON array: { "customers": [ { "id": "...", "name": "...", "city": "..." } ] }

Use proper ESQL syntax for ACE 13. Add comments explaining each step.
```

---

### I4 — ESQL for ORDERS05 IDoc Processing

```
Write an ESQL compute module called IDOcToMQMapper for IBM ACE that processes
an inbound SAP ORDERS05 IDoc received by a SAPInput node.

The module should:
1. Extract the order header fields: document number (BELNR), order date (BLDAT),
   and sold-to party (first E1EDKA1 segment, PARTN field)
2. Loop through all E1EDP01 line item segments and build a JSON array with
   fields: posnr (POSEX), matnr (MATERIAL), qty (MENGE)
3. Set the MQ output queue to 'SAP.ORDERS.IN'

Also write a separate error-handler module SendNegativeACK that sets
EDI_DC40.STATUS = '51' to send a negative acknowledgement back to SAP.
```

---

### I5 — MQSC for SAP Integration Queues

```
Write MQSC commands to create the IBM MQ queues needed for a SAP + ACE integration lab:
- SAP.ORDERS.IN — receives IDoc-sourced order messages, persistent, max depth 500000
- SAP.ORDERS.PROCESSED — successfully processed orders
- SAP.ORDERS.DLQ — dead letter queue for failed SAP messages, max depth 250000
- SAP.ORDERS.RETRY — retry holding queue

Also set BOTHRESH(3) and BOQNAME(SAP.ORDERS.DLQ) on SAP.ORDERS.IN.
```

---

### I6 — Connection Retry Policy in server.conf.yaml

```
Show the server.conf.yaml additions needed to configure automatic retry
for a SAP JCo connection in IBM ACE 13. I want:
- Retry on connection failure: enabled
- Max retry attempts: 3
- Initial delay: 5 seconds
- Backoff multiplier: 2.0 (so delays are 5s, 10s, 20s)

Also explain what happens if all retries are exhausted — does the flow
throw an exception, and how should the error handler subflow catch it?
```

---

## 🔴 Troubleshooting Prompts

### T1 — JCo Library Not Found

```
My IBM ACE integration server fails to start with an error similar to:
  BIP6124E: The integration server cannot load the SAP JCo library.
  java.lang.UnsatisfiedLinkError: no sapjco3 in java.library.path

I placed sapjco3.jar and libsapjco3.dylib in ~/ace-work/shared-classes/.
What are the most common causes of this error on macOS, and what exact
server.conf.yaml or environment variable settings are needed to tell ACE
where to find the JCo native library?
```

---

### T2 — SAPInput Not Receiving IDocs

```
My ACE SAPInput node is configured with Program ID = ACE_ORDER_PROGRAM
and gateway host/service matching the RFC destination in SAP SM59.
ACE starts without errors, but when SAP sends an ORDERS05 IDoc via WE20/WE21,
nothing arrives in my ACE flow. How do I diagnose this step by step?
Include: how to check SAP WE02 IDoc monitor, how to verify the RFC destination
connection test in SM59, and what ACE Integration Server log messages to look for.
```

---

### T3 — SAP BAPI Returns Non-Zero Return Code

```
My ACE SAPRequest node calls BAPI_CUSTOMER_GETLIST and the call completes
without an ACE exception, but the SAP response contains a RETURN table with
TYPE='E' and a non-zero return code. My flow does not detect this as an error.

How do I write ESQL in ACE to inspect the BAPI RETURN table after a SAPRequest
node, check for error entries (TYPE='E' or TYPE='A'), build a structured error
envelope, and route the flow to an error output terminal instead of continuing
with normal processing?
```

---

### T4 — IDoc Duplicate Processing

```
I noticed that the SAP.ORDERS.IN queue occasionally receives duplicate messages
when an ORDERS05 IDoc is retransmitted from SAP. The IDoc DOCNUM in
EDI_DC40 is the same in both copies.

How do I implement idempotency in IBM ACE using the IDoc DOCNUM as a dedup key?
Show the ESQL pattern to:
1. Check a deduplication tracking table using DatabaseRequest
2. Insert the DOCNUM on first receipt
3. Silently discard the duplicate (route to audit terminal, not DLQ)
4. Handle the race condition if two copies arrive simultaneously
```

---

### T5 — Negative ACK Not Reaching SAP

```
My ACE error handler sends a negative ACK (STATUS=51) back to SAP after
a failed ORDERS05 IDoc, but the IDoc status in SAP WE02 still shows status 64
(IDoc ready to be transferred) instead of 51 (Application document not posted).

What are the correct ACE SAPOutput node settings for sending an IDoc
status update back to SAP, and what ESQL tree structure is needed in the
OutputRoot to correctly set the EDI_DC40 control record fields?
```
