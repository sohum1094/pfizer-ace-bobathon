# Lab 07 — REST/SOAP API Exposure from ACE

## Overview

ACE can expose backend systems (SAP, relational DBs, MQ) as
**RESTful APIs** or **SOAP services**, acting as an API gateway layer.
This lab covers:

- Exposing a backend service as a REST API via ACE  
- API versioning, rate limiting, and security (OAuth2, JWT, mutual TLS)  
- Integration with **IBM API Connect** for full API governance  

```
API Consumer (mobile / partner / microservice)
        │
        ▼ HTTPS
[IBM API Connect — rate-limit, auth, analytics]
        │
        ▼ HTTPS (policy enforced)
[ACE HTTP Listener]
        │
  ┌─────┴──────────────────────────────┐
  ▼             ▼             ▼        ▼
SAP RFC     DB Query       MQ Put    SOAP call
(backend)   (backend)    (async)    (backend)
        │             │
        └──── JSON ───┘
              response
              assembly
        │
        ▼ JSON REST response
API Consumer
```

---

## Prerequisites

| Requirement | Notes |
|---|---|
| ACE 13 | From parent lab |
| IBM API Connect | Optional — use reserve proxy section if not available |
| Keycloak / any OAuth2 IdP | For JWT validation; free with Docker |
| OpenSSL | For mTLS certificate generation |

---

## Part 1 — REST API Exposure

### 1.1  Create REST API Project in ACE Toolkit

1. **File → New → REST API** — name it `OrdersAPI`.
2. Set base path: `/api/v1`.
3. Define resource `/orders` with operations:
   - `GET /orders` — query orders from DB
   - `POST /orders` — enqueue new order to MQ
   - `GET /orders/{orderId}` — lookup single order

### 1.2  OpenAPI 3.0 Descriptor

```yaml
# ace-config/orders-api.yaml
openapi: "3.0.3"
info:
  title: Orders API
  version: "1.0.0"
  description: Exposes Orders backend via IBM ACE
servers:
  - url: https://ace-server.example.com/api/v1
paths:
  /orders:
    get:
      summary: List orders
      parameters:
        - name: status
          in: query
          schema: { type: string, enum: [PENDING, PROCESSED, CANCELLED] }
        - name: limit
          in: query
          schema: { type: integer, default: 50, maximum: 500 }
      responses:
        "200":
          description: Array of orders
    post:
      summary: Submit new order
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Order"
      responses:
        "202": { description: Accepted }
        "400": { description: Validation error }
  /orders/{orderId}:
    get:
      summary: Get single order
      parameters:
        - name: orderId
          in: path
          required: true
          schema: { type: string }
      responses:
        "200": { description: Order }
        "404": { description: Not found }
components:
  schemas:
    Order:
      type: object
      required: [customerId, product, quantity, unitPrice]
      properties:
        customerId: { type: string }
        product:    { type: string }
        quantity:   { type: integer, minimum: 1 }
        unitPrice:  { type: number, format: double }
```

### 1.3  Flow: `GET /orders` — DB Backend

```
[HTTPInput GET /orders] ──► [DatabaseRequest] ──► [Mapping] ──► [HTTPReply 200]
                                SELECT with
                                ?status filter
```

```esql
CREATE COMPUTE MODULE GetOrdersQuery
  CREATE FUNCTION Main() RETURNS BOOLEAN
  BEGIN
    DECLARE status CHARACTER
        InputLocalEnvironment.REST.Input.Parameters.status;
    DECLARE lim INTEGER
        COALESCE(
          CAST(InputLocalEnvironment.REST.Input.Parameters.limit AS INTEGER),
          50);

    IF status IS NULL THEN
      SET OutputRoot.Database.Select.SQL =
          'SELECT ORDER_ID, CUSTOMER_ID, PRODUCT, QUANTITY, UNIT_PRICE, STATUS '
          || 'FROM ORDERS ORDER BY CREATED_AT DESC FETCH FIRST '
          || CAST(lim AS CHARACTER) || ' ROWS ONLY';
    ELSE
      SET OutputRoot.Database.Select.SQL =
          'SELECT ORDER_ID, CUSTOMER_ID, PRODUCT, QUANTITY, UNIT_PRICE, STATUS '
          || 'FROM ORDERS WHERE STATUS = ''' || status || ''' '
          || 'ORDER BY CREATED_AT DESC FETCH FIRST '
          || CAST(lim AS CHARACTER) || ' ROWS ONLY';
    END IF;

    RETURN TRUE;
  END;
END MODULE;
```

### 1.4  Flow: `POST /orders` — MQ Backend

```
[HTTPInput POST /orders]
        │
        ▼
[Compute: validate + generate orderId + enrich]
        │
        ▼
[MQOutput ORDER.IN]
        │
        ▼
[HTTPReply 202 — { "orderId": "...", "status": "ACCEPTED" }]
```

---

## Part 2 — API Versioning

### 2.1  URL-Path Versioning (Recommended for ACE)

