# Lab 03 — Reconciliation, Error Handling & Transformation Errors

## Overview

Production integration flows fail. This lab focuses on:

- **Clear, structured error messages** when transformation fails  
- **Reconciliation patterns** to detect missing, duplicate, or out-of-order messages  
- **Dead Letter Queue (DLQ) reprocessing** with exponential back-off  
- **ACE exception handling** at every tier: node, sub-flow, and flow level  

```
Normal path
───────────────────────────────────────────────────────────
[Input] ──► [Transform] ──► [Validate] ──► [Output]

Error path
───────────────────────────────────────────────────────────
[Input] ──► [Transform] ──X── exception
                              │
                         [Error Handler]
                              │
               ┌──────────────┼──────────────┐
               ▼              ▼              ▼
         [Enrich error]  [Log to file]  [DLQ / Retry]
               │
         structured JSON error envelope
```

---

## Part 1 — Structured Error Envelope

### 1.1  Design the Error Envelope Schema

Every error published to the DLQ or returned to a caller must carry a
**consistent, human-readable** payload:

```json
{
  "error": {
    "code": "ACE-TRANSFORM-001",
    "severity": "ERROR",
    "message": "Required field 'customerId' is missing",
    "source": {
      "flow": "OrderTransformFlow",
      "node": "ValidateOrder",
      "server": "ACE_LAB_SERVER"
    },
    "originalMessage": {
      "inputBody": "{ \"product\": \"Widget\" }",
      "inputHeaders": {}
    },
    "timestamp": "2024-07-15T10:32:00Z",
    "correlationId": "abc-123-xyz",
    "retryCount": 0,
    "retryable": true
  }
}
```

### 1.2  ESQL — Build the Error Envelope

```esql
CREATE PROCEDURE BuildErrorEnvelope(
  IN  errorCode    CHARACTER,
  IN  errorMsg     CHARACTER,
  IN  retryable    BOOLEAN,
  IN  retryCount   INTEGER,
  OUT envelope     ROW)
BEGIN
  SET envelope.error.code      = errorCode;
  SET envelope.error.severity  = 'ERROR';
  SET envelope.error.message   = errorMsg;
  SET envelope.error.source.flow   =
      CAST(InputLocalEnvironment.ComIbmFlowName AS CHARACTER);
  SET envelope.error.source.node   =
      CAST(InputLocalEnvironment.ComIbmNodeName AS CHARACTER);
  SET envelope.error.source.server =
      CAST(InputLocalEnvironment.ComIbmIntegrationServerLabel AS CHARACTER);
  SET envelope.error.timestamp     =
      CAST(CURRENT_TIMESTAMP AS CHARACTER FORMAT 'IU');
  SET envelope.error.correlationId =
      InputRoot.HTTPInputHeader."X-Correlation-ID";
  SET envelope.error.retryCount    = retryCount;
  SET envelope.error.retryable     = retryable;

  -- Capture original body (truncated to 4096 chars)
  SET envelope.error.originalMessage.inputBody =
      LEFT(CAST(InputRoot.BLOB.BLOB AS CHARACTER CCSID 1208), 4096);
END;
```

---

## Part 2 — Transformation Error Categories

### 2.1  Error Code Taxonomy

| Code | Category | Retryable | Example |
|---|---|---|---|
| `ACE-PARSE-001` | Parse / syntax | No | Malformed JSON body |
| `ACE-VALIDATE-001` | Schema validation | No | Missing required field |
| `ACE-VALIDATE-002` | Business rule | No | Negative quantity |
| `ACE-ENRICH-001` | Enrichment lookup failure | Yes | DB timeout during lookup |
| `ACE-ROUTE-001` | Routing decision failure | Yes | Unresolvable queue name |
| `ACE-DOWNSTREAM-001` | Downstream system error | Yes | SAP RFC timeout |
| `ACE-DOWNSTREAM-002` | Downstream data error | No | SAP BAPI return code ≠ 0 |

### 2.2  ESQL — Classify Transform Exceptions

