# Prompts — Lab 05: MFT Integration with ACE Flows

> Copy any prompt below and paste it into your AI assistant.
> Replace values in `<angle brackets>` with your own details.

---

## 🔵 Conceptual Prompts

### C1 — What is IBM Managed File Transfer?

```
I am learning about IBM Managed File Transfer (MFT) as part of an ACE integration lab.
Explain what MFT is and how it fits alongside IBM MQ and ACE. Cover:
- What MFT provides that plain FTP/SFTP does not (guaranteed delivery, audit, retry)
- The roles of: coordination queue manager, source agent, destination agent
- What happens when a transfer fails midway through (resumption, checkpointing)
- How ACE fits into the MFT architecture: consuming transfer events and initiating transfers
- The SYSTEM.FTE topic tree and what events are published there
```

---

### C2 — MFT Transfer Event Lifecycle

```
Describe the full lifecycle of an MFT file transfer event in IBM MQ pub/sub.
Starting from when a file arrives in the source agent's monitored directory:
1. What events are published to SYSTEM/FTE and at what stages
   (started, progress, completed, failed)?
2. What does the TransferLog XML document contain (key fields)?
3. How does an ACE durable subscription on FTE.EVENTS receive these events?
4. What is the resultCode=0 for success vs non-zero for failure?
5. How does ACE differentiate a partial transfer from a total failure?
```

---

### C3 — File-Complete Trigger Pattern

```
In MFT + ACE integration, explain the "file-complete trigger" pattern.
The problem: a large batch consists of multiple part files transferred by MFT
before a final sentinel .COMPLETE marker file arrives.

Explain:
- Why processing the parts before all arrive causes data integrity issues
- How the .COMPLETE marker file signals batch readiness
- How ACE detects the .COMPLETE marker in the MFT transfer event XML
- How the ACE flow holds part-file events until the COMPLETE marker arrives
- Alternative approaches (file count in COMPLETE file, manifest file, fixed batch size)
```

---

## 🟡 Implementation Prompts

### I1 — MFT Setup Commands

```
Generate the complete shell commands to set up an IBM MFT environment
on a local machine using queue manager MQLAB (already running on localhost:1414).

I need:
1. fteSetupCoordination command for queue manager MQLAB
2. fteCreateAgent for SOURCE_AGENT and DEST_AGENT, both on MQLAB
3. fteStartAgent commands for both agents
4. The MQSC commands to create FTE.EVENTS queue and a durable subscription
   to 'SYSTEM/FTE/Log/MQLAB/SOURCE_AGENT' that routes events to FTE.EVENTS

Also show fteListAgents to verify both agents are registered and active.
```

---

### I2 — ESQL to Parse MFT Transfer Log XML

```
Write an IBM ACE ESQL compute module ParseMFTEvent that processes a
MFT TransferLog XML message received from the FTE.EVENTS queue.

The module should extract into OutputRoot.JSON.Data:
- transferId (from the transaction ID attribute)
- outcome: 'SUCCESS' if resultCode='0', else 'FAILED'
- resultCode and supplement text
- sourceFile (from transferSet.item.source.file)
- destFile (from transferSet.item.destination.file)
- bytesTransferred (from transferSet bytesTransferred attribute)
- eventTime (from action time attribute)

Store outcome and filename in OutputLocalEnvironment.Transfer for downstream routing.

Include correct ESQL attribute access syntax (-attrName in XMLNSC tree)
and add comments explaining the XMLNSC namespace access pattern.
```

---

### I3 — ESQL to Build MFT Transfer Request

```
Write an IBM ACE ESQL compute module BuildMFTRequest that constructs an
MFT transfer request XML document and routes it to SYSTEM.FTE.COMMAND.SOURCE_AGENT.

The input is a JSON message with fields: filename, destinationPath.

The transfer request XML should set:
- transferRequest version='1.00' and a UUID ID attribute
- sourceAgent: name=SOURCE_AGENT, QMgr=MQLAB, source file=/outbound/<filename>
- destAgent: name=DEST_AGENT, QMgr=MQLAB, destination file=<destinationPath>/<filename>
- Transfer mode: binary

Show the XMLNSC attribute syntax for setting XML attributes in ACE ESQL.
```

---

### I4 — File-Complete Trigger ESQL Module

```
Write an IBM ACE ESQL compute module CheckFileComplete that:
1. Reads the filename from InputLocalEnvironment.Transfer.filename
2. If the filename ends with '.COMPLETE':
   - Extracts the batch name by stripping the '.COMPLETE' suffix
   - Sets OutputRoot.JSON.Data.batchName and readyToProcess=TRUE
   - PROPAGATEs to terminal 'out1' (trigger batch processing)
3. Otherwise (regular chunk file):
   - PROPAGATEs to terminal 'out2' (acknowledge receipt only)
   - RETURN FALSE to prevent double-propagation

Also show the flow diagram (ASCII) and explain what the out2 terminal should
connect to (e.g., an ACK flow or a discard node).
```

---

### I5 — MFT Business-Level Audit Trail

