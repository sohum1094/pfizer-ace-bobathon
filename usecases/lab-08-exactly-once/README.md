# Lab 08 — Exactly-Once Processing

## Overview

In distributed integration, the safe default is **at-least-once delivery**.
Moving to **exactly-once** requires combining:

1. **Idempotency** — safe to replay the same message  
2. **Deduplication** — detect and discard duplicates  
3. **XA (two-phase commit) transactions** — atomic MQ + DB in one transaction  
4. **Compensation / rollback** — undo partial work when a step fails  

```
PROBLEM
───────────────────────────────────────────────────────────────
Consumer crashes after DB INSERT but before MQ ACK
→ message replayed → duplicate DB INSERT ← BAD

SOLUTION
───────────────────────────────────────────────────────────────
Option A: Idempotent backend (MERGE / upsert) — no duplicate effect
Option B: Deduplication table — discard known messageIds
Option C: XA transaction — MQ GET + DB INSERT atomically
Option D: Compensation flow — detect + undo partial writes
```

---

## Prerequisites

| Requirement | Notes |
|---|---|
| ACE 13 with XA coordinator | `server.conf.yaml` global transaction settings |
| IBM MQ 9.3 | XA-capable queue manager |
| JDBC-capable DB | PostgreSQL, Db2, Oracle — any XA-capable JDBC driver |
| Base lab running | IBM MQ + ACE 13 |

---

## Part 1 — Idempotency Patterns

### 1.1  Natural Key Upsert (MERGE / INSERT OR IGNORE)

The simplest approach: design the backend operation so running it
twice has the same effect as running it once.

```sql
-- PostgreSQL / Db2 — upsert on order_id (natural key)
INSERT INTO processed_orders
  (order_id, customer_id, product, quantity, unit_price, processed_at)
VALUES
  (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
ON CONFLICT (order_id)
  DO NOTHING;          -- duplicate → silent no-op

-- Snowflake variant
MERGE INTO processed_orders AS t
USING (SELECT ? AS order_id) AS s ON t.order_id = s.order_id
WHEN NOT MATCHED THEN INSERT (order_id, ...) VALUES (?,...);
```

```esql
CREATE COMPUTE MODULE IdempotentInsert
  CREATE FUNCTION Main() RETURNS BOOLEAN
  BEGIN
    -- Use MERGE/upsert — safe to call multiple times
    SET OutputRoot.Database.Request.SQL =
        'INSERT INTO processed_orders '
        || '(order_id, customer_id, product, quantity, unit_price) '
        || 'VALUES (?,?,?,?,?) '
        || 'ON CONFLICT (order_id) DO NOTHING';

    SET OutputRoot.Database.Request.Parameter[1].value =
        InputRoot.JSON.Data.orderId;
    SET OutputRoot.Database.Request.Parameter[2].value =
        InputRoot.JSON.Data.customerId;
    SET OutputRoot.Database.Request.Parameter[3].value =
        InputRoot.JSON.Data.product;
    SET OutputRoot.Database.Request.Parameter[4].value =
        CAST(InputRoot.JSON.Data.quantity AS CHARACTER);
    SET OutputRoot.Database.Request.Parameter[5].value =
        CAST(InputRoot.JSON.Data.unitPrice AS CHARACTER);

    RETURN TRUE;
  END;
END MODULE;
```

### 1.2  Version / Sequence Idempotency

For update operations, always include a version/sequence check:

```sql
-- Only update if incoming version is strictly greater
UPDATE orders
SET    status = ?, version = ?, updated_at = CURRENT_TIMESTAMP
WHERE  order_id = ?
  AND  version < ?;       -- reject stale replays
```

---

## Part 2 — Deduplication Table

When the backend is not naturally idempotent, ACE maintains a
deduplication registry:

### 2.1  Schema

