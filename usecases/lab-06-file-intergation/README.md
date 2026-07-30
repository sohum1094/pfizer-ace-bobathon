# Lab 06 — File-Based Integration (SFTP / S3 / Azure Blob)

## Overview

ACE handles file-based integration through:
- **SFTP** via the built-in SFTP connector or FileInput node  
- **AWS S3** via the AWS S3 connector (ACE 12+)  
- **Azure Blob Storage** via the Azure Blob connector  
- **Large file processing** with streaming, splitting, and aggregation patterns  

```
INBOUND
────────────────────────────────────────────────────────────────
[SFTP / S3 / Azure Blob] ──► [ACE File/Cloud Connector]
                                        │
                              ┌─────────┴─────────┐
                              ▼                   ▼
                         Small files          Large files
                         parse whole        stream + split
                              │                   │
                              └──────────┬─────────┘
                                         ▼
                                  [Transform + Validate]
                                         │
                                         ▼
                                  [MQ / DB / API]

OUTBOUND
────────────────────────────────────────────────────────────────
[MQ / DB] ──► [Aggregate] ──► [Format CSV/JSON/XML]
                                      │
                                      ▼
                          [Write to SFTP / S3 / Azure Blob]
```

---

## Prerequisites

| Requirement | Notes |
|---|---|
| SFTP server | `docker run -p 2222:22 atmoz/sftp user:pass:::upload` |
| AWS account + S3 bucket | Free tier is sufficient |
| Azure Storage account + container | Free tier is sufficient |
| ACE 13 | ACE 12.0.4+ recommended for cloud connectors |

---

## Part 1 — SFTP Integration

### 1.1  SFTP Policy

Create `ace-config/SFTPEndpointPolicy.policyxml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<policies>
  <policy policyType="SFTPServerPolicy"
          policyName="LabSFTP"
          policyVersion="1">
    <properties>
      <remoteHost>localhost</remoteHost>
      <remotePort>2222</remotePort>
      <remoteDirectory>/upload</remoteDirectory>
      <filePattern>*.csv</filePattern>
      <credentials>LabSFTPCreds</credentials>
    </properties>
  </policy>
</policies>
```

```bash
mqsisetdbparms ACE_LAB_SERVER \
  -n LabSFTPCreds::username -u user -p pass
```

### 1.2  Flow: `SFTPInboundFlow.msgflow`

```
[FileInput — polls SFTP every 30s] ──► [CSVParser] ──► [MQOutput]
```

**FileInput node settings:**

| Property | Value |
|---|---|
| Policy | `{default}:LabSFTP` |
| Directory | `/upload` |
| Filter | `orders_*.csv` |
| Post-read action | Move to `/processed` |
| Record detection | Fixed length / CSV |

---

## Part 2 — AWS S3 Integration

### 2.1  S3 Policy

```xml
<?xml version="1.0" encoding="UTF-8"?>
<policies>
  <policy policyType="AmazonS3"
          policyName="LabS3"
          policyVersion="1">
    <properties>
      <region>us-east-1</region>
      <bucketName>ace-lab-orders</bucketName>
      <accessKeyId>{{AWS_ACCESS_KEY}}</accessKeyId>
      <secretAccessKey>{{AWS_SECRET_KEY}}</secretAccessKey>
    </properties>
  </policy>
</policies>
```

### 2.2  PULL: Read from S3

```
[S3Input — event trigger or poll] ──► [Compute] ──► [MQOutput]
        new-object event
        from SNS/SQS
```

**S3Input node:** configure with `{default}:LabS3`, Object key prefix `inbound/orders/`.

### 2.3  PUSH: Write to S3

```esql
CREATE COMPUTE MODULE BuildS3OutputPath
  CREATE FUNCTION Main() RETURNS BOOLEAN
  BEGIN
    SET OutputRoot = InputRoot;

    -- Build date-partitioned S3 key
    DECLARE today CHARACTER
        CAST(CURRENT_DATE AS CHARACTER FORMAT 'yyyyMMdd');

    SET OutputLocalEnvironment.S3.ObjectKey =
        'processed/orders/' || today || '/'
        || InputRoot.JSON.Data.orderId || '.json';

    SET OutputLocalEnvironment.S3.ContentType = 'application/json';

    RETURN TRUE;
  END;
END MODULE;
```

