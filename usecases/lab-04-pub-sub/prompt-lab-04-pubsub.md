# Prompts — Lab 04: Pub/Sub Patterns with IBM MQ & ACE

> Copy any prompt below and paste it into your AI assistant.
> Replace values in `<angle brackets>` with your own details.

---

## 🔵 Conceptual Prompts

### C1 — MQ Pub/Sub vs Point-to-Point

```
I am learning IBM MQ publish/subscribe. Explain the fundamental difference
between point-to-point messaging (queues) and publish/subscribe (topics) in MQ.
Cover:
- How a topic tree differs from a queue in terms of routing behaviour
- What a subscription is and how MQ delivers a published message to all subscribers
- When to choose pub/sub over point-to-point (and vice versa)
- How IBM ACE flows participate in pub/sub as both publishers and subscribers
Use an order processing scenario to illustrate (publisher = order intake, subscribers = inventory, billing, analytics).
```

---

### C2 — Durable vs Non-Durable Subscriptions

```
In IBM MQ, what is the difference between a durable and non-durable subscription?
Explain:
- What happens to messages published while a non-durable subscriber is offline
- How MQ implements durable subscriptions (a backing local queue per sub)
- The trade-off: disk usage and backlog risk with durable subscriptions
- Which systems should always use durable subscriptions (financial, audit) vs
  which can use non-durable (dashboards, monitoring, real-time analytics)
- The BOTHRESH and MAXDEPTH settings to protect durable subscription queues
  from unbounded growth
```

---

### C3 — MQ Topic Tree Wildcards

```
Explain the IBM MQ topic tree wildcard characters # and +.
For a topic tree structured as ORDERS/REGION/<region>/<orderType>:
- What does ORDERS/# match?
- What does ORDERS/REGION/+/NEW match vs ORDERS/REGION/#?
- What does ORDERS/+/+/CANCEL match?
- What are the security implications of overly broad wildcard subscriptions?
- Can a publisher and subscriber use wildcards simultaneously?
Give 5 concrete subscription examples with explanations of what each matches.
```

---

### C4 — Fan-Out vs Pub/Sub

```
In IBM ACE integration design, when should I use MQ native pub/sub (topics +
durable subscriptions) vs implementing my own fan-out in an ACE flow
(set DestinationData[1..N] to multiple queue names)?

Compare the two approaches on:
- Decoupling (adding a new consumer requires change to ACE flow vs just adding a new sub)
- Persistence and durability guarantees
- Message filtering capability (wildcard subscriptions vs ESQL content-based routing)
- Operational complexity (managing subscriptions vs managing flow deployments)
- Use cases where each approach is clearly better
```

---

## 🟡 Implementation Prompts

### I1 — MQSC Topic Tree and Durable Subscriptions

```
Write MQSC commands to set up an MQ topic tree and durable subscriptions for
an order processing system on queue manager MQLAB. I need:

Topics:
- ORDERS.ROOT with topicstr 'ORDERS', durable subscriptions enabled, wildcard passthrough
- ORDERS.EMEA with topicstr 'ORDERS/REGION/EMEA'
- ORDERS.SAP with topicstr 'ORDERS/SAP'

Durable subscriptions:
- INVENTORY.ORDER.SUB → subscribes to 'ORDERS/#', destination INVENTORY.ORDERS.IN
- BILLING.ORDER.SUB → subscribes to 'ORDERS/#', destination BILLING.ORDERS.IN
- ANALYTICS.ORDER.SUB → subscribes to 'ORDERS/REGION/EMEA/#', destination ANALYTICS.ORDERS.IN

Destination queues:
- INVENTORY.ORDERS.IN, BILLING.ORDERS.IN, ANALYTICS.ORDERS.IN, SAP.ORDERS.IN
  all persistent, MAXDEPTH 1000000, QDEPTHHI at 900000 to trigger alerting

Also show ALTER QMGR QDEPTHHI(ENABLED) to activate the high-depth event.
```

---

### I2 — ESQL Publisher with Dynamic Topic String

```
Write an IBM ACE ESQL compute module PublisherEnrich for a flow that:
1. Receives a JSON order body with fields: region, type (PURCHASE/CANCEL/RETURN),
   customerId, product, quantity, unitPrice, totalValue
2. Adds publishedAt (ISO 8601) and messageId (UUID) to the JSON
3. Builds a dynamic MQ topic string: 'ORDERS/REGION/<REGION>/<TYPE>'
   where REGION and TYPE are uppercased
4. Sets OutputLocalEnvironment.Destination.MQ.Topic to the built string

Also show the MQOutput node settings needed to publish to a topic
(Destination mode = Topic, Persistence = Persistent) and explain what
happens if the topic string does not match any defined topic object in MQ.
```

---

### I3 — ESQL Content-Based Router

```
Write an IBM ACE ESQL compute module ContentRouter for a flow that subscribes
to the MQ wildcard topic 'ORDERS/#' and routes messages to multiple queues
based on content. Routing rules:
- INVENTORY.ORDERS.IN: always (all orders)
- ANALYTICS.ORDERS.IN: always (all orders)
- BILLING.ORDERS.IN: only if type = 'PURCHASE'
- SAP.ORDERS.IN: only if region = 'EMEA' AND type = 'PURCHASE' AND totalValue > 10000

Use OutputLocalEnvironment.Destination.MQ.DestinationData[] for multi-destination.
Show how ACE sends a single message to multiple queues in one PROPAGATE.
Also explain what happens if no DestinationData entries are set (is the message dropped?).
```

---

### I4 — ESQL Fan-Out to Fixed Destinations

