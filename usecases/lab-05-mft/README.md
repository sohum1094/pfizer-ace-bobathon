# Lab 05 — MFT Integration with ACE Flows

## Overview

IBM **Managed File Transfer (MFT)** handles reliable, audited file movement
between systems. ACE integrates with MFT through:

1. **MFT → ACE** — MFT emits transfer completion events to an MQ queue; ACE consumes them to trigger downstream processing.
2. **ACE → MFT** — ACE calls MFT agent APIs (via MQ command queues) to initiate transfers.

```
FILE ARRIVES ON SFTP SERVER
        │
        ▼
MFT Agent picks up file ──► transfers to destination
        │
        ▼
MFT publishes TransferComplete event to SYSTEM.FTE topic
        │
        ▼
[ACE MQInput — FTE.EVENTS queue]
        │
        ▼
[Parse XML event] ──► [Route on outcome] ──► [Trigger business flow]
                              │
                    ┌─────────┴─────────┐
                    ▼                   ▼
             SUCCESS path           FAILURE path
             [process file]     [alert + retry request]
```

---

## Prerequisites

| Requirement | Notes |
|---|---|
| IBM MQ MFT (or WMQFTE) | Installed and configured with at least one agent |
| Base lab MQ running | Queue manager MQLAB |
| ACE 13 | From parent lab |

---

## Part 1 — MFT Configuration

### 1.1  Create MFT Coordination Queue Manager Config

```bash
# On the MFT coordination server
fteSetupCoordination -coordinationQMgr MQLAB \
  -coordinationQMgrHost localhost \
  -coordinationQMgrPort 1414 \
  -coordinationQMgrChannel LAB.SVRCONN \
  -f
```

### 1.2  Create Source and Destination Agents

```bash
# Source agent (reads from SFTP / local filesystem)
fteCreateAgent -agentName SOURCE_AGENT \
  -agentQMgr MQLAB \
  -agentQMgrHost localhost \
  -agentQMgrPort 1414 \
  -agentQMgrChannel LAB.SVRCONN

# Destination agent (writes to target directory)
fteCreateAgent -agentName DEST_AGENT \
  -agentQMgr MQLAB \
  -agentQMgrHost localhost \
  -agentQMgrPort 1414 \
  -agentQMgrChannel LAB.SVRCONN
```

### 1.3  Create ACE Event Subscription Queue

```mqsc
* Queue to receive MFT transfer log events
DEFINE QLOCAL(FTE.EVENTS) +
  DEFPSIST(YES) +
  MAXDEPTH(100000) +
  REPLACE

* Durable subscription to MFT system topic
DEFINE SUB(ACE.FTE.SUB) +
  TOPICSTR('SYSTEM/FTE/Log/MQLAB/SOURCE_AGENT') +
  DEST(FTE.EVENTS) +
  DURABLE(YES) +
  REPLACE
```

---

## Part 2 — ACE Flow: Consume MFT Transfer Events

### 2.1  Flow: `MFTEventConsumer.msgflow`

```
[MQInput FTE.EVENTS]
        │
        ▼
[XMLParser — parse MFT transfer log XML]
        │
        ▼
[Compute: extract outcome + filename + timestamps]
        │
        ▼
[Route on outcome]
        │
   ┌────┴────┐
   ▼         ▼
SUCCESS   FAILED/PARTIAL
   │         │
Process    Alert + maybe
 file      re-request
   │
   ▼
[MQOutput PROCESSED.FILES.IN]
```

### 2.2  MFT Transfer Log XML Structure

A typical `TransferLog` event from `SYSTEM/FTE`:

```xml
<transaction version="1.00" ID="414d51204d514c414220202020202020..." >
  <action time="2024-07-15T10:30:00Z">progress</action>
  <sourceAgent agent="SOURCE_AGENT" QMgr="MQLAB" />
  <destinationAgent agent="DEST_AGENT" QMgr="MQLAB" />
  <transferSet bytesTransferred="204800" >
    <item mode="binary" result="success" >
      <source recursive="false">
        <file size="204800">/inbound/orders_20240715.csv</file>
      </source>
      <destination type="file" exist="overwrite">
        <file>/processed/orders_20240715.csv</file>
      </destination>
    </item>
  </transferSet>
  <status resultCode="0">
    <supplement>BFGRP0032I: file transfer has completed successfully.</supplement>
  </status>
</transaction>
```