```sql
CREATE TABLE ace_dedup.message_registry (
    message_id   VARCHAR(36)   NOT NULL PRIMARY KEY,
    queue_name   VARCHAR(48)   NOT NULL,
    received_at  TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status       VARCHAR(10)   NOT NULL DEFAULT 'PROCESSING',  -- PROCESSING / DONE / FAILED
    expires_at   TIMESTAMP     NOT NULL                        -- TTL for cleanup
);

-- Index for fast lookup
CREATE INDEX idx_dedup_mid ON ace_dedup.message_registry (message_id);

-- Cleanup job: delete rows where expires_at < NOW()
```

### 2.2  ESQL — Deduplication Check

```esql
CREATE COMPUTE MODULE DedupCheck
  CREATE FUNCTION Main() RETURNS BOOLEAN
  BEGIN
    -- Use MQ MessageId as dedup key (24-byte hex)
    DECLARE msgId CHARACTER
        CAST(InputRoot.MQMD.MsgId AS CHARACTER);

    DECLARE existingStatus CHARACTER;

    -- Attempt to INSERT; conflict = already seen
    BEGIN
      INSERT INTO Database.ace_dedup.message_registry
        (message_id, queue_name, received_at, expires_at)
      VALUES
        (msgId, 'ORDER.IN', CURRENT_TIMESTAMP,
         CURRENT_TIMESTAMP + INTERVAL '48' HOUR);

      -- Successfully inserted → first time we see this message
      SET OutputLocalEnvironment.Dedup.isDuplicate = FALSE;
      SET OutputLocalEnvironment.Dedup.messageId   = msgId;

    EXCEPTION
      WHEN '23505' THEN  -- unique violation (PostgreSQL / Db2)
        -- Already processed — mark as duplicate
        SET OutputLocalEnvironment.Dedup.isDuplicate = TRUE;
        -- Check if previous attempt completed
        SELECT T.STATUS INTO existingStatus
        FROM Database.ace_dedup.message_registry AS T
        WHERE T.message_id = msgId;

        SET OutputLocalEnvironment.Dedup.priorStatus = existingStatus;
    END;

    RETURN TRUE;
  END;
END MODULE;
```

### 2.3  ESQL — Route Based on Dedup Result

```esql
CREATE COMPUTE MODULE DedupRouter
  CREATE FUNCTION Main() RETURNS BOOLEAN
  BEGIN
    SET OutputRoot = InputRoot;

    IF InputLocalEnvironment.Dedup.isDuplicate = TRUE THEN
      -- Duplicate: discard or send to audit
      PROPAGATE TO TERMINAL 'out2';  -- duplicate output
      RETURN FALSE;
    END IF;

    -- Not a duplicate: proceed to normal processing
    RETURN TRUE;
  END;
END MODULE;
```

---

## Part 3 — XA Transactions (Atomic MQ + DB)

### 3.1  XA Configuration in ACE

```yaml
# server.conf.yaml — enable XA global transactions
Coordinator:
  type: thorntail        # built-in XA coordinator
  recoveryEnabled: true
  recoveryPollInterval: 30000

JDBCProvider:
  OrdersDB:
    xaEnabled: true      # Use XA-capable data source
    maxPoolSize: 10
```

### 3.2  XA Transaction Flow

```
[MQInput ORDER.IN] ─── XA transaction START ───────────────────┐
        │                                                       │
        ▼                                                       │
[DatabaseRequest — INSERT processed_orders]                     │
        │                                                       │
        ▼                                                       │
[MQOutput ORDER.PROCESSED]                                      │
        │                                                       │
        └─── XA COMMIT (both MQ ack + DB insert committed) ────┘

If any step fails:
        └─── XA ROLLBACK (message returned to ORDER.IN, DB insert undone)
```

### 3.3  Flow Properties for XA

In the message flow properties:

| Property | Value |
|---|---|
| Transaction mode | Global |
| Coordinate transactions | Yes |

This ensures that the MQ GET and the DB INSERT are wrapped in a
single distributed (XA) transaction — both commit or neither does.

