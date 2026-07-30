# Lab 04 — Pub/Sub Patterns with IBM MQ & ACE

## Overview

IBM MQ's **publish/subscribe** engine allows multiple consumers to receive
the same message independently, without coupling producers to consumers.  
ACE acts as both publisher and subscriber inside integration flows.

```
                    ┌──────────────────────────────────┐
                    │         IBM MQ Topic Tree         │
                    │  ORDERS/REGION/EMEA/NEW           │
                    └──────────────────────────────────┘
                                    ▲
                    ┌───────────────┘
                    │  ACE Publisher flow
                    │  (HTTP → enrich → MQPUT to topic)

         ┌──────────┬──────────────┬──────────────┐
         ▼          ▼              ▼              ▼
  Subscriber 1  Subscriber 2  Subscriber 3   ACE Router
  Inventory     Billing       Analytics      (content-based)
  (durable)     (durable)     (non-durable)   ↓ ORDERS/SAP
```

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Base lab MQ running | Queue manager MQLAB with topic engine enabled |
| ACE 13 installed | From parent lab |

---

## Part 1 — MQ Topic Configuration

### 1.1  Create Topic Objects

```mqsc
* Root topic for all order events
DEFINE TOPIC(ORDERS.ROOT) +
  TOPICSTR('ORDERS') +
  DURSUB(ENABLED) +
  WILDCARD(PASSTHRU) +
  REPLACE

* Regional sub-topic
DEFINE TOPIC(ORDERS.EMEA) +
  TOPICSTR('ORDERS/REGION/EMEA') +
  DURSUB(ENABLED) +
  REPLACE

* Topic for SAP-bound messages (filtered by ACE)
DEFINE TOPIC(ORDERS.SAP) +
  TOPICSTR('ORDERS/SAP') +
  DURSUB(ENABLED) +
  REPLACE
```

### 1.2  Create Durable Subscriptions

```mqsc
* Durable subscription for Inventory system
DEFINE SUB(INVENTORY.ORDER.SUB) +
  TOPICOBJ(ORDERS.ROOT) +
  TOPICSTR('ORDERS/#') +
  DEST(INVENTORY.ORDERS.IN) +
  DURABLE(YES) +
  REPLACE

* Durable subscription for Billing system
DEFINE SUB(BILLING.ORDER.SUB) +
  TOPICOBJ(ORDERS.ROOT) +
  TOPICSTR('ORDERS/#') +
  DEST(BILLING.ORDERS.IN) +
  DURABLE(YES) +
  REPLACE

* Create destination queues
DEFINE QLOCAL(INVENTORY.ORDERS.IN) DEFPSIST(YES) REPLACE
DEFINE QLOCAL(BILLING.ORDERS.IN)   DEFPSIST(YES) REPLACE
DEFINE QLOCAL(ANALYTICS.ORDERS.IN) DEFPSIST(YES) REPLACE
DEFINE QLOCAL(SAP.ORDERS.IN)       DEFPSIST(YES) REPLACE
```

---

## Part 2 — Publisher Flow (HTTP → MQ Topic)

### 2.1  Flow: `OrderPublisherFlow.msgflow`

```
[HTTPInput /orders/publish]
        │
        ▼
[Compute: enrich + build topic string]
        │
        ▼
[MQOutput — publish to topic]
        │
        ▼
[HTTPReply 202 Accepted]
```

### 2.2  ESQL — Build Dynamic Topic String

```esql
CREATE COMPUTE MODULE PublisherEnrich
  CREATE FUNCTION Main() RETURNS BOOLEAN
  BEGIN
    SET OutputRoot = InputRoot;

    DECLARE region  CHARACTER InputRoot.JSON.Data.region;
    DECLARE orderType CHARACTER InputRoot.JSON.Data.type;

    -- Add metadata
    SET OutputRoot.JSON.Data.publishedAt =
        CAST(CURRENT_TIMESTAMP AS CHARACTER FORMAT 'IU');
    SET OutputRoot.JSON.Data.messageId = UUIDASCHAR;

    -- Build topic string dynamically
    -- e.g. ORDERS/REGION/EMEA/NEW  or  ORDERS/REGION/APAC/CANCEL
    SET OutputLocalEnvironment.Destination.MQ.Topic =
        'ORDERS/REGION/' || UPPER(region) || '/' || UPPER(orderType);

    RETURN TRUE;
  END;
END MODULE;
```

**MQOutput node settings:**

| Property | Value |
|---|---|
| Connection | MQ connection policy |
| Destination mode | Topic |
| Topic string | (set dynamically in ESQL above) |
| Persistence | Persistent |

---

## Part 3 — Content-Based Routing Subscriber

### 3.1  Flow: `ContentBasedRouter.msgflow`

This ACE flow subscribes to `ORDERS/#` (all orders) and routes based on
message content — a common pattern to decouple consumers from having to
know the topic hierarchy.

```
[MQInput — ORDERS.ROOT wildcard subscription]
        │
        ▼
[Compute: read region + orderType]
        │
  ┌─────┴──────┬──────────┬──────────┐
  ▼            ▼          ▼          ▼
SAP         Inventory   Billing  Analytics
orders      (all)       (all)    (all)
REGION=EU
type=PURCHASE
```

### 3.2  ESQL — Content-Based Route

