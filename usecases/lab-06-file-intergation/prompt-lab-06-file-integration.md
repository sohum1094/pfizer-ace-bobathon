# Prompts — Lab 06: File-Based Integration (SFTP / S3 / Azure Blob)

> Copy any prompt below and paste it into your AI assistant.
> Replace values in `<angle brackets>` with your own details.

---

## 🔵 Conceptual Prompts

### C1 — File Integration Patterns in ACE

```
I am working on a file-based integration lab in IBM ACE 13.
Explain the main patterns for reading and writing files in ACE:
- FileInput node vs SFTP connector vs cloud (S3/Azure Blob) connectors
- How ACE streams large files line-by-line vs loading the whole file into memory
- The difference between the inbound (read) and outbound (write) patterns
- What "record detection" means in the FileInput node
  (fixed length, delimiter-based, whole-file modes)
- How in-progress suffixes (.inprogress) prevent double-processing of files
```

---

### C2 — Large File Processing Best Practices

```
In IBM App Connect Enterprise, what are the best practices for processing
very large files (100MB+ CSVs, multi-GB XMLs)?

Cover:
- Why you must never load the entire file into memory (BIP2111E OutOfMemory)
- How the FileInput node emits one message per CSV line (record-by-record streaming)
- How to configure XMLParser in streaming mode for large XML files
- What "checkpointing" means for file processing restarts
- Back-pressure: how to detect that the downstream MQ queue is filling up
  faster than it can be consumed, and how to pause the FileInput node
- The .inprogress, .processed, and error rename patterns for SFTP polling
```

---

### C3 — Push/Pull with Cloud Storage (S3 and Azure Blob)

```
Explain how IBM ACE 13 integrates with AWS S3 and Azure Blob Storage.
For each:
- How ACE is triggered when a new object/blob arrives
  (S3: SNS → SQS → ACE; Azure: Event Grid → Service Bus → ACE)
- What ACE connectors/nodes are available (S3Input, AzureBlobRequest)
- How to write an object to S3 or Azure Blob from ACE
- Policy configuration (SFTPServerPolicy, AmazonS3, AzureBlobStorage)
- Authentication methods (IAM role vs access key for S3; connection string vs
  managed identity for Azure)
- Date-partitioned key patterns for S3 (e.g., processed/orders/20240715/<id>.json)
```

---

### C4 — File Splitting, Aggregation and Sequencing

```
In IBM ACE, explain the three patterns: file splitting, aggregation, and sequencing.

1. Splitting: How a single large file becomes N individual MQ messages
   (one per CSV row), including how to attach metadata (sequence number, source filename, group ID)

2. Aggregation: How N individual MQ messages are collected back into a
   single batch message using the ACE Aggregation node
   (what triggers emission: size threshold vs timeout)

3. Sequencing: Why split messages may arrive out of order (parallel consumers)
   and how to reorder them using a sequence tracker table and reorder buffer queue

Give a concrete end-to-end example: 10,000-line CSV → 9,999 messages → aggregated batch → output file.
```

---

## 🟡 Implementation Prompts

### I1 — SFTP Policy and FileInput Flow

```
Generate the IBM ACE artefacts for polling an SFTP server for CSV order files.
I need:

1. SFTPServerPolicy XML (policyName: LabSFTP) for:
   - host: localhost, port: 2222, directory: /upload, filePattern: orders_*.csv
   - credentials stored in LabSFTPCreds policy alias

2. The mqsisetdbparms command to store SFTP credentials

3. FileInput node settings table:
   - Policy, Directory, Filter, Post-read action (move to /processed),
     Record detection (delimiter=\n), In-progress suffix (.inprogress),
     Maximum record size (65535), Persist across restart (Yes)

4. The full flow diagram (ASCII):
   FileInput → CSVParse → Validate → MQOutput ORDER.LINES.IN
   with a DLQ route for invalid rows

5. The Docker command to start a local SFTP server for testing
```

---

### I2 — S3 Policy and Push/Pull ESQL