### 2.3  ESQL — Parse MFT Transfer Log

```esql
CREATE COMPUTE MODULE ParseMFTEvent
  CREATE FUNCTION Main() RETURNS BOOLEAN
  BEGIN
    DECLARE txn REFERENCE TO InputRoot.XMLNSC.transaction;

    -- Extract key fields
    DECLARE outcome CHARACTER;
    IF txn.status.resultCode = '0' THEN
      SET outcome = 'SUCCESS';
    ELSE
      SET outcome = 'FAILED';
    END IF;

    SET OutputRoot.JSON.Data.transferId    = txn.-ID;
    SET OutputRoot.JSON.Data.outcome       = outcome;
    SET OutputRoot.JSON.Data.resultCode    = txn.status.resultCode;
    SET OutputRoot.JSON.Data.supplement    = txn.status.supplement;
    SET OutputRoot.JSON.Data.sourceFile    = txn.transferSet.item.source.file;
    SET OutputRoot.JSON.Data.destFile      = txn.transferSet.item.destination.file;
    SET OutputRoot.JSON.Data.bytesXferred  = txn.transferSet.-bytesTransferred;
    SET OutputRoot.JSON.Data.eventTime     = txn.action.-time;

    -- Store outcome for routing
    SET OutputLocalEnvironment.Transfer.outcome = outcome;
    SET OutputLocalEnvironment.Transfer.filename =
        txn.transferSet.item.source.file;

    RETURN TRUE;
  END;
END MODULE;
```

### 2.4  ESQL — Route on Transfer Outcome

```esql
CREATE COMPUTE MODULE RouteOnOutcome
  CREATE FUNCTION Main() RETURNS BOOLEAN
  BEGIN
    SET OutputRoot = InputRoot;

    IF InputLocalEnvironment.Transfer.outcome = 'SUCCESS' THEN
      -- Forward to the file-processing pipeline
      SET OutputLocalEnvironment.Destination.MQ.DestinationData[1].queueName
          = 'FILE.PROCESSING.IN';
    ELSE
      -- Route to alert queue; include full event for diagnosis
      SET OutputLocalEnvironment.Destination.MQ.DestinationData[1].queueName
          = 'FILE.TRANSFER.ALERTS';
    END IF;

    RETURN TRUE;
  END;
END MODULE;
```

---

## Part 3 — ACE Flow: Initiate MFT Transfer

### 3.1  ACE Initiates a File Transfer via MFT Command

ACE can trigger MFT transfers by putting an XML request to the agent's
command queue (`SYSTEM.FTE.COMMAND.SOURCE_AGENT`):

### 3.2  ESQL — Build Transfer Request XML

```esql
CREATE COMPUTE MODULE BuildMFTRequest
  CREATE FUNCTION Main() RETURNS BOOLEAN
  BEGIN
    DECLARE filename CHARACTER InputRoot.JSON.Data.filename;
    DECLARE destPath CHARACTER InputRoot.JSON.Data.destinationPath;

    -- Build MFT XML transfer request
    SET OutputRoot.XMLNSC.transferRequest.-version  = '1.00';
    SET OutputRoot.XMLNSC.transferRequest.-ID       = UUIDASCHAR;

    SET OutputRoot.XMLNSC.transferRequest.sourceAgent.-agent   = 'SOURCE_AGENT';
    SET OutputRoot.XMLNSC.transferRequest.sourceAgent.-QMgr    = 'MQLAB';
    SET OutputRoot.XMLNSC.transferRequest.destAgent.-agent     = 'DEST_AGENT';
    SET OutputRoot.XMLNSC.transferRequest.destAgent.-QMgr      = 'MQLAB';

    SET OutputRoot.XMLNSC.transferRequest.transferSet.item.source.file =
        '/outbound/' || filename;
    SET OutputRoot.XMLNSC.transferRequest.transferSet.item.destination.file =
        destPath || '/' || filename;
    SET OutputRoot.XMLNSC.transferRequest.transferSet.item.-mode = 'binary';

    -- Route to MFT command queue
    SET OutputLocalEnvironment.Destination.MQ.DestinationData[1].queueName
        = 'SYSTEM.FTE.COMMAND.SOURCE_AGENT';

    RETURN TRUE;
  END;
END MODULE;
```

