# Prompts — Lab 03: Reconciliation, Error Handling & Transformation Errors

> Copy any prompt below and paste it into your AI assistant.
> Replace values in `<angle brackets>` with your own details.

---

## 🔵 Conceptual Prompts

### C1 — ACE Error Handling Architecture

```
I am learning about error handling in IBM App Connect Enterprise 13.
Explain the full error handling architecture, covering:
- The difference between node-level error terminals, sub-flow error handlers,
  and flow-level Catch terminals
- What the InputExceptionList tree is, when it is populated, and how to
  traverse it in ESQL
- Why every production flow needs an explicit error handler subflow
  (what happens if you don't have one)
- The difference between a retryable error (transient, worth retrying) and
  a non-retryable error (permanent, send to DLQ immediately)
Use concrete examples: a DB timeout (retryable) vs a malformed JSON body (non-retryable).
```

---

### C2 — Reconciliation Patterns in Integration

```
In enterprise integration using IBM MQ and ACE, what does "reconciliation" mean
and why is it necessary? Explain:
- Volume reconciliation: comparing message counts between source and target systems
- Sequence reconciliation: detecting gaps or duplicates in ordered message streams
- End-of-day / batch reconciliation vs. real-time event reconciliation
- How the ACE tracking database and MESSAGE_LOG table support both approaches
- What actions should be triggered when a reconciliation gap is detected
  (alerting, replay, compensating transaction)
```

---

### C3 — Correlation IDs and Distributed Tracing

```
Explain the role of a Correlation ID in IBM ACE integration flows.
Cover:
- Why generating a UUID at the entry flow and propagating it everywhere is critical
- How to carry the correlation ID through: HTTP headers (X-Correlation-ID),
  MQ MQMD.CorrelId, SAP IDoc reference fields, and DB tracking tables
- How correlation IDs enable end-to-end log tracing across ACE, MQ, and downstream systems
- What tooling (IBM Operations Dashboard, ELK/Splunk) can consume structured
  JSON logs containing the correlation ID
```

---

## 🟡 Implementation Prompts

### I1 — Structured Error Envelope ESQL Procedure

```
Write a reusable ESQL PROCEDURE called BuildErrorEnvelope for IBM ACE 13
that constructs a standardised JSON error envelope. The envelope should include:
- error.code (passed in)
- error.severity (always 'ERROR')
- error.message (passed in)
- error.source.flow (from InputLocalEnvironment.ComIbmFlowName)
- error.source.node (from InputLocalEnvironment.ComIbmNodeName)
- error.source.server (from InputLocalEnvironment.ComIbmIntegrationServerLabel)
- error.timestamp (current timestamp in ISO 8601)
- error.correlationId (from InputRoot.HTTPInputHeader."X-Correlation-ID")
- error.retryCount (passed in as INTEGER)
- error.retryable (passed in as BOOLEAN)
- error.originalMessage.inputBody (first 4096 chars of InputRoot.BLOB.BLOB as UTF-8)

The procedure signature should be: IN errorCode CHARACTER, IN errorMsg CHARACTER,
IN retryable BOOLEAN, IN retryCount INTEGER, OUT envelope ROW

Add inline comments explaining each field.
```

---

### I2 — Error Code Taxonomy and Exception Classifier

```
Write an IBM ACE ESQL compute module called TransformErrorClassifier that:
1. Traverses the InputExceptionList tree to concatenate all exception text
2. Classifies the exception into one of these error codes using keyword matching:
   - ACE-PARSE-001: keywords 'JSON', 'parse', 'syntax'
   - ACE-VALIDATE-001: keywords 'NULL', 'required', 'missing', 'schema'
   - ACE-VALIDATE-002: keywords 'negative', 'range', 'business rule'
   - ACE-ENRICH-001: keywords 'JDBC', 'SQL', 'database'
   - ACE-DOWNSTREAM-001: keywords 'MQRC', 'timeout', 'connect'
   - ACE-UNKNOWN-001: fallback for anything else
3. Reads retryCount from MQMD.UserIdentifier (default 0)
4. Calls BuildErrorEnvelope to populate OutputRoot.JSON.Data
5. Routes to ORDER.RETRY (if retryable AND retryCount < 3) or ORDER.DEADLETTER

Mark retryable=TRUE only for ENRICH and DOWNSTREAM-001 codes.
```

---

### I3 — Exponential Back-off Retry Flow

```
Write the IBM ACE ESQL and MQSC configuration for an exponential back-off
retry pattern. Requirements:
- Retry queue: ORDER.RETRY
- Main processing queue: ORDER.IN
- Dead letter queue: ORDER.DEADLETTER
- Max retries: 3
- Delays: attempt 1 = 5s, attempt 2 = 30s, attempt 3 = 300s

Show:
1. The ESQL compute module RetryDelayCompute that reads retryCount from
   MQMD.UserIdentifier and sets MQMD.PutDateTime for scheduled delivery
2. The MQSC commands to define ORDER.RETRY and set BOTHRESH/BOQNAME on ORDER.IN
3. A flow diagram (ASCII) of the retry topology
4. How to verify the scheduled put worked using the MQ Web Console
```

---

### I4 — Sequence Gap Detection