---

## Part 3 — Azure Blob Storage Integration

### 3.1  Azure Blob Policy

```xml
<?xml version="1.0" encoding="UTF-8"?>
<policies>
  <policy policyType="AzureBlobStorage"
          policyName="LabAzureBlob"
          policyVersion="1">
    <properties>
      <storageAccountName>acelabstorage</storageAccountName>
      <containerName>orders</containerName>
      <connectionString>{{AZURE_STORAGE_CONN_STR}}</connectionString>
    </properties>
  </policy>
</policies>
```

### 3.2  PULL: Trigger on New Blob

Azure uses Event Grid → Service Bus → ACE to trigger on new blobs:

```
Azure Blob Storage ──► Event Grid ──► Azure Service Bus Queue
                                               │
                                               ▼
                              ACE [ServiceBusInput] reads event
                                               │
                                    parse blob path from event
                                               │
                                    [AzureBlobRequest] download
                                               │
                                          process file
```

### 3.3  ESQL — Parse Azure Event Grid Notification

```esql
CREATE COMPUTE MODULE ParseBlobEvent
  CREATE FUNCTION Main() RETURNS BOOLEAN
  BEGIN
    -- Azure Event Grid schema
    DECLARE evt REFERENCE TO InputRoot.JSON.Data;

    SET OutputRoot.JSON.Data.blobName    = evt.subject;
    SET OutputRoot.JSON.Data.eventType   = evt.eventType;
    SET OutputRoot.JSON.Data.contentType = evt.data.contentType;
    SET OutputRoot.JSON.Data.blobUrl     = evt.data.url;
    SET OutputRoot.JSON.Data.blobSize    = evt.data.contentLength;

    RETURN TRUE;
  END;
END MODULE;
```

---

## Part 4 — Large File Processing

### 4.1  Streaming CSV Processing

Never load a full large file into memory. Use ACE's record-by-record
streaming with a **FileInput** node configured for line-by-line reading:

```
[FileInput — record=line] ──► [CSVParse] ──► [Validate] ──► [MQOutput]
        emits 1 msg
        per CSV line
```

**FileInput node — key settings for large files:**

| Property | Value |
|---|---|
| Record detection | Delimited — `\n` |
| Maximum record size | 65535 bytes |
| Persist across restart | Yes |
| In-progress suffix | `.inprogress` |

### 4.2  XML Streaming with XMLParser

For large XML files, switch to **streaming mode** to avoid loading the
full DOM into memory:

```
[FileInput] ──► [XMLParser — streaming] ──► [XPath extract] ──► [MQOutput]
```

In the `XMLParser` node, set **Parse timing** to `On demand` and use
XPath to extract only the elements needed.

### 4.3  ESQL — CSV Line Parser

```esql
CREATE COMPUTE MODULE ParseCSVLine
  CREATE FUNCTION Main() RETURNS BOOLEAN
  BEGIN
    -- Each message body is one raw CSV line
    DECLARE line CHARACTER
        CAST(InputRoot.BLOB.BLOB AS CHARACTER CCSID 1208);

    -- Skip header row
    IF LEFT(line, 8) = 'order_id' THEN RETURN FALSE; END IF;

    -- Tokenize (basic CSV — no quoted commas)
    DECLARE fields CHARACTER[] = STRTOK_LIST(line, ',');

    SET OutputRoot.JSON.Data.orderId    = TRIM(fields[1]);
    SET OutputRoot.JSON.Data.customerId = TRIM(fields[2]);
    SET OutputRoot.JSON.Data.product    = TRIM(fields[3]);
    SET OutputRoot.JSON.Data.quantity   = CAST(TRIM(fields[4]) AS INTEGER);
    SET OutputRoot.JSON.Data.unitPrice  = CAST(TRIM(fields[5]) AS DECIMAL);
    SET OutputRoot.JSON.Data.lineNumber = InputLocalEnvironment.File.RecordIndex;

    RETURN TRUE;
  END;
END MODULE;
```

---