---

## Part 4 — File-Complete Trigger Pattern

A common challenge: process a file **only after all chunks arrive**.
MFT can be configured to write a trigger file when a batch is complete:

```
MFT transfers: orders_part1.csv, orders_part2.csv, orders_part3.csv
then transfers: orders.COMPLETE marker file

ACE watches for *.COMPLETE files and only then starts processing.
```

```esql
CREATE COMPUTE MODULE CheckFileComplete
  CREATE FUNCTION Main() RETURNS BOOLEAN
  BEGIN
    DECLARE filename CHARACTER InputLocalEnvironment.Transfer.filename;

    IF RIGHT(filename, 9) = '.COMPLETE' THEN
      -- Extract batch name
      DECLARE batchName CHARACTER
          LEFT(filename, LENGTH(filename) - 9);
      SET OutputRoot.JSON.Data.batchName = batchName;
      SET OutputRoot.JSON.Data.readyToProcess = TRUE;
      PROPAGATE TO TERMINAL 'out1';  -- trigger processing
    ELSE
      -- Regular file chunk — just acknowledge receipt
      PROPAGATE TO TERMINAL 'out2';
    END IF;

    RETURN FALSE;
  END;
END MODULE;
```

---

## Part 5 — Audit Trail

MFT maintains a full audit log in the coordination database.
ACE flows should augment this with business-level tracking:

```mqsc
* Dedicated audit queue
DEFINE QLOCAL(FILE.AUDIT.LOG) +
  DEFPSIST(YES) +
  MAXDEPTH(1000000) +
  REPLACE
```

```esql
-- After each successful file processing, emit audit record
CREATE COMPUTE MODULE EmitAuditRecord
  CREATE FUNCTION Main() RETURNS BOOLEAN
  BEGIN
    SET OutputRoot.JSON.Data.auditType     = 'FILE_PROCESSED';
    SET OutputRoot.JSON.Data.filename      = InputRoot.JSON.Data.filename;
    SET OutputRoot.JSON.Data.recordCount   = Environment.processedCount;
    SET OutputRoot.JSON.Data.processedAt   =
        CAST(CURRENT_TIMESTAMP AS CHARACTER FORMAT 'IU');
    SET OutputRoot.JSON.Data.flowServer    =
        InputLocalEnvironment.ComIbmIntegrationServerLabel;
    SET OutputLocalEnvironment.Destination.MQ.DestinationData[1].queueName
        = 'FILE.AUDIT.LOG';
    RETURN TRUE;
  END;
END MODULE;
```

---

## Exercises

1. **Exercise A** — Drop a file in the source agent's monitored directory; watch it transfer and verify the `FTE.EVENTS` queue receives the completion event.
2. **Exercise B** — Trigger the `MFTEventConsumer` flow with a fabricated `resultCode=2` event; confirm the message routes to `FILE.TRANSFER.ALERTS`.
3. **Exercise C** — Use the ACE Flow Exerciser to send a JSON payload to `BuildMFTRequest`; inspect the XML placed on `SYSTEM.FTE.COMMAND.SOURCE_AGENT`.
4. **Exercise D** — Transfer 3 part files followed by a `.COMPLETE` marker; verify `CheckFileComplete` only fires once, on the marker file.

---

## Key Concepts

| Concept | Description |
|---|---|
| **MFT agent** | Process that manages file transfer on one endpoint |
| **Coordination QM** | MQ queue manager that stores MFT audit database and routes commands |
| **SYSTEM.FTE topic** | MFT publishes all transfer events here in XML format |
| **Transfer log** | XML document describing outcome of each file transfer |
| **Command queue** | `SYSTEM.FTE.COMMAND.<agent>` — ACE sends transfer requests here |
| **File-complete trigger** | Pattern using a sentinel marker file to signal batch readiness |