---

## Part 4 — Compensation / Rollback Patterns

### 4.1  The Saga Pattern

For long-running transactions spanning multiple systems (where XA is
impractical), use the **Saga** pattern — each step emits a compensating
action if a later step fails:

```
Step 1: Reserve inventory       → Compensate: Release reservation
Step 2: Create SAP order        → Compensate: Cancel SAP order
Step 3: Charge billing          → Compensate: Issue refund
Step 4: Notify customer         → No compensation needed
```

### 4.2  ACE Saga Orchestrator Flow

```
[HTTP POST /orders/saga]
        │
        ▼
[Compute: generate sagaId]
        │
        ▼
[MQOutput INVENTORY.RESERVE.CMD]  ←── Step 1
        │ await reply (RequestReply)
        ▼
[MQOutput SAP.ORDER.CREATE.CMD]   ←── Step 2
        │ await reply
        ▼
[MQOutput BILLING.CHARGE.CMD]     ←── Step 3
        │ await reply
        ▼
[HTTPReply 200 OK] ←── all steps succeeded

On any failure:
        ▼
[Compensation Flow: reverse completed steps in reverse order]
```

### 4.3  ESQL — Saga State Tracking

```esql
CREATE COMPUTE MODULE SagaOrchestrator
  CREATE FUNCTION Main() RETURNS BOOLEAN
  BEGIN
    DECLARE sagaId CHARACTER UUIDASCHAR;

    -- Initialize saga record
    INSERT INTO Database.ace_sagas.saga_state
      (saga_id, order_id, current_step, status, started_at)
    VALUES
      (sagaId, InputRoot.JSON.Data.orderId, 'INIT', 'IN_PROGRESS',
       CURRENT_TIMESTAMP);

    -- Store sagaId for downstream flows
    SET Environment.sagaId = sagaId;
    SET OutputRoot = InputRoot;
    SET OutputRoot.JSON.Data.sagaId = sagaId;

    RETURN TRUE;
  END;
END MODULE;

CREATE COMPUTE MODULE SagaStepComplete
  CREATE FUNCTION Main() RETURNS BOOLEAN
  BEGIN
    DECLARE step CHARACTER InputRoot.JSON.Data.step;

    -- Advance saga state
    UPDATE Database.ace_sagas.saga_state
    SET   current_step = step,
          updated_at   = CURRENT_TIMESTAMP
    WHERE saga_id = InputRoot.JSON.Data.sagaId;

    RETURN TRUE;
  END;
END MODULE;

CREATE COMPUTE MODULE SagaCompensate
  CREATE FUNCTION Main() RETURNS BOOLEAN
  BEGIN
    DECLARE sagaId    CHARACTER InputRoot.JSON.Data.sagaId;
    DECLARE failedAt  CHARACTER InputRoot.JSON.Data.failedStep;

    -- Mark saga as compensating
    UPDATE Database.ace_sagas.saga_state
    SET status = 'COMPENSATING', failed_step = failedAt
    WHERE saga_id = sagaId;

    SET OutputRoot = InputRoot;

    -- Trigger compensation commands in reverse order
    IF failedAt = 'BILLING' OR failedAt = 'NOTIFY' THEN
      -- Need to cancel SAP + release inventory
      PROPAGATE TO TERMINAL 'cancelSAP';
    END IF;

    IF failedAt = 'SAP' OR failedAt = 'BILLING' OR failedAt = 'NOTIFY' THEN
      -- Need to release inventory
      PROPAGATE TO TERMINAL 'releaseInventory';
    END IF;

    RETURN FALSE;
  END;
END MODULE;
```

### 4.4  Compensation Commands

