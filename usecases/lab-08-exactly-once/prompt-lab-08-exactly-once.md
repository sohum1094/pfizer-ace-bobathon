# Prompts — Lab 08: Exactly-Once Processing

> Copy any prompt below and paste it into your AI assistant.
> Replace values in `<angle brackets>` with your own details.

---

## 🔵 Conceptual Prompts

### C1 — Delivery Guarantees in Distributed Integration

```
Explain the three message delivery guarantees in distributed integration systems:
at-most-once, at-least-once, and exactly-once.

For each:
- What it means and when messages can be lost or duplicated
- How IBM MQ's persistent messages and transactional GET implement at-least-once
- Why exactly-once is expensive and often unnecessary if the backend is idempotent
- Practical examples: financial transactions that must be exactly-once vs
  analytics event counts that are fine with at-least-once

Conclude with advice on when to invest in exactly-once vs when to design
for idempotency instead.
```

---

### C2 — Idempotency: Designing Safe-to-Replay Operations

```
Explain what idempotency means in the context of IBM ACE + IBM MQ integration.
Cover:
- The difference between a naturally idempotent operation (e.g., HTTP PUT, SQL MERGE)
  vs a non-idempotent operation (e.g., HTTP POST, SQL INSERT)
- How SQL MERGE / INSERT ON CONFLICT DO NOTHING makes a DB write idempotent
- Version/sequence idempotency for UPDATE operations (only update if version < incoming)
- How to design a SAP BAPI call to be idempotent (using an idempotency key in BAPI header)
- The trade-off: idempotency adds a natural key constraint to the backend schema
```

---

### C3 — XA Transactions Explained

```
Explain XA (two-phase commit) transactions in the context of IBM ACE and IBM MQ.
Cover:
- What the two phases are (prepare and commit/rollback)
- Why both the MQ GET and the DB INSERT must be in the same XA boundary to
  guarantee exactly-once (atomicity)
- What happens during an XA rollback: the MQ message is returned to the queue,
  the DB write is undone
- Performance implications of XA: why it is slower than local transactions
- When XA is the right choice (critical financial records) vs when idempotency
  is sufficient and cheaper
- The ACE server.conf.yaml settings: Coordinator type, recoveryEnabled
```

---

### C4 — The Saga Pattern vs XA Transactions

```
Compare the Saga pattern and XA (two-phase commit) for managing multi-step
distributed transactions in IBM ACE.

Cover:
- Why XA does not work across microservices or when one participant is
  a SAP system or a REST API (non-XA participants)
- What the Saga pattern is: a sequence of local transactions with compensating
  actions to undo completed steps if a later step fails
- Choreography-based Saga (each service publishes events) vs Orchestration-based Saga
  (an ACE orchestrator drives the steps)
- How to implement a Saga orchestrator in ACE using MQ request/reply and state tracking in a DB
- The trade-off: Saga achieves eventual consistency, not strict ACID atomicity

Give a 3-step example: inventory reservation → SAP order → billing charge.
```

---

## 🟡 Implementation Prompts

### I1 — Idempotent DB Insert (MERGE Pattern)

```
Write the IBM ACE ESQL compute module IdempotentInsert that performs an
idempotent INSERT into a PostgreSQL / Db2 table called processed_orders.

Requirements:
1. Use INSERT ... ON CONFLICT (order_id) DO NOTHING (PostgreSQL) or
   MERGE INTO (Db2/Snowflake) to make the insert safe to replay
2. Map fields from InputRoot.JSON.Data:
   orderId → order_id (primary key), customerId, product, quantity (INTEGER),
   unitPrice (DECIMAL)
3. Use parameterised query via Database.Request.Parameter[] to prevent SQL injection
4. After the insert, check Database.Request.RowsAffected:
   - 1 = first insert (new message)
   - 0 = duplicate (already processed) → PROPAGATE to 'out2' audit terminal

Also show the Db2 MERGE variant for completeness.
```

---

### I2 — Deduplication Table Schema and ESQL