```
Write an IBM ACE ESQL compute module SequenceChecker that:
1. Reads channelId and sequenceNumber from InputRoot.JSON.Data
2. Looks up the last seen sequence number from Database.ACE_TRACKING.SEQ_TRACKER
   (columns: CHANNEL_ID, LAST_SEQ)
3. If incoming sequence != last_seq + 1, sets a reconciliation alert on
   OutputRoot.JSON.Data.reconciliationAlert with type='SEQUENCE_GAP',
   expected=(last_seq+1), received=(sequenceNumber), and PROPAGATEs to terminal 'out2'
4. If the sequence is correct, updates SEQ_TRACKER and returns TRUE for normal processing

Also show the DDL for the SEQ_TRACKER table and how to handle the first-message
case where no row exists yet (LAST_SEQ should be treated as 0).
```

---

### I5 — End-of-Day Volume Reconciliation Flow

```
Design an IBM ACE reconciliation flow that runs at 23:50 every day and:
1. Queries ACE_TRACKING.MESSAGE_LOG to count received/success/DLQ messages per source system
2. Queries each source system's API or DB for the expected count for that day
3. Compares the two counts
4. If counts match: POSTs to POST /api/v1/reconciliation/ok with a summary JSON
5. If gap detected: POSTs to POST /api/v1/reconciliation/alert with details

Show:
- The TimerInput node settings for 23:50 daily
- The MESSAGE_LOG DDL (columns: message_id, source_system, status, processed_at)
- The ESQL that builds the reconciliation report JSON
- The SQL SELECT with GROUP BY used to aggregate the counts
```

---

### I6 — Structured JSON Logging with Correlation ID

```
Write two reusable ESQL artefacts for IBM ACE 13:

1. A PROCEDURE LogMessage(IN level CHARACTER, IN code CHARACTER,
   IN message CHARACTER, IN correlId CHARACTER) that emits a single-line
   JSON log entry via LOG USER TRACE in this format:
   {"ts":"...","level":"INFO","code":"ACE-ORDER-001","msg":"...","corr":"..."}

2. A compute module CorrelationIdInit (to use at the start of every entry flow) that:
   - Checks if InputRoot.HTTPInputHeader."X-Correlation-ID" is non-empty
   - If present, stores it in Environment.correlationId
   - If missing, generates a UUID using UUIDASCHAR and stores it
   - Sets OutputRoot.HTTPResponseHeader."X-Correlation-ID" to the same value
   - Sets OutputRoot.MQMD.CorrelId to the UTF-8 BLOB of the correlation ID

Add comments explaining the CCSID 1208 cast for MQMD.CorrelId.
```

---

## 🔴 Troubleshooting Prompts

### T1 — InputExceptionList Is Empty in Error Handler

```
My IBM ACE error handler subflow is triggered correctly when a downstream
node fails, but when I try to traverse InputExceptionList to get the error text,
it appears empty. My ESQL looks like:
  DECLARE excList REFERENCE TO InputExceptionList.*;
  MOVE excList FIRSTCHILD;
  WHILE LASTMOVE(excList) DO ...

What are the common reasons InputExceptionList is empty or inaccessible in an
ACE error handler, and what is the correct way to traverse the full nested
exception list tree including nested exception nodes and their Text fields?
```

---

### T2 — Messages Not Appearing on ORDER.RETRY After Error

```
My TransformErrorClassifier compute module sets the output queue to ORDER.RETRY
for retryable errors, but messages are landing on ORDER.DEADLETTER instead
(the MQ backout queue). The BOTHRESH on ORDER.IN is set to 3.

Explain the interaction between:
- The MQ BackoutCount in MQMD (incremented by MQ on rollback)
- My application-level retryCount in MQMD.UserIdentifier
- The MQ BOTHRESH setting

Why might MQ be moving the message to the DLQ before my flow's retry logic
runs 3 times, and what is the correct architecture to prevent MQ's BOTHRESH
from interfering with application-level retry?
```

---

### T3 — Retry Loop Causing Infinite Processing

```
My retry flow accidentally created an infinite loop: a message keeps cycling
between ORDER.IN → error → ORDER.RETRY → ORDER.IN → error.
The retryCount in MQMD.UserIdentifier is being reset to 0 each time.

Why does this happen and how do I fix it? Show the ESQL pattern that:
1. Correctly reads retryCount from the incoming message (from MQMD.UserIdentifier
   or a custom MQRFH2/usr header)
2. Increments and preserves it across re-enqueue to ORDER.IN
3. Hard-stops at retryCount >= 3 regardless of any other condition
```

---

### T4 — Reconciliation Query Returns Wrong Counts

```
My end-of-day reconciliation query against ACE_TRACKING.MESSAGE_LOG
returns counts that don't match the source system's reported totals.
After investigation I find that some messages have NULL in the processed_at
column and are not being counted.

What are common reasons messages end up with NULL processed_at in a tracking
table, and how should I fix the reconciliation SQL to include them?
Also, should messages that are still IN_PROGRESS at 23:50 be counted as
success or gap, and how do I handle that in the reconciliation logic?
```

---

### T5 — Correlation ID Lost After MQ Hop

```
My correlation ID is correctly set in HTTP flows (X-Correlation-ID header),
but after a message passes through an MQ queue and is consumed by a downstream
ACE flow, the correlation ID is missing from Environment.correlationId.

How does IBM MQ carry correlation IDs in MQMD (CorrelId vs MsgId), and what
ESQL do I need in the downstream consuming flow to correctly read the
correlation ID from the incoming MQMD.CorrelId and restore it to Environment?
Also explain the BLOB-to-CHARACTER conversion required given MQMD.CorrelId is 24 bytes.
```