```esql
CREATE COMPUTE MODULE ContentRouter
  CREATE FUNCTION Main() RETURNS BOOLEAN
  BEGIN
    SET OutputRoot = InputRoot;

    DECLARE region    CHARACTER InputRoot.JSON.Data.region;
    DECLARE orderType CHARACTER InputRoot.JSON.Data.type;

    -- Always send to Inventory and Analytics
    SET OutputLocalEnvironment.Destination.MQ.DestinationData[1].queueName
        = 'INVENTORY.ORDERS.IN';
    SET OutputLocalEnvironment.Destination.MQ.DestinationData[2].queueName
        = 'ANALYTICS.ORDERS.IN';

    -- Send to Billing only for PURCHASE orders
    IF orderType = 'PURCHASE' THEN
      SET OutputLocalEnvironment.Destination.MQ.DestinationData[3].queueName
          = 'BILLING.ORDERS.IN';
    END IF;

    -- Send to SAP only for EU PURCHASE orders above threshold
    IF region = 'EMEA' AND orderType = 'PURCHASE'
       AND InputRoot.JSON.Data.totalValue > 10000 THEN
      SET OutputLocalEnvironment.Destination.MQ.DestinationData[4].queueName
          = 'SAP.ORDERS.IN';
    END IF;

    RETURN TRUE;
  END;
END MODULE;
```

---

## Part 4 — Fan-Out Pattern

### 4.1  Flow: `FanOutPublisher.msgflow`

When the same message must reach **all** registered systems without them
subscribing directly to MQ topics, ACE can fan-out via a single flow:

```
[MQInput SOURCE.EVENTS]
        │
        ▼
[Compute: clone to N destinations]
        │
  ┌─────┴──────┬──────────┬──────────┐
  ▼            ▼          ▼          ▼
SYS.A.IN   SYS.B.IN  SYS.C.IN  SYS.D.IN
```

```esql
CREATE COMPUTE MODULE FanOut
  CREATE FUNCTION Main() RETURNS BOOLEAN
  BEGIN
    SET OutputRoot = InputRoot;

    -- Define all fan-out destinations
    SET OutputLocalEnvironment.Destination.MQ.DestinationData[1].queueName
        = 'SYS.A.IN';
    SET OutputLocalEnvironment.Destination.MQ.DestinationData[2].queueName
        = 'SYS.B.IN';
    SET OutputLocalEnvironment.Destination.MQ.DestinationData[3].queueName
        = 'SYS.C.IN';
    SET OutputLocalEnvironment.Destination.MQ.DestinationData[4].queueName
        = 'SYS.D.IN';

    RETURN TRUE;
  END;
END MODULE;
```

---

## Part 5 — Durable vs Non-Durable Subscriptions

| Feature | Durable | Non-Durable |
|---|---|---|
| Messages retained while offline | ✅ Yes | ❌ No — missed |
| Suitable for financial/audit systems | ✅ | ❌ |
| Suitable for dashboards / real-time only | ✅ (wasteful) | ✅ |
| MQ queue backs the subscription | ✅ | ❌ |
| Configuration | `DEFINE SUB … DURABLE(YES)` | `DEFINE SUB … DURABLE(NO)` |

### 5.1  Backlog Management for Durable Subs

```mqsc
* Cap backlog per subscription queue to avoid disk fill
ALTER QLOCAL(INVENTORY.ORDERS.IN) +
  MAXDEPTH(1000000) +
  QDEPTHHI(900000)   * Trigger alert at 90%

* Set high-depth event
ALTER QMGR QDEPTHHI(ENABLED)
```

---

## Part 6 — Wildcard Subscriptions

IBM MQ supports two wildcard characters:

| Wildcard | Meaning | Example |
|---|---|---|
| `#` | Multi-level — any topic levels | `ORDERS/#` matches `ORDERS/REGION/EMEA/NEW` |
| `+` | Single-level | `ORDERS/+/NEW` matches `ORDERS/EMEA/NEW` but not `ORDERS/REGION/EMEA/NEW` |

```mqsc
* Subscribe to all EMEA events at any depth
DEFINE SUB(EMEA.ALL.SUB) +
  TOPICSTR('ORDERS/REGION/EMEA/#') +
  DEST(EMEA.ALL.IN) +
  DURABLE(YES) +
  REPLACE

* Subscribe to NEW orders only, one level deep
DEFINE SUB(NEW.ORDERS.SUB) +
  TOPICSTR('ORDERS/+/NEW') +
  DEST(NEW.ORDERS.IN) +
  DURABLE(YES) +
  REPLACE
```

---

## Exercises

1. **Exercise A** — Publish 5 orders with `region=EMEA` and 5 with `region=APAC`. Verify both `INVENTORY.ORDERS.IN` and `ANALYTICS.ORDERS.IN` have 10 messages each, while `SAP.ORDERS.IN` has only the high-value EMEA ones.
2. **Exercise B** — Stop the Billing subscriber flow, publish 10 PURCHASE orders, restart it; verify all 10 are delivered (durable subscription retained them).
3. **Exercise C** — Add a new subscriber `COMPLIANCE.ORDERS.IN` for the `ORDERS/REGION/EMEA/#` wildcard; replay existing messages to verify it receives them retroactively.
4. **Exercise D** — Modify the content-based router to also filter on `totalValue > 5000` for Billing, and re-run Exercise A.

---

## Key Concepts

| Concept | Description |
|---|---|
| **Topic tree** | Hierarchical string namespace for pub/sub routing in MQ |
| **Durable subscription** | Subscription backed by a queue — persists while subscriber is offline |
| **Wildcard `#`** | Matches zero or more topic levels — broadest subscription |
| **Content-based routing** | Routing based on message content rather than topic alone |
| **Fan-out** | Single publisher → multiple consumers via one ACE flow |
