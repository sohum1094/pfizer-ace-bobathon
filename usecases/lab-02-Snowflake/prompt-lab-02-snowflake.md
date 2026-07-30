# Prompts — Lab 02: Snowflake DB Integration (Push / Pull)

> Copy any prompt below and paste it into your AI assistant.
> Replace values in `<angle brackets>` with your own details.

---

## 🔵 Conceptual Prompts

### C1 — How ACE Connects to Snowflake

```
I am working through an IBM ACE lab that integrates with Snowflake.
Explain how IBM App Connect Enterprise 13 connects to Snowflake using JDBC.
Cover:
- What a JDBCProvider policy is and why it is needed
- The difference between DatabaseInput (periodic SELECT) and DatabaseRequest
  (mid-flow SQL) nodes
- Why Snowflake requires the JDBC driver JAR in a shared-classes directory
- What connection pooling means in this context and why pool size matters
  for Snowflake's compute warehouse concurrency limits
```

---

### C2 — Pull vs Push Patterns with a Cloud Data Warehouse

```
In IBM ACE, explain the difference between the PULL pattern (ACE reads from
Snowflake) and the PUSH pattern (ACE writes to Snowflake), including:
- When to use STATUS column polling vs timestamp watermarking for pull
- Why bulk batching (collect 500 messages, then one MERGE) is preferred
  over row-by-row inserts into Snowflake
- What MERGE INTO does in Snowflake and why it is idempotent
- How Change-Data-Capture (CDC) fits into the push pattern
```

---

### C3 — Understanding the Aggregation Node

```
Explain the IBM ACE Aggregation node pattern used when pushing batches of
MQ messages into Snowflake. Cover:
- How the Aggregation node collects messages and what triggers emission
  (size threshold vs timeout)
- What the ComIbmAggregateReplyBody tree structure looks like in ESQL
- How to handle a partial batch (e.g., timeout fires with only 47 of 500
  messages collected) without data loss
- The trade-off between batch size (throughput) and timeout (latency)
```

---

## 🟡 Implementation Prompts

### I1 — Generate JDBC Policy for Snowflake

```
Generate a complete JDBCProvider policy XML file for IBM ACE 13 that connects
to a Snowflake database with these settings:
- Policy name: SnowflakeDB
- Snowflake account: myaccount (so URL = jdbc:snowflake://myaccount.snowflakecomputing.com/)
- Database: ORDERS_DB
- Warehouse: COMPUTE_WH, Schema: PUBLIC, Role: SYSADMIN
- Max pool size: 10, Min pool size: 2
- Connection timeout: 30 seconds, Max idle time: 10 minutes
- Statement cache size: 50
- Use streaming result format: jdbc_query_result_format=json

Also show the mqsisetdbparms command to store the username and password.
```

---

### I2 — Snowflake Source Table DDL

```
Write the Snowflake DDL for a table called PENDING_ORDERS in ORDERS_DB.PUBLIC
suitable for use as the source table in an ACE pull flow. The table should:
- Have a VARCHAR(36) primary key ORDER_ID
- Include columns: CUSTOMER_ID, PRODUCT, QUANTITY (INTEGER), UNIT_PRICE (DECIMAL 10,2)
- Have a STATUS column defaulting to 'PENDING' with possible values: PENDING, DISPATCHED, FAILED
- Have CREATED_AT (TIMESTAMP_NTZ, default CURRENT_TIMESTAMP) and PROCESSED_AT (nullable)
- Include a Snowflake clustering key on STATUS to make the WHERE STATUS='PENDING' query efficient

Also show the INSERT statement to seed 10 test rows with STATUS='PENDING'.
```

---

### I3 — ESQL for Pull Flow (Snowflake → MQ)

```
Write the ESQL for a DatabaseInput-based ACE pull flow that reads PENDING rows
from Snowflake and publishes them to MQ. I need two compute modules:

1. SnowflakeRowToJSON — maps the DFDL row from DatabaseInput into a JSON message
   with fields: orderId, customerId, product, quantity (INTEGER), unitPrice (DECIMAL),
   pulledAt (ISO 8601 timestamp), and sets the MQ output queue to 'SNOWFLAKE.ORDERS.OUT'

2. MarkAsProcessed — after the MQ put succeeds, updates the Snowflake row to
   STATUS='DISPATCHED' and sets PROCESSED_AT = CURRENT_TIMESTAMP
   using the ORDER_ID from the message

Show both modules in ACE 13 ESQL with comments.
```

---

### I4 — ESQL for Push Flow (MQ → Snowflake MERGE)