```esql
CREATE COMPUTE MODULE TransformErrorClassifier
  CREATE FUNCTION Main() RETURNS BOOLEAN
  BEGIN
    -- Inspect the ACE exception list
    DECLARE excText  CHARACTER '';
    DECLARE excCode  CHARACTER 'ACE-UNKNOWN-001';
    DECLARE retryable BOOLEAN FALSE;

    DECLARE excList REFERENCE TO InputExceptionList.*;
    MOVE excList FIRSTCHILD;
    WHILE LASTMOVE(excList) DO
      SET excText = excText || excList.Text || ' ';
      MOVE excList NEXTSIBLING;
    END WHILE;

    -- Classify by exception keywords
    IF CONTAINS(excText, 'JSON') OR CONTAINS(excText, 'parse') THEN
      SET excCode   = 'ACE-PARSE-001';
      SET retryable = FALSE;
    ELSEIF CONTAINS(excText, 'NULL') OR CONTAINS(excText, 'required') THEN
      SET excCode   = 'ACE-VALIDATE-001';
      SET retryable = FALSE;
    ELSEIF CONTAINS(excText, 'MQRC') OR CONTAINS(excText, 'timeout') THEN
      SET excCode   = 'ACE-DOWNSTREAM-001';
      SET retryable = TRUE;
    ELSEIF CONTAINS(excText, 'JDBC') OR CONTAINS(excText, 'SQL') THEN
      SET excCode   = 'ACE-ENRICH-001';
      SET retryable = TRUE;
    END IF;

    -- Get retry count from message header (0 if first attempt)
    DECLARE retryCount INTEGER
        COALESCE(InputRoot.MQMD.UserIdentifier, 0);

    CALL BuildErrorEnvelope(excCode, excText, retryable, retryCount,
                            OutputRoot.JSON.Data);

    -- Route to DLQ or retry queue
    IF retryable AND retryCount < 3 THEN
      SET OutputLocalEnvironment.Destination.MQ.DestinationData[1].queueName
          = 'ORDER.RETRY';
      -- Embed retry metadata in MQMD
      SET OutputRoot.MQMD.UserIdentifier =
          CAST(retryCount + 1 AS CHARACTER);
    ELSE
      SET OutputLocalEnvironment.Destination.MQ.DestinationData[1].queueName
          = 'ORDER.DEADLETTER';
    END IF;

    RETURN TRUE;
  END;
END MODULE;
```

---

## Part 3 — DLQ Reprocessing with Exponential Back-off

### 3.1  Retry Queue Topology

```
ORDER.IN ──► [Main Flow] ──X──► [Error Handler] ──► ORDER.RETRY
                                                          │
                                           [Retry Consumer - scheduled]
                                                          │
                                              check retryCount & delay
                                                          │
                                      ┌──── retryCount < 3 ────┐
                                      ▼                        ▼
                               back to ORDER.IN         ORDER.DEADLETTER
```

### 3.2  ESQL — Exponential Back-off Delay

```esql
CREATE COMPUTE MODULE RetryDelayCompute
  CREATE FUNCTION Main() RETURNS BOOLEAN
  BEGIN
    DECLARE retryCount INTEGER
        CAST(InputRoot.MQMD.UserIdentifier AS INTEGER);

    -- Exponential back-off: 5s, 30s, 300s
    DECLARE delayMs INTEGER;
    CASE retryCount
      WHEN 1 THEN SET delayMs = 5000;
      WHEN 2 THEN SET delayMs = 30000;
      WHEN 3 THEN SET delayMs = 300000;
      ELSE        SET delayMs = 300000;
    END CASE;

    -- Schedule the re-enqueue via MQ scheduled delivery
    SET OutputRoot = InputRoot;
    SET OutputRoot.MQMD.PutDateTime =
        CURRENT_TIMESTAMP + CAST(delayMs AS INTERVAL MILLISECOND);

    RETURN TRUE;
  END;
END MODULE;
```

### 3.3  MQ Queue Configuration for Retry

```mqsc
* Retry queue — messages wait here before re-processing
DEFINE QLOCAL(ORDER.RETRY) +
  MAXDEPTH(50000) +
  MSGDLVSQ(FIFO) +
  DEFPSIST(YES) +
  REPLACE

* Backout/DLQ — messages land here after max retries
DEFINE QLOCAL(ORDER.DEADLETTER) +
  MAXDEPTH(250000) +
  DEFPSIST(YES) +
  REPLACE

* Set backout threshold on the main queue
ALTER QLOCAL(ORDER.IN) +
  BOQNAME(ORDER.DEADLETTER) +
  BOTHRESH(3)
```

---

## Part 4 — Reconciliation Patterns

### 4.1  Message Sequence Reconciliation

For ordered processing (e.g. financial transactions):