```
Design a complete deduplication solution for IBM ACE with these requirements:
- Dedup key: MQMD.MsgId (24-byte hex string)
- TTL: 48 hours (entries expire and can be cleaned up)
- Status tracking: PROCESSING → DONE or FAILED

Show:
1. The SQL DDL for ace_dedup.message_registry with all columns,
   primary key on message_id, and index on (message_id, expires_at)
2. The ESQL compute module DedupCheck that:
   - Attempts INSERT into message_registry
   - On unique violation (SQLSTATE 23505): marks isDuplicate=TRUE and
     reads the prior status into OutputLocalEnvironment.Dedup.priorStatus
   - On success: marks isDuplicate=FALSE
3. The ESQL compute module DedupRouter that routes duplicates to 'out2'
   and first-time messages to 'out1'
4. The ESQL to mark a message as DONE after successful processing:
   UPDATE message_registry SET status='DONE' WHERE message_id=?
5. A cleanup SQL job (DELETE WHERE expires_at < CURRENT_TIMESTAMP)
```

---

### I3 — XA Transaction Configuration (server.conf.yaml + Flow)

```
Show the complete IBM ACE 13 configuration for XA (global) transactions
spanning MQ and a JDBC database.

Provide:
1. server.conf.yaml additions:
   - Coordinator section (type, recoveryEnabled, recoveryPollInterval)
   - JDBCProvider with xaEnabled: true and maxPoolSize

2. The message flow property settings that must be set in the ACE Toolkit:
   - Transaction mode: Global
   - Coordinate transactions: Yes

3. The ASCII flow diagram showing the XA transaction boundary:
   MQInput ORDER.IN → XA START
   → DatabaseRequest (INSERT processed_orders)
   → MQOutput ORDER.PROCESSED
   → XA COMMIT (both ack + DB insert committed)
   → on failure: XA ROLLBACK (message returned to ORDER.IN, DB rolled back)

4. How to test XA rollback by stopping the DB mid-flow and verifying
   the MQ message is returned to ORDER.IN

5. XA recovery: what happens after an ACE crash during the prepare phase
```

---

### I4 — Saga Orchestrator Flow

```
Write the IBM ACE ESQL for a Saga orchestrator that manages a 3-step order flow:
Step 1: Reserve inventory (INVENTORY.RESERVE.CMD)
Step 2: Create SAP order (SAP.ORDER.CREATE.CMD)
Step 3: Charge billing (BILLING.CHARGE.CMD)

I need three ESQL modules:

1. SagaOrchestrator — generates a sagaId (UUID), inserts into
   Database.ace_sagas.saga_state (saga_id, order_id, current_step='INIT',
   status='IN_PROGRESS', started_at), sets Environment.sagaId, adds sagaId
   to the output message

2. SagaStepComplete — updates current_step in saga_state after each step reply

3. SagaCompensate — on failure at a given step, marks status='COMPENSATING',
   sets failed_step, and PROPAGATEs to the correct compensation terminals
   (cancelSAP, releaseInventory) in reverse order

Also show the DDL for ace_sagas.saga_state.
```

---

### I5 — Compensation Command Builders

```
Write the IBM ACE ESQL modules for saga compensation commands:

1. BuildInventoryRelease — builds a JSON command to INVENTORY.RELEASE.CMD:
   { action: 'RELEASE', sagaId, orderId, product, quantity, requestedAt }

2. BuildSAPOrderCancel — builds a command to SAP.ORDER.CANCEL.CMD:
   { action: 'CANCEL', sagaId, sapOrderId, cancelReason: 'SAGA_COMPENSATION',
     requestedAt }

3. BuildBillingRefund — builds a command to BILLING.REFUND.CMD:
   { action: 'REFUND', sagaId, chargeId, amount, currency, requestedAt }

For each, also show:
- How the sagaId is passed from Environment (set by SagaOrchestrator)
- How the sagaId ties these compensation commands back to the original order
- How the orchestrator marks the saga as COMPENSATED once all compensation
  replies are received
```

---

### I6 — Poison Message Detection with BackoutCount

```
Write the IBM ACE ESQL compute module PoisonCheck and the MQSC
configuration for poison message detection.

Requirements:
1. MQSC: set BOTHRESH(3) and BOQNAME(ORDER.DEADLETTER) on ORDER.IN
2. ESQL module PoisonCheck that:
   - Reads InputRoot.MQMD.BackoutCount
   - If BackoutCount >= 3: adds _poisonReason to the message JSON,
     routes to ORDER.DEADLETTER via PROPAGATE TO TERMINAL 'out2',
     RETURN FALSE
   - Otherwise: RETURN TRUE (normal processing)

Also explain:
- The difference between MQ's automatic BOTHRESH mechanism and the
  application-level BackoutCount check in ESQL (which fires first)
- Why you need BOTH: MQ BOTHRESH as a safety net, and ESQL check for
  application-controlled routing before MQ forces the move
- How to replay a message from ORDER.DEADLETTER back to ORDER.IN
  after fixing the underlying issue
```