```
Write an IBM ACE ESQL compute module FanOut that unconditionally copies one
inbound message from SOURCE.EVENTS queue to four downstream queues:
SYS.A.IN, SYS.B.IN, SYS.C.IN, SYS.D.IN.

Then extend it to:
1. Add a fan-out sequence number to each copy (e.g., fanOutSeq = 1..4)
2. Set a different MQMD.Priority per destination (SYS.A.IN gets priority 9)
3. Route to SYS.D.IN only if Environment.featureFlag.sysD = TRUE

Show the complete ESQL and explain the difference between using DestinationData[]
vs PROPAGATE TO TERMINAL for fan-out.
```

---

### I5 — Backlog Management for Durable Subscriptions

```
My durable MQ subscription queue INVENTORY.ORDERS.IN has grown to 800,000
messages because the inventory system is processing slowly. I need to:
1. Monitor the depth and alert before it hits MAXDEPTH
2. Temporarily pause publishing to the ORDERS topic without losing messages
3. Resume processing safely

Show:
- The MQSC commands to check queue depth, MAXDEPTH, and QDEPTHHI events
- How to pause a topic (SUSPEND) without dropping in-flight messages
- How an ACE operational dashboard flow could subscribe to MQ events
  and POST a Slack/Teams alert when depth exceeds 90%
- Best practices for sizing MAXDEPTH on durable subscription queues
```

---

### I6 — Adding a New Subscriber Without Changing the Publisher

```
I have a running pub/sub system with ORDERS topic and 3 durable subscribers.
I need to add a new COMPLIANCE subscriber without changing any ACE publisher
flow or existing subscriber flows. Requirements:
- New subscription: COMPLIANCE.ORDERS.IN, subscribes to 'ORDERS/REGION/EMEA/#'
- It should receive all past messages that are still on existing queues (replay)
- It should receive all future published messages

Show:
1. The MQSC DEFINE SUB command for the new subscription
2. Whether historical messages (already consumed by other subscribers) can be
   replayed to the new subscriber — and if not, what the alternatives are
3. How to verify the new subscription is active using DISPLAY SUB(*)
```

---

## 🔴 Troubleshooting Prompts

### T1 — Messages Not Reaching Durable Subscriber

```
I defined a durable subscription BILLING.ORDER.SUB pointing to BILLING.ORDERS.IN.
I publish 10 messages to the ORDERS/REGION/EMEA/NEW topic, but BILLING.ORDERS.IN
has 0 messages. The queue exists and is empty. Where should I start diagnosing?

Walk me through the MQ diagnostic steps:
1. Verifying the subscription is active (DISPLAY SUB command)
2. Checking the topic string in the SUB matches the published topic string exactly
3. Verifying the TOPICOBJ in the SUB exists and has DURSUB(ENABLED)
4. Checking authority records (setmqaut) for the publishing and subscribing channels
5. What SYSTEM.FTE or SYSTEM.BROKER topics could interfere
```

---

### T2 — Publisher Receives MQRC_UNKNOWN_ALIAS_BASE_Q

```
My ACE MQOutput node set to publish to topic 'ORDERS/REGION/EMEA/NEW' throws:
  MQRC 2082: MQRC_UNKNOWN_ALIAS_BASE_Q

The topic ORDERS.EMEA is defined with TOPICSTR('ORDERS/REGION/EMEA').
What does this error mean in the context of pub/sub, and what MQ configuration
is missing? Walk me through creating a topic object with the correct TOPICSTR
and verifying it resolves correctly with DISPLAY TOPIC(*) STATUS.
```

---

### T3 — Wildcard Subscription Receiving Wrong Messages

```
I created a subscription with TOPICSTR('ORDERS/REGION/EMEA/#') expecting to
receive only EMEA regional orders. But I am also receiving messages published
to 'ORDERS/REGION/APAC/NEW'. This seems wrong.

Walk me through debugging wildcard subscription matching in IBM MQ:
- How to use DISPLAY SUB to see the effective topic string
- Whether ORDERS/REGION/EMEA/# could match ORDERS/REGION/APAC/NEW (it shouldn't)
- Whether there is another subscription active that is feeding APAC messages
  to the same destination queue
- How to trace which published message is being routed to which subscription
  using MQ trace or runmqsc DISPLAY QSTATUS
```

---

### T4 — Fan-Out Flow Only Sends to First Destination

```
My ACE FanOut compute module sets DestinationData[1], [2], [3], [4] and
the MQOutput node is configured for "List of queues". But only DestinationData[1]
receives messages — the others are empty.

What are the common configuration mistakes that cause this:
1. MQOutput node "Destination mode" setting
2. Whether all 4 queues exist on the queue manager
3. Whether PUT authority is granted on all 4 queues for the ACE service account
4. Whether the ESQL array indexing starts at 1 or 0
5. How to use the ACE Flow Exerciser to inspect OutputLocalEnvironment.Destination
   after the compute module runs to verify all 4 entries are set
```

---

### T5 — Non-Durable Subscriber Missing Messages After Restart

```
My analytics ACE flow uses a non-durable MQ subscription to ORDERS/#.
After a planned ACE server restart for maintenance (30 minutes), I noticed
we missed approximately 2,400 published messages during the downtime.
This is acceptable for analytics but I now need to understand the exact
message delivery semantics to document them for the business.

Explain:
- Exactly when does a non-durable subscription stop receiving messages
  (at MQInput node disconnect or at ACE server shutdown?)
- Can messages published during downtime ever be recovered for a non-durable subscriber?
- What would I need to change to make this subscriber durable without impacting
  the existing publisher flows?
- How to estimate the required MAXDEPTH if we convert to durable (given
  30 min downtime and 80 messages/second publish rate)
```