```esql
CREATE COMPUTE MODULE SequenceChecker
  CREATE FUNCTION Main() RETURNS BOOLEAN
  BEGIN
    DECLARE expectedSeq INTEGER;

    -- Retrieve last-seen sequence from a tracking table
    SELECT T.LAST_SEQ INTO expectedSeq
    FROM Database.ACE_TRACKING.SEQ_TRACKER AS T
    WHERE T.CHANNEL_ID = InputRoot.JSON.Data.channelId;

    DECLARE incomingSeq INTEGER = InputRoot.JSON.Data.sequenceNumber;

    IF incomingSeq <> expectedSeq + 1 THEN
      -- Gap detected
      SET OutputRoot.JSON.Data.reconciliationAlert.type = 'SEQUENCE_GAP';
      SET OutputRoot.JSON.Data.reconciliationAlert.expected = expectedSeq + 1;
      SET OutputRoot.JSON.Data.reconciliationAlert.received = incomingSeq;
      PROPAGATE TO TERMINAL 'out2';  -- alert output
      RETURN FALSE;
    END IF;

    -- Update last-seen
    UPDATE Database.ACE_TRACKING.SEQ_TRACKER
    SET LAST_SEQ = incomingSeq
    WHERE CHANNEL_ID = InputRoot.JSON.Data.channelId;

    RETURN TRUE;
  END;
END MODULE;
```

### 4.2  Volume Reconciliation (End-of-Day)

```esql
-- Stored in ACE tracking DB
-- Run after day's processing completes
SELECT
    DATE(PROCESSED_AT)           AS process_date,
    SOURCE_SYSTEM                AS source,
    COUNT(*)                     AS received_count,
    SUM(CASE WHEN STATUS='OK'   THEN 1 ELSE 0 END) AS success_count,
    SUM(CASE WHEN STATUS='DLQ'  THEN 1 ELSE 0 END) AS dlq_count,
    SUM(CASE WHEN STATUS='SKIP' THEN 1 ELSE 0 END) AS skipped_count
FROM ACE_TRACKING.MESSAGE_LOG
WHERE DATE(PROCESSED_AT) = CURRENT_DATE
GROUP BY 1, 2
ORDER BY 2;
```

### 4.3  Reconciliation Flow Architecture

```
[Timer 23:50] ──► [Query tracking DB] ──► [Query source counts]
                           │                       │
                           └──────────┬────────────┘
                                      ▼
                               [Compare totals]
                                      │
                       ┌─────────────┴─────────────┐
                       ▼                           ▼
               counts match                  gap detected
               [POST /recon/ok]         [POST /recon/alert]
                                               │
                                     email / ServiceNow ticket
```

---

## Part 5 — Logging Best Practices

### 5.1  User-Defined Log Entries

```esql
-- Structured log entry sent to stdout (captured by log aggregator)
CREATE PROCEDURE LogMessage(
  IN level      CHARACTER,  -- INFO / WARN / ERROR
  IN code       CHARACTER,
  IN message    CHARACTER,
  IN correlId   CHARACTER)
BEGIN
  DECLARE logLine CHARACTER
      '{"ts":"' || CAST(CURRENT_TIMESTAMP AS CHARACTER FORMAT 'IU')
      || '","level":"' || level
      || '","code":"'  || code
      || '","msg":"'   || REPLACE(message, '"', '\"')
      || '","corr":"'  || correlId || '"}';

  -- Write to ACE activity log
  LOG USER TRACE VALUES (logLine);
END;
```

### 5.2  Correlation ID Propagation

Always propagate a correlation ID from inbound to all outbound calls:

```esql
-- At entry flow: generate if missing
IF InputRoot.HTTPInputHeader."X-Correlation-ID" = '' THEN
  SET Environment.correlationId =
      UUIDASCHAR;  -- ACE built-in UUID generator
ELSE
  SET Environment.correlationId =
      InputRoot.HTTPInputHeader."X-Correlation-ID";
END IF;

-- Set on all outbound MQ messages
SET OutputRoot.MQMD.CorrelId =
    CAST(Environment.correlationId AS BLOB CCSID 1208);
```

---

## Exercises

1. **Exercise A** — Post a JSON message with a missing `customerId` field; verify the error envelope returned has code `ACE-VALIDATE-001` and `retryable: false`.
2. **Exercise B** — Post a message that causes a DB timeout; verify it lands on `ORDER.RETRY` with `retryCount: 1`, then watch it fail 3 times total before ending up on `ORDER.DEADLETTER`.
3. **Exercise C** — Send messages with sequence numbers 1, 2, 4 (skip 3); verify the reconciliation flow raises a `SEQUENCE_GAP` alert.
4. **Exercise D** — Browse `ORDER.DEADLETTER` in the MQ Web Console and replay a message manually back to `ORDER.IN`; observe it processes successfully.

---

## Key Concepts

| Concept | Description |
|---|---|
| **Exception list** | ACE internal tree populated when a node throws — always inspect in error handler |
| **Backout threshold** | MQ BOTHRESH — automatically moves poison messages to BOQNAME after N failures |
| **Exponential back-off** | Increasing delay between retries to avoid thundering herd |
| **Reconciliation** | Comparing processed counts vs source counts to detect data loss |
| **Correlation ID** | End-to-end tracing token — must be generated at entry and propagated everywhere |