---

## 🔴 Troubleshooting Prompts

### T1 — Duplicate Rows Appearing Despite MERGE/Upsert

```
My ACE flow uses INSERT INTO processed_orders ... ON CONFLICT (order_id) DO NOTHING.
I still see duplicate rows in processed_orders for the same order_id.
The duplicate rows have different processed_at timestamps.

What are the possible causes:
1. The order_id column does not have a UNIQUE constraint (the ON CONFLICT clause
   requires a constraint or index to detect the conflict)
2. Two parallel ACE flow instances are processing the same message simultaneously
   (race condition between the SELECT check and the INSERT)
3. The deduplication is happening on order_id but MQ is delivering two messages
   with different MsgIds that happen to contain the same order_id payload
4. The table is in a different schema than expected (MERGE target name mismatch)

Show the SQL to add the missing UNIQUE constraint and verify it is enforced.
```

---

### T2 — XA Transaction: DB Rolled Back but Message Consumed

```
My XA flow should roll back both the MQ GET and the DB INSERT if either fails.
After a test where I deliberately caused a DB failure, the DB INSERT was rolled
back correctly, but the MQ message was consumed (not returned to ORDER.IN).

This breaks the exactly-once guarantee. What are the likely causes:
1. The flow's Transaction mode is set to 'Local' instead of 'Global'
2. The JDBC data source does not have xaEnabled: true in server.conf.yaml
3. The XA coordinator crashed before it could write the prepared-but-not-committed
   log entry — explain what happens during XA recovery in this case
4. The MQInput node is configured with Transactional=No

For each cause, show the corrective configuration change.
```

---

### T3 — Deduplication Table Causing High DB Latency

```
My ACE deduplication check (INSERT into message_registry) is adding
80-100ms to every message's processing time at peak load (500 msg/sec).
The table has 2M rows.

What optimisations can I apply:
1. Index tuning (what index exactly is needed for the INSERT conflict check)
2. Partitioning the dedup table by expires_at to speed up TTL cleanup
3. Using an in-memory cache (Redis, Hazelcast) instead of DB for dedup lookup
   — explain the trade-off (in-memory is faster but non-durable across crashes)
4. Batching the dedup inserts (can I check 50 MsgIds in one query?)
5. Whether the dedup table should be in the same DB as the business data
   or a separate, lightweight DB
```

---

### T4 — Saga Stuck in COMPENSATING State

```
My Saga orchestrator shows a saga in status='COMPENSATING' for 3 hours.
The compensation commands were sent to INVENTORY.RELEASE.CMD and SAP.ORDER.CANCEL.CMD,
but the saga_state table was never updated to COMPENSATED.

Walk me through diagnosing a stuck Saga:
1. How to check whether the compensation commands are still sitting on the queue
   (unprocessed) vs processed but the reply was lost
2. Whether the orchestrator is correctly awaiting compensation replies
   (is there a ReplyTo queue set on the compensation commands?)
3. How to implement a saga timeout: if COMPENSATING for > 30 minutes,
   raise an alert and require manual intervention
4. How to manually mark a saga as COMPENSATED in the database (with audit trail)
   when the automated compensation flow has failed permanently
```

---

### T5 — BackoutCount Not Incrementing as Expected

```
I set BOTHRESH(3) on ORDER.IN and my PoisonCheck ESQL checks BackoutCount.
In testing, I see BackoutCount = 0 on all messages, even messages that have
been rolled back multiple times. The messages are not moving to the DLQ.

What are the common reasons BackoutCount stays at 0 in IBM MQ:
1. The MQInput node is not configured in Transactional mode
   (BackoutCount only increments on transactional rollback)
2. The flow is catching the exception before it reaches a rollback
   (exception caught by error handler, message acknowledged even though processing failed)
3. BOTHRESH is set on the wrong queue (alias queue vs base queue)
4. The IBM MQ version does not support the BOTHRESH feature (very old versions)

Show the MQSC commands to verify BOTHRESH and BOQNAME are correctly set,
and show the flow configuration changes needed to ensure transactional rollback
actually triggers BackoutCount increment.
```