```
Design the IBM ACE audit trail for MFT file processing. I need:

1. An MQ queue FILE.AUDIT.LOG (MQSC definition: persistent, max 1M depth)
2. An ESQL compute module EmitAuditRecord that after every successful
   file processing emits a JSON audit message with:
   - auditType: 'FILE_PROCESSED'
   - filename (from InputRoot.JSON.Data.filename)
   - recordCount (from Environment.processedCount)
   - processedAt (ISO 8601)
   - flowServer (from InputLocalEnvironment.ComIbmIntegrationServerLabel)
   - correlationId (from Environment.correlationId)
3. A separate module EmitTransferFailAudit for failed transfers with:
   - auditType: 'FILE_TRANSFER_FAILED'
   - resultCode, supplement, sourceFile, eventTime

Show how to deploy these as a shared audit sub-flow reusable across multiple file flows.
```

---

### I6 — Retry Failed MFT Transfer from ACE

```
When an MFT transfer fails (resultCode != 0), my ACE flow should
automatically request a retry from the source system.

Design the retry flow:
1. How ACE detects a failed transfer (resultCode check in ParseMFTEvent)
2. How ACE puts a retry request on an alert queue FILE.TRANSFER.ALERTS
   with the original sourceFile path and error details
3. A separate ACE retry-initiator flow that consumes FILE.TRANSFER.ALERTS
   and re-sends the MFT transfer request to SYSTEM.FTE.COMMAND.SOURCE_AGENT
4. How to limit retries to 3 attempts using a retryCount header
5. What to do after 3 failed retries (operations alert via email/webhook)
```

---

## 🔴 Troubleshooting Prompts

### T1 — FTE.EVENTS Queue Receiving No Messages

```
I defined a durable subscription:
  DEFINE SUB(ACE.FTE.SUB) TOPICSTR('SYSTEM/FTE/Log/MQLAB/SOURCE_AGENT')
  DEST(FTE.EVENTS) DURABLE(YES)

I triggered a file transfer with SOURCE_AGENT, the transfer completed
successfully (I can see it in the MFT transfer log), but FTE.EVENTS has 0 messages.

Walk me through the diagnostic steps:
1. How to verify the durable subscription is active using DISPLAY SUB(*)
2. How to check that the MFT coordination queue manager is MQLAB
   and that SOURCE_AGENT is publishing to the correct topic string
3. How to verify the topic string format: is it SYSTEM/FTE/Log/MQLAB/SOURCE_AGENT
   or SYSTEM.FTE.LOG.MQLAB.SOURCE_AGENT (slash vs dot)?
4. What authority records (setmqaut) are needed for MFT to publish to the topic
```

---

### T2 — ACE Cannot Parse MFT Transfer Log XML

```
My ACE ParseMFTEvent compute module throws:
  BIP5010E: A parsing error was detected in the XML input data.

When I browse the FTE.EVENTS queue in the MQ Web Console, the message looks
like valid XML. What are the common causes of XML parse failures in IBM ACE
when consuming MFT transfer log messages?

Cover:
- CCSID mismatch (MFT publishes in UTF-8, ACE may expect a different encoding)
- BOM (Byte Order Mark) in the XML header
- The correct XMLParser node settings for MFT messages (namespace awareness, XMLNSC vs MRM)
- How to use the ACE Flow Exerciser to test with a raw XML message and see the parsed tree
```

---

### T3 — BuildMFTRequest XML Not Accepted by Agent

```
My ACE flow sends an XML transfer request to SYSTEM.FTE.COMMAND.SOURCE_AGENT
but the agent ignores it (no transfer is initiated, no error in agent log).
My ESQL builds the XMLNSC tree and the message body looks correct when I browse the queue.

What are the common reasons an MFT agent ignores a transfer request message on its command queue?
Check:
1. The message format — does it need to be MQFMT_STRING or MQFMT_NONE?
2. Whether the transferRequest XML namespace is required
3. Whether the agent name in the XML must exactly match the registered agent name (case-sensitive)
4. The correct MQMD.ReplyToQ and MQMD.ReplyToQMgr fields for the agent to send a response
5. How to enable MFT agent debug logging to see why it rejected the message
```

---

### T4 — File-Complete Pattern: .COMPLETE Marker Never Arrives

```
My ACE file-complete trigger flow is correctly holding part-file events
and waiting for a .COMPLETE marker. But the source system sometimes fails to
send the marker file (network outage, crash).

What should happen in my ACE flow when the .COMPLETE marker never arrives?
Design a timeout mechanism:
1. How to use a TimerInput or MQ scheduled message to trigger a timeout check
2. How to track which batches are pending (e.g., in a database table)
3. What the timeout action should be: alert + manual intervention, or
   auto-retry the file request to the source
4. How to clean up the partial batch state to prevent memory/queue accumulation
```

---

### T5 — Audit Log Records Missing for Large Batch Transfers

```
My file audit trail (FILE.AUDIT.LOG queue) shows only 80% of the expected
audit records after processing a large batch of 5,000 MFT transfer events.
The other 20% processed correctly (I can see the output files), but no audit record.

What are the likely causes and how do I fix them?
Cover:
1. Whether the audit emit is inside or outside the main transaction (XA scope)
2. Whether an MQOutput exception for the audit queue can silently suppress
   the audit record while allowing main processing to continue
3. How to make audit record emission non-transactional (best-effort) vs
   transactional (same commit as main processing)
4. How to add a dead-letter audit fallback (write to a file if MQ put fails)
```