## Part 5 — File Splitting, Aggregation & Sequencing

### 5.1  Splitting — One File → N Messages

```
[FileInput large_orders.csv]     1 msg per line
        │
        ▼ (stream)
[Compute: assign sequence number]  adds msg.seq, msg.total
        │
        ▼
[MQOutput ORDER.LINES.IN]
```

```esql
SET OutputRoot.JSON.Data.sequence =
    InputLocalEnvironment.File.RecordIndex;
SET OutputRoot.JSON.Data.sourceFile =
    InputLocalEnvironment.File.Name;
SET OutputRoot.MQMD.MsgType  = 8;    -- MQMT_DATAGRAM
SET OutputRoot.MQMD.GroupId  =
    CAST(InputLocalEnvironment.File.Name AS BLOB CCSID 1208);
```

### 5.2  Aggregation — N Messages → One File

```
[MQInput ORDER.LINES.IN]
        │
        ▼
[AggregationControl: group by sourceFile]
        │
        ▼
[Aggregation: collect all lines for same file]
        │
        ▼
[Compute: format as output CSV / JSON array]
        │
        ▼
[FileOutput / S3Output / AzureBlobOutput]
```

**Key aggregation settings:**

| Property | Value |
|---|---|
| Grouping | By message property `sourceFile` |
| Completion condition | MQ message group end-of-group |
| Timeout | 60 seconds (abort partial batches) |

### 5.3  Sequencing — Reorder Out-of-Order Messages

```esql
CREATE COMPUTE MODULE SequenceEnforcer
  CREATE FUNCTION Main() RETURNS BOOLEAN
  BEGIN
    DECLARE expectedSeq INTEGER;

    -- Check sequence table for this file
    SELECT T.NEXT_SEQ INTO expectedSeq
    FROM Database.ACE_TRACKING.FILE_SEQUENCE AS T
    WHERE T.FILE_NAME = InputRoot.JSON.Data.sourceFile;

    IF InputRoot.JSON.Data.sequence <> expectedSeq THEN
      -- Hold message in reorder buffer queue
      SET OutputLocalEnvironment.Destination.MQ.DestinationData[1].queueName
          = 'ORDER.REORDER.BUFFER';
      -- Do not update sequence counter
    ELSE
      -- Process and advance counter
      UPDATE Database.ACE_TRACKING.FILE_SEQUENCE
      SET NEXT_SEQ = expectedSeq + 1
      WHERE FILE_NAME = InputRoot.JSON.Data.sourceFile;

      SET OutputLocalEnvironment.Destination.MQ.DestinationData[1].queueName
          = 'ORDER.LINES.PROCESSING';
    END IF;

    RETURN TRUE;
  END;
END MODULE;
```

---

## Part 6 — Best Practices Summary

| Practice | Detail |
|---|---|
| **Stream, don't buffer** | Use record-by-record FileInput — never load full GB files into memory |
| **Idempotent file naming** | Include date+UUID in S3 keys to prevent overwrite collisions |
| **Checkpointing** | Store last-processed record index so restarts resume mid-file |
| **Poison-row handling** | Route bad CSV lines to DLQ with line number; keep rest flowing |
| **Compression** | Request gzip from S3/Azure for large JSON/CSV downloads |
| **File locking** | Use `.inprogress` suffix on SFTP to prevent concurrent reads |
| **Sequencing** | Attach record index to every split message; verify at aggregation |
| **Back-pressure** | Monitor MQ depth on split-output queue; pause FileInput if > 500k |

---

## Exercises

1. **Exercise A** — Drop a 10,000-line CSV on the SFTP server; verify ACE publishes exactly 9,999 messages to `ORDER.LINES.IN` (line 1 is header).
2. **Exercise B** — Introduce 3 malformed rows in the CSV; verify they route to the DLQ while the other rows process normally.
3. **Exercise C** — Configure S3 push: send a JSON message and verify it appears in `processed/orders/<date>/<orderId>.json` in your S3 bucket.
4. **Exercise D** — Send split messages out-of-order (sequence 1, 3, 2, 4); verify `SequenceEnforcer` holds sequence 3 until 2 is processed, then processes 3 and 4.