```
Write the Amazon S3 policy XML (policyName: LabS3) and two ESQL compute modules
for IBM ACE 13:

Policy settings:
- region: us-east-1, bucketName: ace-lab-orders
- accessKeyId and secretAccessKey stored via credentials placeholder

Module 1 — BuildS3OutputPath:
- Reads orderId from InputRoot.JSON.Data.orderId
- Builds a date-partitioned S3 key: processed/orders/<yyyyMMdd>/<orderId>.json
- Sets OutputLocalEnvironment.S3.ObjectKey and S3.ContentType = 'application/json'

Module 2 — ParseS3EventNotification:
- Parses an SNS/SQS S3 event notification JSON (s3.object.key, s3.bucket.name, eventTime)
- Extracts bucket and key into OutputRoot.JSON.Data
- Sets OutputLocalEnvironment.S3.SourceBucket and S3.SourceKey for a downstream
  S3Input/AzureBlobRequest download

Add comments explaining the date format used with CURRENT_DATE.
```

---

### I3 — Azure Blob Event Grid Trigger Flow

```
Design the full IBM ACE flow for processing new files in Azure Blob Storage
triggered by Azure Event Grid → Azure Service Bus.

Show:
1. Azure Blob Storage policy XML (policyName: LabAzureBlob) with storageAccountName,
   containerName, and connectionString placeholder
2. The ESQL compute module ParseBlobEvent that extracts: blobName (from subject),
   eventType, contentType (from data.contentType), blobUrl, blobSize (contentLength)
3. The flow diagram (ASCII):
   ServiceBusInput → ParseBlobEvent → [AzureBlobRequest download] → CSVParse → MQOutput
4. The Event Grid subscription settings needed in Azure to route
   'Microsoft.Storage.BlobCreated' events to the Service Bus queue

Also explain the difference between polling (FileInput) and event-driven (Event Grid)
approaches and when to use each.
```

---

### I4 — Streaming CSV Parser ESQL

```
Write an IBM ACE ESQL compute module ParseCSVLine that processes
one CSV line per message (from a FileInput node in line-by-line mode).

Requirements:
1. Read the raw line from InputRoot.BLOB.BLOB as UTF-8 (CCSID 1208)
2. Skip the header row (if line starts with 'order_id')
3. Tokenize using STRTOK_LIST(line, ',')
4. Map fields to output JSON:
   - orderId (field 1, trim whitespace)
   - customerId (field 2)
   - product (field 3)
   - quantity (field 4, cast to INTEGER)
   - unitPrice (field 5, cast to DECIMAL)
   - lineNumber (from InputLocalEnvironment.File.RecordIndex)
   - sourceFile (from InputLocalEnvironment.File.Name)
5. If quantity <= 0 or unitPrice <= 0: route to DLQ terminal with error code ACE-VALIDATE-002

Handle the edge case where STRTOK_LIST returns a NULL element (empty CSV field).
```

---

### I5 — File Splitting with MQ Group Messages

```
Write the IBM ACE ESQL for splitting a large CSV file into individual
MQ messages that belong to an MQ message group (for later aggregation).

Requirements:
1. Attach the source filename as OutputRoot.JSON.Data.sourceFile
2. Attach the line sequence number as OutputRoot.JSON.Data.sequence
   (from InputLocalEnvironment.File.RecordIndex)
3. Set OutputRoot.MQMD.GroupId to a BLOB derived from the source filename
4. Set OutputRoot.MQMD.MsgFlags to indicate group membership
5. Set the last message in the file to have MQMF_LAST_MSG_IN_GROUP flag
   (using InputLocalEnvironment.File.IsLastRecord)
6. Route all messages to ORDER.LINES.IN

Also show the Aggregation node settings to collect by MQ group:
groupCompletion = 'OnLastMessage', timeout = 60s.
```

---

### I6 — Out-of-Order Sequencing with Reorder Buffer

```
Write the IBM ACE ESQL compute module SequenceEnforcer that enforces
in-order processing of split file messages.

The module should:
1. Read sourceFile and sequence from InputRoot.JSON.Data
2. Look up NEXT_SEQ from Database.ACE_TRACKING.FILE_SEQUENCE for the given FILE_NAME
3. If incoming sequence == NEXT_SEQ:
   - Process normally (RETURN TRUE)
   - Update NEXT_SEQ = NEXT_SEQ + 1
   - Also show how to re-check ORDER.REORDER.BUFFER for now-unblocked messages
4. If incoming sequence != NEXT_SEQ:
   - Route to ORDER.REORDER.BUFFER queue
5. Handle the first-message case (no row in FILE_SEQUENCE yet)

Also provide the DDL for the FILE_SEQUENCE tracking table and explain the
risk of this approach under high parallelism (hint: row-level locking needed).
```

