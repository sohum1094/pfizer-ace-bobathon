# Lab 01 — SAP Adapter Integration (Push / Pull)

## Overview

IBM ACE ships with a built-in **SAP connector** (based on SAP JCo) that lets
integration flows call SAP BAPIs/RFCs (pull) or receive IDocs / BAPIs inbound
from SAP (push).  
This lab covers both directions end-to-end.

```
┌──────────────────────────────────────────────────────────┐
│  PUSH (SAP → ACE)                                        │
│  SAP ──IDoc/RFC──► [SAP Adapter Node] ──► ACE Flow       │
│                                              │            │
│                                    enrich + validate      │
│                                              │            │
│                                     PUT ──► [MQ Queue]   │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│  PULL (ACE → SAP)                                        │
│  [MQ Trigger / HTTP] ──► ACE Flow ──► [SAP Request Node] │
│                                            │              │
│                                     BAPI/RFC call         │
│                                            │              │
│                                    SAP responds ──► ACE   │
└──────────────────────────────────────────────────────────┘
```

## Prerequisites

| Requirement | Notes |
|---|---|
| SAP JCo 3.x libraries | Place `sapjco3.jar` + native lib in ACE shared library path |
| SAP system access | Dev/sandbox system with RFC destination configured |
| Base lab running | IBM MQ + ACE 13 from parent lab |

---

## Part 1 — Environment Setup

### 1.1  Install SAP JCo in ACE

```bash
# Create shared-lib directory used by ACE
mkdir -p ~/ace-work/shared-classes

# Copy JCo artefacts (adjust paths to your download)
cp ~/Downloads/sapjco3.jar          ~/ace-work/shared-classes/
cp ~/Downloads/libsapjco3.dylib     ~/ace-work/shared-classes/   # macOS
# cp ~/Downloads/libsapjco3.so      ~/ace-work/shared-classes/   # Linux

# Verify JCo works
java -cp ~/ace-work/shared-classes/sapjco3.jar \
     com.sap.conn.jco.rt.JCoRuntimeFactory
```

### 1.2  Create SAP Connection Policy

Create `ace-config/SAPEndpointPolicy.policyxml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<policies>
  <policy policyType="SAPEndpoint"
          policyName="SAP_DEV"
          policyVersion="1">
    <properties>
      <applicationServerHost>sap-dev.example.com</applicationServerHost>
      <systemNumber>00</systemNumber>
      <clientNumber>100</clientNumber>
      <username>ACEUSER</username>
      <password>{{SAP_PASSWORD}}</password>
      <language>EN</language>
      <poolCapacity>5</poolCapacity>
      <peakLimit>10</peakLimit>
    </properties>
  </policy>
</policies>
```

Apply the policy:

```bash
source '/Applications/IBM App Connect Enterprise/server/bin/mqsiprofile'
mqsisetdbparms ACE_LAB_SERVER \
  -n SAP_DEV::password \
  -u ACEUSER -p <your-password>
```

---

## Part 2 — PULL Pattern (ACE calls SAP BAPI)

### 2.1  Flow Architecture

```
HTTP POST /sap/customers
        │
        ▼
 [HTTPInput] ──► [Mapping] ──► [SAPRequest] ──► [Mapping] ──► [HTTPReply]
                                   │
                           BAPI_CUSTOMER_GETLIST
                           (RFC call to SAP)
```

### 2.2  Message Flow: `SAPCustomerQuery.msgflow`

Create a new ACE application `SAPIntegrationApp` and add a message flow:

**Key node settings:**

| Node | Property | Value |
|---|---|---|
| HTTPInput | Path suffix | `/sap/customers` |
| SAPRequest | Policy | `{default}:SAP_DEV` |
| SAPRequest | Function type | BAPI |
| SAPRequest | Function name | `BAPI_CUSTOMER_GETLIST` |
| SAPRequest | Connection type | Managed |

### 2.3  ESQL Mapping — Build SAP Input Tree

```esql
-- Map HTTP JSON body ──► SAP BAPI import parameters
CREATE COMPUTE MODULE SAPRequestMapper
  CREATE FUNCTION Main() RETURNS BOOLEAN
  BEGIN
    -- Pass through existing tree
    SET OutputRoot = InputRoot;

    -- SAP BAPI expects a specific structure
    SET OutputRoot.SAP.BAPI_CUSTOMER_GETLIST.MAXROWS =
        CAST(InputRoot.JSON.Data.maxResults AS INTEGER);

    SET OutputRoot.SAP.BAPI_CUSTOMER_GETLIST.CUSTOMRANGE[1].SIGN   = 'I';
    SET OutputRoot.SAP.BAPI_CUSTOMER_GETLIST.CUSTOMRANGE[1].OPTION = 'BT';
    SET OutputRoot.SAP.BAPI_CUSTOMER_GETLIST.CUSTOMRANGE[1].LOW    =
        InputRoot.JSON.Data.fromCustomer;
    SET OutputRoot.SAP.BAPI_CUSTOMER_GETLIST.CUSTOMRANGE[1].HIGH   =
        InputRoot.JSON.Data.toCustomer;

    RETURN TRUE;
  END;
END MODULE;
```

### 2.4  ESQL Mapping — Parse SAP Response

