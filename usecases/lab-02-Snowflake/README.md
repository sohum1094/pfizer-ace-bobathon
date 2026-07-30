# Lab 02 — Snowflake DB Integration (Push / Pull)

## Overview

ACE integrates with Snowflake using its **JDBC connector**.  
This lab demonstrates two patterns:

- **Pull** — ACE queries Snowflake on a schedule or HTTP trigger and publishes results to MQ.  
- **Push** — ACE consumes messages from MQ and bulk-loads them into Snowflake.

```
PULL pattern
─────────────────────────────────────────────────────────────────────
[Timer / HTTP] ──► [JDBC Input / DatabaseInput] ──► [MQ Output]
                          │
                   SELECT from Snowflake

PUSH pattern
─────────────────────────────────────────────────────────────────────
[MQ Input] ──► [Aggregate] ──► [JDBC Request] ──► [Snowflake Table]
                  batch N rows      INSERT / MERGE
```

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Snowflake JDBC driver | `snowflake-jdbc-x.y.z.jar` — download from [Snowflake Maven repo](https://repo1.maven.org/maven2/net/snowflake/snowflake-jdbc/) |
| Snowflake account + warehouse | Free trial at snowflake.com is sufficient |
| Base lab running | IBM MQ + ACE 13 |

### Install JDBC Driver

```bash
mkdir -p ~/ace-work/shared-classes
cp ~/Downloads/snowflake-jdbc-*.jar ~/ace-work/shared-classes/

# Verify driver loads
java -cp ~/ace-work/shared-classes/snowflake-jdbc-*.jar \
     net.snowflake.client.jdbc.SnowflakeDriver
```

---

## Part 1 — Database Policy Configuration

Create `ace-config/SnowflakeJDBCPolicy.policyxml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<policies>
  <policy policyType="JDBCProvider"
          policyName="SnowflakeDB"
          policyVersion="1">
    <properties>
      <type>Snowflake</type>
      <url>jdbc:snowflake://{{SNOWFLAKE_ACCOUNT}}.snowflakecomputing.com/</url>
      <driverClassName>net.snowflake.client.jdbc.SnowflakeDriver</driverClassName>
      <databaseName>ORDERS_DB</databaseName>
      <maxPoolSize>5</maxPoolSize>
      <connectionUrlParameters>
        warehouse=COMPUTE_WH&amp;schema=PUBLIC&amp;role=SYSADMIN
      </connectionUrlParameters>
    </properties>
  </policy>
</policies>
```

Store credentials securely:

```bash
source '/Applications/IBM App Connect Enterprise/server/bin/mqsiprofile'
mqsisetdbparms ACE_LAB_SERVER \
  -n SnowflakeDB::username -u SVCACEUSER -p <password>
```

---

## Part 2 — PULL Pattern (ACE reads Snowflake → MQ)

### 2.1  Schema — Snowflake Source Table

```sql
-- Run in Snowflake worksheet
CREATE OR REPLACE TABLE ORDERS_DB.PUBLIC.PENDING_ORDERS (
    ORDER_ID      VARCHAR(36) NOT NULL PRIMARY KEY,
    CUSTOMER_ID   VARCHAR(20),
    PRODUCT       VARCHAR(100),
    QUANTITY      INTEGER,
    UNIT_PRICE    DECIMAL(10,2),
    STATUS        VARCHAR(20) DEFAULT 'PENDING',
    CREATED_AT    TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    PROCESSED_AT  TIMESTAMP_NTZ
);
```

### 2.2  Flow: `SnowflakePullFlow.msgflow`

```
[TimerInput] ──► [DatabaseInput] ──► [Mapping] ──► [MQOutput]
   every 30s       SELECT WHERE             JSON
                   STATUS='PENDING'
```

**DatabaseInput node settings:**

| Property | Value |
|---|---|
| Data source | `{default}:SnowflakeDB` |
| SQL statement | `SELECT ORDER_ID, CUSTOMER_ID, PRODUCT, QUANTITY, UNIT_PRICE FROM PENDING_ORDERS WHERE STATUS='PENDING' FETCH FIRST 100 ROWS ONLY` |

### 2.3  ESQL — Map Snowflake Row to JSON

```esql
CREATE COMPUTE MODULE SnowflakeRowToJSON
  CREATE FUNCTION Main() RETURNS BOOLEAN
  BEGIN
    DECLARE row REFERENCE TO InputRoot.DFDL.PENDING_ORDERS;

    SET OutputRoot.JSON.Data.orderId    = row.ORDER_ID;
    SET OutputRoot.JSON.Data.customerId = row.CUSTOMER_ID;
    SET OutputRoot.JSON.Data.product    = row.PRODUCT;
    SET OutputRoot.JSON.Data.quantity   = CAST(row.QUANTITY AS INTEGER);
    SET OutputRoot.JSON.Data.unitPrice  = CAST(row.UNIT_PRICE AS DECIMAL);
    SET OutputRoot.JSON.Data.pulledAt   =
        CAST(CURRENT_TIMESTAMP AS CHARACTER FORMAT 'IU');

    -- Mark the destination queue
    SET OutputLocalEnvironment.Destination.MQ.DestinationData[1].queueName
        = 'SNOWFLAKE.ORDERS.OUT';

    RETURN TRUE;
  END;
END MODULE;
```

### 2.4  Mark Rows as Processed (post-publish)

After publishing to MQ, ACE must mark those rows so they are not re-pulled.
Use an **MQInput → DatabaseRequest** downstream flow, or include an UPDATE
in a second compute node within the same XA transaction:

```esql
CREATE COMPUTE MODULE MarkAsProcessed
  CREATE FUNCTION Main() RETURNS BOOLEAN
  BEGIN
    -- Update status in Snowflake after successful MQ put
    SET OutputRoot.Database.Update.UPDATE_PENDING_ORDERS.STATUS       = 'DISPATCHED';
    SET OutputRoot.Database.Update.UPDATE_PENDING_ORDERS.PROCESSED_AT =
        CURRENT_TIMESTAMP;
    SET OutputRoot.Database.Update.UPDATE_PENDING_ORDERS.WHERE.ORDER_ID =
        InputRoot.JSON.Data.orderId;

    RETURN TRUE;
  END;
END MODULE;
```

---

## Part 3 — PUSH Pattern (MQ → Snowflake Bulk Load)

### 3.1  Flow: `SnowflakePushFlow.msgflow`

```
[MQInput] ──► [Aggregation] ──► [DatabaseRequest] ──► [MQOutput (ACK)]
 ORDER.IN      collect 500 msg     MERGE INTO             ORDER.PROCESSED
               or 10s window       Snowflake table
```

### 3.2  Aggregation Node Settings

| Property | Value |
|---|---|
| Aggregate type | Collection |
| Collection size | 500 |
| Collection timeout | 10000 ms |
| Aggregate control | On size or timeout |

### 3.3  ESQL — Build Batch MERGE Statement

```esql
CREATE COMPUTE MODULE BuildSnowflakeMerge
  CREATE FUNCTION Main() RETURNS BOOLEAN
  BEGIN
    DECLARE i INTEGER 1;
    DECLARE msgs REFERENCE TO InputRoot.ComIbmAggregateReplyBody;

    -- Build VALUES list for MERGE
    DECLARE valueList CHARACTER '';
    WHILE i <= CARDINALITY(msgs.msg[]) DO
      DECLARE m REFERENCE TO msgs.msg[i].JSON.Data;
      IF i > 1 THEN SET valueList = valueList || ','; END IF;
      SET valueList = valueList || '(''' || m.orderId    || ''','
                                        || '''' || m.customerId || ''','
                                        || '''' || m.product    || ''','
                                        || CAST(m.quantity  AS CHARACTER) || ','
                                        || CAST(m.unitPrice AS CHARACTER) || ','
                                        || '''RECEIVED'')';
      SET i = i + 1;
    END WHILE;

    SET OutputRoot.BLOB.BLOB = CAST(
      'MERGE INTO PROCESSED_ORDERS AS t USING (SELECT * FROM VALUES '
      || valueList
      || ' AS s(ORDER_ID,CUSTOMER_ID,PRODUCT,QUANTITY,UNIT_PRICE,STATUS))'
      || ' ON t.ORDER_ID = s.ORDER_ID'
      || ' WHEN MATCHED THEN UPDATE SET t.STATUS = s.STATUS'
      || ' WHEN NOT MATCHED THEN INSERT VALUES (s.ORDER_ID,s.CUSTOMER_ID,'
      ||   's.PRODUCT,s.QUANTITY,s.UNIT_PRICE,s.STATUS)'
      AS BLOB CCSID 1208);

    RETURN TRUE;
  END;
END MODULE;
```

### 3.4  Change-Data-Capture (CDC) Pattern

For near-real-time CDC from operational DBs into Snowflake via ACE:

```
Operational DB (change events)
        │
        ▼
  [MQInput ORDER.CHANGES]
        │
        ▼
  [Compute: classify INSERT/UPDATE/DELETE]
        │
     ┌──┴──────────┐
     ▼             ▼
 [DatabaseRequest] [DatabaseRequest]
  MERGE (I/U)     DELETE
        └──────────┘
                │
                ▼
      Snowflake ORDERS_DB.EVENTS table
```

---

## Part 4 — Connection Pooling & Performance Tuning

```yaml
# server.conf.yaml — JDBC tuning for Snowflake
JDBCProvider:
  SnowflakeDB:
    maxPoolSize: 10
    minPoolSize: 2
    connectionTimeout: 30000
    maxIdleTime: 600000
    statementCacheSize: 50
    # Snowflake-specific: use streaming result sets for large pulls
    additionalProperties: "jdbc_query_result_format=json"
```

---

## Exercises

1. **Exercise A** — Insert 10 rows with `STATUS='PENDING'` in Snowflake and trigger the pull flow with `curl http://localhost:7600/snowflake/pull`. Verify 10 messages arrive on `SNOWFLAKE.ORDERS.OUT`.
2. **Exercise B** — Send 600 messages to `ORDER.IN` and observe the aggregation node batching them into two MERGE calls (500 + 100).
3. **Exercise C** — Simulate a Snowflake connection drop (wrong password) and confirm the error lands on the Dead Letter Queue without losing data.
4. **Exercise D** — Extend the pull flow to use `CURRENT_TIMESTAMP` watermarking instead of a `STATUS` column.

---

## Key Concepts

| Concept | Description |
|---|---|
| **JDBC Provider Policy** | ACE policy that wraps a JDBC data source with pooling config |
| **DatabaseInput node** | Periodically executes a SELECT and emits one message per row |
| **DatabaseRequest node** | Executes a SQL statement mid-flow and propagates the result |
| **Aggregation** | ACE pattern to collect N messages into a single batch message |
| **MERGE** | Snowflake upsert statement — idempotent, safe for at-least-once delivery |
| **CDC** | Change-Data-Capture — capturing row-level changes for downstream replication |