Maintain separate ACE REST API projects per major version:

```
/api/v1/orders   →   OrdersAPIv1  (ACE application)
/api/v2/orders   →   OrdersAPIv2  (ACE application)
```

Both applications can run on the same integration server, each with
their own listener port or shared port with different path prefixes.

### 2.2  Header-Based Versioning

```esql
CREATE COMPUTE MODULE VersionRouter
  CREATE FUNCTION Main() RETURNS BOOLEAN
  BEGIN
    DECLARE apiVersion CHARACTER
        InputRoot.HTTPInputHeader."Accept-Version";

    SET OutputRoot = InputRoot;

    IF apiVersion = '2.0' OR apiVersion = '' THEN
      PROPAGATE TO TERMINAL 'out1';  -- v2 flow
    ELSE
      PROPAGATE TO TERMINAL 'out2';  -- v1 (legacy) flow
    END IF;

    RETURN FALSE;
  END;
END MODULE;
```

### 2.3  Deprecation Headers

```esql
-- In the v1 response path, add deprecation warning header
SET OutputRoot.HTTPResponseHeader."Deprecation" = 'true';
SET OutputRoot.HTTPResponseHeader."Sunset"      = 'Sat, 31 Dec 2025 23:59:59 GMT';
SET OutputRoot.HTTPResponseHeader."Link"        =
    '</api/v2/orders>; rel="successor-version"';
```

---

## Part 3 — Security

### 3.1  OAuth2 / JWT Token Validation

ACE validates JWT Bearer tokens using the **HTTP Header Validation** pattern:

```
[HTTPInput] ──► [Compute: extract Bearer token]
                        │
                        ▼
               [Validate JWT signature + claims]
                        │
            ┌───────────┴────────────┐
            ▼                       ▼
       VALID token            INVALID token
       continue flow          [HTTPReply 401]
```

```esql
CREATE COMPUTE MODULE ValidateJWT
  CREATE FUNCTION Main() RETURNS BOOLEAN
  BEGIN
    DECLARE authHeader CHARACTER
        InputRoot.HTTPInputHeader.Authorization;

    -- Check Bearer prefix
    IF LEFT(authHeader, 7) <> 'Bearer ' THEN
      SET OutputRoot.JSON.Data.error = 'Missing Bearer token';
      SET OutputLocalEnvironment.Destination.HTTP.ReplyStatusCode = 401;
      PROPAGATE TO TERMINAL 'out2';
      RETURN FALSE;
    END IF;

    DECLARE token CHARACTER SUBSTRING(authHeader FROM 8);

    -- Call OIDC introspection endpoint (or validate locally with JWKS)
    SET OutputRoot.HTTPRequestHeader."Content-Type" =
        'application/x-www-form-urlencoded';
    SET OutputRoot.BLOB.BLOB =
        CAST('token=' || token AS BLOB CCSID 1208);

    -- After introspection response, check active flag
    IF InputRoot.JSON.Data.active = FALSE THEN
      SET OutputLocalEnvironment.Destination.HTTP.ReplyStatusCode = 401;
      PROPAGATE TO TERMINAL 'out2';
      RETURN FALSE;
    END IF;

    -- Store claims in Environment for downstream nodes
    SET Environment.auth.sub   = InputRoot.JSON.Data.sub;
    SET Environment.auth.scope = InputRoot.JSON.Data.scope;

    RETURN TRUE;
  END;
END MODULE;
```

### 3.2  Mutual TLS (mTLS) Configuration

```bash
# Generate CA, server cert, and client cert
openssl genrsa -out ca.key 4096
openssl req -new -x509 -days 365 -key ca.key -out ca.crt \
  -subj "/CN=ACE Lab CA"

openssl genrsa -out server.key 4096
openssl req -new -key server.key -out server.csr \
  -subj "/CN=ace-server.example.com"
openssl x509 -req -days 365 -in server.csr \
  -CA ca.crt -CAkey ca.key -CAcreateserial -out server.crt

openssl genrsa -out client.key 4096
openssl req -new -key client.key -out client.csr \
  -subj "/CN=api-client-1"
openssl x509 -req -days 365 -in client.csr \
  -CA ca.crt -CAkey ca.key -CAcreateserial -out client.crt
```

```yaml
# server.conf.yaml — mTLS listener
RestAdminListener:
  port: 7443
  sslEnabled: true
  sslCertificate: /ace-work/certs/server.crt
  sslKey: /ace-work/certs/server.key
  sslClientAuth: required
  sslTruststore: /ace-work/certs/ca.crt
```

### 3.3  Rate Limiting via HTTP Input Filter

ACE does not have native rate limiting — handle this at the API gateway
(API Connect), but ACE can enforce a simple per-IP throttle using a
shared database counter:

```esql
CREATE COMPUTE MODULE RateLimiter
  CREATE FUNCTION Main() RETURNS BOOLEAN
  BEGIN
    DECLARE clientIP CHARACTER
        InputLocalEnvironment.HTTP.Input.RemoteAddress;

    -- Read rolling 60s window counter
    DECLARE requestCount INTEGER;
    SELECT T.REQUEST_COUNT INTO requestCount
    FROM Database.ACE_RLIMIT.RATE_LIMIT AS T
    WHERE T.CLIENT_IP = clientIP
      AND T.WINDOW_START > CURRENT_TIMESTAMP - INTERVAL '60' SECOND;

    IF requestCount > 100 THEN
      SET OutputRoot.JSON.Data.error   = 'Rate limit exceeded';
      SET OutputRoot.JSON.Data.retryAfter = 60;
      SET OutputLocalEnvironment.Destination.HTTP.ReplyStatusCode = 429;
      PROPAGATE TO TERMINAL 'out2';
      RETURN FALSE;
    END IF;

    RETURN TRUE;
  END;
END MODULE;
```

---

## Part 4 — SOAP Service Exposure

### 4.1  Expose a DB as a SOAP Service

```
[SOAPInput /OrderService]
        │
        ▼
[XMLTransformation: SOAP → internal JSON]
        │
        ▼
[DatabaseRequest]
        │
        ▼
[XMLTransformation: result → SOAP response]
        │
        ▼
[SOAPReply]
```

### 4.2  WSDL Definition Snippet

```xml
<definitions name="OrderService"
  targetNamespace="urn:ace.lab.orders"
  xmlns:tns="urn:ace.lab.orders"
  xmlns:xsd="http://www.w3.org/2001/XMLSchema"
  xmlns:soap="http://schemas.xmlsoap.org/wsdl/soap/"
  xmlns="http://schemas.xmlsoap.org/wsdl/">

  <types>
    <xsd:schema targetNamespace="urn:ace.lab.orders">
      <xsd:element name="GetOrderRequest">
        <xsd:complexType>
          <xsd:sequence>
            <xsd:element name="orderId" type="xsd:string"/>
          </xsd:sequence>
        </xsd:complexType>
      </xsd:element>
    </xsd:schema>
  </types>

  <message name="GetOrderRequest">
    <part name="parameters" element="tns:GetOrderRequest"/>
  </message>

  <portType name="OrderServicePortType">
    <operation name="GetOrder">
      <input message="tns:GetOrderRequest"/>
      <output message="tns:GetOrderResponse"/>
    </operation>
  </portType>
</definitions>
```

---

## Part 5 — IBM API Connect Integration

### 5.1  Architecture

```
Developer Portal
      │ subscribe
      ▼
API Connect Gateway ──► ACE (backend)
      │ enforce:            │
      │  - rate limit       ├── GET /orders  ──► DB
      │  - OAuth2           ├── POST /orders ──► MQ
      │  - TLS              └── /orders/{id} ──► DB
      │ analytics
      ▼
Consumer App
```

### 5.2  Publish ACE OpenAPI to API Connect

```bash
# Install API Connect CLI
npm install -g @ibm-cloud/ibmcloud-apic

# Login
apic login --server apim.example.com \
  --username admin --password <password>

# Publish API definition
apic apis:publish \
  --server apim.example.com \
  --org dev-org \
  --catalog sandbox \
  ace-config/orders-api.yaml
```

### 5.3  API Connect Policy Snippet — Rate Limiting

```yaml
# API Connect rate-limit policy (in API YAML)
x-ibm-configuration:
  gateway: datapower-api-gateway
  assembly:
    execute:
      - rate-limit:
          name: standard-plan
          weight: 1
          hard-limit: false
          use-api-name: false
          use-app-id: false
      - invoke:
          title: Invoke ACE
          target-url: https://ace-server.example.com$(request.path)
          secure-gateway: false
          tls-profile: ace-tls-profile
```

---

## Exercises

1. **Exercise A** — Deploy `OrdersAPIv1` and call `GET /api/v1/orders?status=PENDING` with `curl`; verify it returns JSON from the DB.
2. **Exercise B** — Call `POST /api/v1/orders` without an `Authorization` header; verify `401 Unauthorized` is returned with `{"error":"Missing Bearer token"}`.
3. **Exercise C** — Generate a client cert and configure mTLS; test that `curl --cert client.crt --key client.key` succeeds while an unauthenticated call is rejected.
4. **Exercise D** — Publish the OpenAPI spec to API Connect (or a local mock gateway); enable rate limiting at 10 req/min and verify the 11th request gets `429`.

---

## Key Concepts

| Concept | Description |
|---|---|
| **REST API project** | ACE artefact that binds OpenAPI operations to message flows |
| **JWT introspection** | Validating an opaque token via IdP `/introspect` endpoint |
| **mTLS** | Mutual TLS — both server and client present X.509 certificates |
| **API Connect** | IBM's full API management platform — rate limiting, analytics, portal |
| **SOAP SOAPInput** | ACE node for WSDL-defined web service exposure |
| **Rate limiting** | Throttling requests per client to protect the backend |