```esql
CREATE COMPUTE MODULE SAPResponseMapper
  CREATE FUNCTION Main() RETURNS BOOLEAN
  BEGIN
    DECLARE sapData REFERENCE TO
      InputRoot.SAP.BAPI_CUSTOMER_GETLIST.ADDRESSDATA;

    -- Build JSON array response
    DECLARE i INTEGER 1;
    WHILE i <= CARDINALITY(sapData[]) DO
      SET OutputRoot.JSON.Data.customers[i].id   = sapData[i].CUSTOMER;
      SET OutputRoot.JSON.Data.customers[i].name = sapData[i].NAME;
      SET OutputRoot.JSON.Data.customers[i].city = sapData[i].CITY;
      SET i = i + 1;
    END WHILE;

    RETURN TRUE;
  END;
END MODULE;
```

---

## Part 3 — PUSH Pattern (SAP sends IDoc to ACE)

### 3.1  Flow Architecture

```
SAP ──RFC/IDoc──► [SAPInput] ──► [IDocParser] ──► [Validate] ──► PUT ──► [MQ]
                                                        │
                                                   ORDERS05 IDoc
```

### 3.2  Configure SAP-Side RFC Destination

In SAP transaction **SM59**, create an RFC destination of type **TCP/IP**:

| Field | Value |
|---|---|
| RFC destination | `ACE_ORDERS_RECEIVER` |
| Connection type | `T` (TCP/IP) |
| Program ID | `ACE_ORDER_PROGRAM` |
| Gateway host | `<ACE server hostname>` |
| Gateway service | `sapgw00` |

In **WE21** (IDoc port), create a port pointing to the RFC destination above.

### 3.3  Message Flow: `SAPIDOcReceiver.msgflow`

**Key node settings for SAPInput:**

| Property | Value |
|---|---|
| Policy | `{default}:SAP_DEV` |
| Program ID | `ACE_ORDER_PROGRAM` |
| Gateway host | `<ACE hostname>` |
| Gateway service | `sapgw00` |

### 3.4  ESQL — Process Inbound ORDERS05 IDoc

```esql
CREATE COMPUTE MODULE IDOcToMQMapper
  CREATE FUNCTION Main() RETURNS BOOLEAN
  BEGIN
    DECLARE idoc REFERENCE TO InputRoot.MRM.ORDERS05;

    -- Extract order header
    SET OutputRoot.JSON.Data.sapOrderId   = idoc.IDOC.E1EDK01.BELNR;
    SET OutputRoot.JSON.Data.orderDate    = idoc.IDOC.E1EDK01.BLDAT;
    SET OutputRoot.JSON.Data.soldTo       = idoc.IDOC.E1EDKA1[1].PARTN;

    -- Extract line items
    DECLARE i INTEGER 1;
    DECLARE item REFERENCE TO idoc.IDOC.E1EDP01[1];
    WHILE LASTMOVE(item) DO
      SET OutputRoot.JSON.Data.items[i].posnr  = item.POSEX;
      SET OutputRoot.JSON.Data.items[i].matnr  = item.MATERIAL;
      SET OutputRoot.JSON.Data.items[i].qty    = item.MENGE;
      SET i = i + 1;
      MOVE item NEXTSIBLING REPEAT TYPE NAME;
    END WHILE;

    -- Route to MQ
    SET OutputLocalEnvironment.Destination.MQ.DestinationData[1].queueName
        = 'SAP.ORDERS.IN';

    RETURN TRUE;
  END;
END MODULE;
```

---

## Part 4 — Error Handling & Retry

### 4.1  SAP Connection Retry Policy

```yaml
# server.conf.yaml additions
SAPEndpointPolicy:
  retryOnConnectionFailure: true
  maxRetryAttempts: 3
  retryDelay: 5000        # ms between retries
  backoffMultiplier: 2.0
```

### 4.2  IDoc Negative Acknowledgement

If processing fails, ACE must send a negative acknowledgement back to SAP:

```esql
-- In error handler subflow
CREATE COMPUTE MODULE SendNegativeACK
  CREATE FUNCTION Main() RETURNS BOOLEAN
  BEGIN
    -- Preserve original IDoc control record
    SET OutputRoot.SAP.IDOC.EDI_DC40.DOCNUM =
        InputRoot.SAP.IDOC.EDI_DC40.DOCNUM;
    SET OutputRoot.SAP.IDOC.EDI_DC40.STATUS = '51';  -- Application error
    RETURN TRUE;
  END;
END MODULE;
```

---

## Exercises

1. **Exercise A** — Deploy the PULL flow and call it with `curl -X POST http://localhost:7600/sap/customers -d '{"fromCustomer":"0000100000","toCustomer":"0000199999","maxResults":50}'`. Inspect the response.
2. **Exercise B** — Simulate a SAP IDoc push by sending a raw ORDERS05 XML file to the SAPInput node using the ACE Flow Exerciser.
3. **Exercise C** — Introduce a deliberate mapping error and observe that ACE sends a `STATUS=51` negative ACK back to SAP.
4. **Exercise D** — Monitor the `SAP.ORDERS.IN` queue in the MQ Web Console while replaying Exercise B 5 times; verify no duplicates appear (idempotency via IDoc DOCNUM check).

---

## Key Concepts

| Concept | Description |
|---|---|
| **JCo** | SAP Java Connector — native library ACE uses to call RFCs |
| **BAPI** | Business API — stable RFC-enabled function modules in SAP |
| **IDoc** | Intermediate Document — SAP's native asynchronous message format |
| **Program ID** | Registered server program on SAP side that ACE listens on |
| **SM59** | SAP transaction for managing RFC destinations |