---

## 🔴 Troubleshooting Prompts

### T1 — FileInput Node Not Picking Up Files

```
My ACE FileInput node is configured to poll an SFTP server every 30 seconds
for files matching orders_*.csv in /upload directory. The SFTP server has
files present and I can connect manually with the same credentials, but the
FileInput node never picks up any files.

Walk me through the diagnostic checklist:
1. Verifying the SFTPServerPolicy is deployed to the correct policy project
2. Checking the ACE Integration Server log for FileInput connection errors
3. Confirming the filePattern glob syntax is correct (orders_*.csv)
4. Whether the .inprogress suffix interferes if a previous run crashed
5. How to enable FileInput diagnostic tracing in ACE
```

---

### T2 — OutOfMemory When Processing Large CSV

```
My ACE flow using FileInput to read a 2GB CSV file throws:
  BIP2111E: The integration server has run out of memory.
  java.lang.OutOfMemoryError: Java heap space

My FileInput node is set to "Whole file" record detection.
Explain what change I must make to switch to streaming (line-by-line) mode
and how to verify ACE is now processing one line at a time rather than
buffering the entire file. Also show the server.conf.yaml JVM heap settings
I should check to ensure sufficient memory for the streaming approach.
```

---

### T3 — S3 PUT Fails with Access Denied

```
My ACE flow using an S3Output node to write to bucket ace-lab-orders
throws:
  BIP3748E: Amazon S3 request failed. HTTP 403: Access Denied

I set the access key and secret in the AmazonS3 policy. What are
the common causes of S3 403 errors in ACE, specifically:
1. IAM policy missing s3:PutObject permission on the bucket
2. Bucket policy denying cross-account access
3. S3 bucket name containing uppercase letters (S3 is case-sensitive)
4. Region mismatch between the policy and the actual bucket region
5. KMS encryption: bucket requires SSE-KMS but ACE is not providing the key ARN

Show the minimal IAM policy JSON that grants ACE the right to PUT objects in a specific S3 prefix.
```

---

### T4 — Aggregation Node Emitting Before All Messages Collected

```
My ACE Aggregation node is set to collect 500 messages (size threshold)
with a 10-second timeout. When I send exactly 500 messages from a split file,
the aggregation fires correctly. But when I send 1000 messages (two batches
of 500), the second batch is sometimes emitted with fewer than 500 messages
because the timeout fires early.

What are the reasons the timeout fires before reaching the size threshold:
1. Whether message processing time pushes individual messages past the timeout window
2. How to configure the aggregation to use MQ group semantics (MQMF_LAST_MSG_IN_GROUP)
   instead of time/size thresholds
3. Whether running multiple ACE flow instances (parallel consumers) can split
   a group across instances, breaking aggregation
4. The correct flow design to handle both approaches safely
```

---

### T5 — Sequencing: Messages Stuck in Reorder Buffer Forever

```
My SequenceEnforcer flow puts out-of-order messages into ORDER.REORDER.BUFFER.
The idea is that when the missing sequence arrives, the flow should drain the
buffer and process the waiting messages. However, messages are accumulating in
ORDER.REORDER.BUFFER and never being re-processed.

The issue: the flow only checks the buffer when a new message arrives on
ORDER.LINES.IN, but there are no more incoming messages (the file is fully split).

Design a remediation mechanism:
1. A TimerInput flow that periodically scans ORDER.REORDER.BUFFER for messages
   whose sequence is now ready (NEXT_SEQ matches)
2. How to move ready messages back to ORDER.LINES.PROCESSING
3. A TTL mechanism to discard messages that have been in the buffer > 1 hour
   (possible missing sequence gap — never coming)
4. An alert when a message exceeds TTL (possible upstream data loss)
```