```esql
-- Sent to INVENTORY.RELEASE.CMD
CREATE COMPUTE MODULE BuildInventoryRelease
  CREATE FUNCTION Main() RETURNS BOOLEAN
  BEGIN
    SET OutputRoot.JSON.Data.action      = 'RELEASE';
    SET OutputRoot.JSON.Data.sagaId      = InputRoot.JSON.Data.sagaId;
    SET OutputRoot.JSON.Data.orderId     = InputRoot.JSON.Data.orderId;
    SET OutputRoot.JSON.Data.product     = InputRoot.JSON.Data.product;
    SET OutputRoot.JSON.Data.quantity    = InputRoot.JSON.Data.quantity;
    SET OutputRoot.JSON.Data.requestedAt =
        CAST(CURRENT_TIMESTAMP AS CHARACTER FORMAT 'IU');

    SET OutputLocalEnvironment.Destination.MQ.DestinationData[1].queueName
        = 'INVENTORY.RELEASE.CMD';
    RETURN TRUE;
  END;
END MODULE;
```

---

## Part 5 — Poison Message Prevention

### 5.1  MQ Backout with Poison Detection

```mqsc
* Set backout threshold — after 3 failed GET+rollbacks, move to DLQ
ALTER QLOCAL(ORDER.IN) +
  BOTHRESH(3) +
  BOQNAME(ORDER.DEADLETTER)
```

### 5.2  ESQL — Detect and Skip Poison Messages

```esql
CREATE COMPUTE MODULE PoisonCheck
  CREATE FUNCTION Main() RETURNS BOOLEAN
  BEGIN
    DECLARE backoutCount INTEGER
        InputRoot.MQMD.BackoutCount;

    IF backoutCount >= 3 THEN
      -- Already tried 3 times — force to DLQ without further rollback
      SET OutputRoot = InputRoot;
      SET OutputRoot.JSON.Data._poisonReason =
          'Max backout count ' || CAST(backoutCount AS CHARACTER) || ' reached';
      SET OutputLocalEnvironment.Destination.MQ.DestinationData[1].queueName
          = 'ORDER.DEADLETTER';
      PROPAGATE TO TERMINAL 'out2';
      RETURN FALSE;
    END IF;

    RETURN TRUE;
  END;
END MODULE;
```

---

## Part 6 — Pattern Comparison

| Pattern | Guarantee | Complexity | When to use |
|---|---|---|---|
| **At-least-once** | No message lost | Low | Idempotent backends; most integrations |
| **Idempotent backend** | No duplicate effect | Low | DB upsert, SAP BAPI idempotency |
| **Deduplication table** | No duplicate processing | Medium | Non-idempotent backends |
| **XA transaction** | Atomic MQ+DB | High | Critical financial operations |
| **Saga + compensation** | Eventual consistency | Very High | Multi-system long-running flows |

---

## Exercises

1. **Exercise A** — Send the same order twice (same `orderId`). With the `ON CONFLICT DO NOTHING` upsert in place, verify only one row exists in `processed_orders`.
2. **Exercise B** — Disable the idempotent insert, send a duplicate, and observe double-insertion. Then enable the deduplication table; resend and verify the second message is routed to the duplicate output.
3. **Exercise C** — Configure XA on the flow; simulate a DB failure mid-flow (stop the DB container) and verify the MQ message is rolled back to `ORDER.IN` rather than lost.
4. **Exercise D** — Implement the Saga orchestrator for a 3-step order flow. Force a failure at step 2 (SAP) and verify the compensation flow releases the inventory reservation created in step 1.

---

## Key Concepts

| Concept | Description |
|---|---|
| **Idempotency** | Operation produces the same result regardless of how many times it is called |
| **Deduplication table** | Registry of processed message IDs — discard known IDs |
| **XA / 2PC** | Two-phase commit — distributed transaction protocol spanning MQ and DB |
| **Saga** | Sequence of local transactions with compensating actions for rollback |
| **Backout count** | MQ counter incremented each time a message is rolled back; used for poison detection |
| **Compensation** | Undoing completed steps when a later step in a saga fails |