```
Write the ESQL compute module BuildSnowflakeMerge for an IBM ACE push flow.
The input is a ComIbmAggregateReplyBody tree containing up to 500 collected
JSON messages, each with fields: orderId, customerId, product, quantity, unitPrice.

The module should:
1. Iterate all collected messages using CARDINALITY and REFERENCE
2. Build a VALUES list string (safe for direct embedding in SQL)
3. Construct a complete Snowflake MERGE INTO PROCESSED_ORDERS statement using
   ORDER_ID as the merge key: update STATUS when matched, insert when not matched
4. Set the result as OutputRoot.BLOB.BLOB encoded as UTF-8

Include proper null-safety and show the Aggregation node settings (size=500, timeout=10s).
```

---

### I5 — Watermark-Based Pull with CURRENT_TIMESTAMP

```
I want to replace the STATUS column polling in my Snowflake pull flow with
a watermark approach using CREATED_AT timestamps.

Show me:
1. The ACE ESQL pattern to read the last watermark from a tracking table
   (ACE_TRACKING.PULL_WATERMARKS) using DatabaseRequest
2. The dynamic SQL to SELECT rows WHERE CREATED_AT > last_watermark
   AND CREATED_AT <= CURRENT_TIMESTAMP
3. The ESQL to update the watermark after a successful MQ publish
4. How to handle the first-run case where no watermark exists yet

Include the tracking table DDL.
```

---

### I6 — CDC Pattern (Operational DB → Snowflake via ACE)

```
Design an IBM ACE flow for Change-Data-Capture (CDC) from an operational
PostgreSQL database into Snowflake. The CDC events arrive on an MQ queue
ORDER.CHANGES as JSON with fields: eventType (INSERT/UPDATE/DELETE),
tableName, primaryKey, beforeImage (object), afterImage (object).

Show the ESQL that:
1. Reads eventType from the message
2. Routes INSERT and UPDATE to a MERGE INTO Snowflake via DatabaseRequest
3. Routes DELETE to a separate DELETE statement
4. Handles unknown eventType by routing to a DLQ with an error envelope

Also explain how to handle high-volume CDC bursts without overwhelming Snowflake.
```

---

## 🔴 Troubleshooting Prompts

### T1 — JDBC Driver Class Not Found

```
My IBM ACE flow fails at startup with:
  BIP2230E: Could not load JDBC driver class 'net.snowflake.client.jdbc.SnowflakeDriver'

I placed snowflake-jdbc-3.13.33.jar in ~/ace-work/shared-classes/.
What are all the locations ACE looks for JDBC driver JARs, and what
server.conf.yaml settings control the JDBC driver class path?
Also, is there a way to verify the JAR is loaded without deploying a full flow?
```

---

### T2 — Snowflake Warehouse Suspended / Connection Timeout

```
My ACE DatabaseInput flow intermittently times out connecting to Snowflake.
The error in the ACE logs is:
  BIP2233E: A database exception occurred. SQLSTATE: 08001
  net.snowflake.client.jdbc.SnowflakeReaperException: JDBC driver timed out

I suspect the Snowflake warehouse auto-suspends after 5 minutes of inactivity.
What JDBCProvider policy settings should I adjust (connectionTimeout, keepAlive, etc.)
to keep the connection alive, and what is the Snowflake-side WAREHOUSE parameter
to control auto-suspend? Also show how to validate the connection is alive in ESQL.
```

---

### T3 — MERGE Statement Fails with SQL Compilation Error

```
My ACE ESQL builds a Snowflake MERGE statement dynamically by concatenating
VALUES from a collected batch. The DatabaseRequest node throws:
  SQL compilation error: syntax error line 1 at position 347 unexpected ','

This only happens when one of the product names contains a single quote (e.g., "O'Brien's Widget").
How do I safely escape single quotes in ESQL string concatenation for Snowflake SQL?
Show the REPLACE() pattern and also explain whether I should use parameterised
queries instead — and if so, how to use Database.Request.Parameter[] in ACE ESQL
with a dynamic number of rows in a VALUES list.
```

---

### T4 — Aggregation Node Emits Partial Batch After Restart

```
My ACE push flow uses an Aggregation node (size=500, timeout=10s).
When the ACE Integration Server restarts, in-flight messages from
the aggregation buffer are lost, causing gaps in the Snowflake data.

How does IBM ACE handle aggregation state across restarts? Is the
collected-but-not-emitted state persisted? What design changes should I make to
ensure no messages are lost when the server restarts mid-aggregation?
Include any relevant server.conf.yaml persistence settings.
```

---

### T5 — Pull Flow Re-Reads Already-Processed Rows

```
My ACE Snowflake pull flow occasionally re-reads rows that were already
published to MQ and marked as DISPATCHED. I think this happens when the
UPDATE (MarkAsProcessed) fails silently after the MQ PUT succeeds.

Explain why this race condition occurs and show me two approaches to fix it:
1. Using an XA transaction to make the MQ PUT and the STATUS UPDATE atomic
2. Using a SELECT FOR UPDATE / SKIP LOCKED pattern to prevent concurrent pulls
   from the same Snowflake table

Which approach works best with Snowflake specifically, since Snowflake does
not support SELECT FOR UPDATE?
```
