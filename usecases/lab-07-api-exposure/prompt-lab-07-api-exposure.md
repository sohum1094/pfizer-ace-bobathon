# Prompts — Lab 07: REST/SOAP API Exposure from ACE

> Copy any prompt below and paste it into your AI assistant.
> Replace values in `<angle brackets>` with your own details.

---

## 🔵 Conceptual Prompts

### C1 — ACE as an API Gateway Layer

```
Explain how IBM App Connect Enterprise 13 can act as an API gateway or
API facade in front of backend systems like SAP, relational databases, and IBM MQ.
Cover:
- What an ACE REST API project is and how it binds OpenAPI operations to message flows
- How ACE differs from a dedicated API gateway (IBM API Connect, AWS API GW)
- When to use ACE alone for API exposure vs when to add API Connect in front
- The request/response pattern: how ACE converts an HTTP REST call into a
  SAP BAPI call, DB query, or MQ put — and assembles the HTTP response
- Synchronous vs asynchronous API patterns (202 Accepted + polling vs 200 with inline data)
```

---

### C2 — API Security Options in ACE

```
Explain the three main API security mechanisms available in IBM ACE 13:

1. OAuth2 / JWT Bearer tokens: how ACE validates a JWT either by calling an
   OIDC introspection endpoint or by validating the signature locally with a JWKS URI

2. Mutual TLS (mTLS): how both client and server present X.509 certificates,
   what sslClientAuth: required means in server.conf.yaml, and what happens
   if the client cert is not signed by the trusted CA

3. API key: simple shared secret in a header — when is this acceptable vs inadequate?

For each, state: is it stateless? Does ACE need to call an external service to validate?
What is the latency impact?
```

---

### C3 — API Versioning Strategies

```
When exposing APIs from IBM ACE, what are the options for API versioning
and what are the trade-offs?

Compare:
1. URL-path versioning: /api/v1/orders vs /api/v2/orders (separate ACE REST API projects)
2. Header-based versioning: Accept-Version: 2.0 header (single flow, ESQL routing)
3. Content negotiation: Accept: application/vnd.orders.v2+json

For each, discuss:
- How consumers discover and adopt the new version
- How to run v1 and v2 simultaneously in the same ACE Integration Server
- How to sunset v1 (Deprecation and Sunset response headers)
- IBM API Connect's role in managing versioned API lifecycle
```

---

### C4 — ACE vs API Connect: Responsibilities

```
In an architecture where both IBM ACE and IBM API Connect are present, explain
who should own each responsibility:

- Rate limiting (per API key, per client IP, per plan)
- OAuth2 token validation
- SSL termination
- Request/response logging and analytics
- Caching
- Load balancing across multiple ACE servers
- Business logic transformation (JSON ↔ SAP BAPI)
- Dead letter queue routing
- API lifecycle management (versioning, deprecation, developer portal)

For each item, state: ACE, API Connect, or both — and why.
```

---

## 🟡 Implementation Prompts

### I1 — OpenAPI 3.0 Descriptor for Orders API

```
Write a complete OpenAPI 3.0 YAML descriptor for an Orders API to be
deployed in IBM ACE 13. Include:

Base path: /api/v1

Endpoints:
- GET /orders: query parameters status (enum: PENDING, PROCESSED, CANCELLED)
  and limit (integer, default 50, max 500); response 200 array of Order
- POST /orders: request body Order schema; responses 202 Accepted and 400 Bad Request
- GET /orders/{orderId}: path parameter orderId; responses 200 Order and 404 Not Found
- DELETE /orders/{orderId}: responses 204 No Content and 404 Not Found

Order schema fields: orderId (readOnly), customerId (required), product (required),
quantity (required, integer min 1), unitPrice (required, number), status (readOnly),
createdAt (readOnly, format date-time)

Add security scheme: BearerAuth (HTTP Bearer JWT) applied to all operations.
```

---

### I2 — ESQL for GET /orders with DB Backend

```
Write the ESQL compute module GetOrdersQuery for an IBM ACE REST flow
that handles GET /orders. Requirements:
1. Read status query parameter from InputLocalEnvironment.REST.Input.Parameters.status
2. Read limit parameter (default 50 if absent)
3. If status is NULL: build a SELECT with no WHERE clause
4. If status is provided: add WHERE STATUS = '<status>' (validate it is one of
   PENDING, PROCESSED, CANCELLED — return 400 if not)
5. Build: SELECT ORDER_ID, CUSTOMER_ID, PRODUCT, QUANTITY, UNIT_PRICE, STATUS,
   CREATED_AT FROM ORDERS ORDER BY CREATED_AT DESC FETCH FIRST <limit> ROWS ONLY

Also write the second module MapDBResultToJSON that iterates the DatabaseRequest
result set and builds OutputRoot.JSON.Data.orders[] array.

Protect against SQL injection: show the parameterised query approach using
Database.Request.Parameter[].
```

---

### I3 — ESQL for JWT Validation

```
Write an IBM ACE ESQL compute module ValidateJWT that:
1. Reads the Authorization header from InputRoot.HTTPInputHeader.Authorization
2. Validates it starts with 'Bearer ' (7 chars); if not, returns HTTP 401 with
   JSON body {"error": "Missing or invalid Bearer token"}
3. Extracts the token string
4. Calls an OIDC introspection endpoint via an HTTPRequest node (show the
   OutputRoot setup for a form-encoded POST with token=<value>)
5. After the introspection response, checks active=true; if false, returns 401
6. If valid, stores sub and scope in Environment.auth.sub and Environment.auth.scope
7. Propagates to 'out1' (valid) or 'out2' (invalid)

Show the ACE flow diagram connecting ValidateJWT → HTTPRequest (introspect) →
a second compute node to check the response.
```

---

### I4 — Mutual TLS Setup (Certificates + server.conf.yaml)

```
Provide a complete step-by-step guide for setting up mutual TLS (mTLS) for an
IBM ACE 13 HTTP listener. Include:

1. OpenSSL commands to:
   - Generate a self-signed CA (ca.key, ca.crt)
   - Generate an ACE server certificate (server.key, server.crt) signed by the CA
   - Generate a client certificate (client.key, client.crt) signed by the CA

2. The server.conf.yaml additions to configure the HTTPS listener on port 7443:
   - sslEnabled: true
   - sslCertificate, sslKey paths
   - sslClientAuth: required
   - sslTruststore: path to ca.crt

3. The curl command to test a successful mTLS request:
   curl --cert client.crt --key client.key --cacert ca.crt https://localhost:7443/api/v1/orders

4. The curl command to test that a request without a client cert is rejected (403 or 401)
```

---

### I5 — API Versioning: Header-Based Routing ESQL

```
Write an IBM ACE ESQL compute module VersionRouter that routes incoming
requests based on the Accept-Version header. Requirements:

1. Read Accept-Version header from InputRoot.HTTPInputHeader."Accept-Version"
2. If value is '2.0' or header is absent: PROPAGATE to 'out1' (v2 flow)
3. If value is '1.0': PROPAGATE to 'out2' (v1 legacy flow)
4. If value is anything else: return HTTP 400 with
   {"error": "Unsupported API version", "supported": ["1.0", "2.0"]}

Also write the deprecation header module for the v1 path that adds:
- Deprecation: true
- Sunset: <date 6 months from now>
- Link: </api/v2/orders>; rel="successor-version"

Show the full flow diagram connecting VersionRouter → v1 path → DeprecationHeaders
→ v1 processing, and VersionRouter → v2 path → v2 processing.
```

---

### I6 — Publish ACE API to IBM API Connect

```
Walk me through publishing an ACE-exposed OpenAPI to IBM API Connect.
Cover:
1. The apic CLI commands to login, list catalogs, and publish an API YAML file
2. What the x-ibm-configuration section in the API YAML needs to contain
   for the invoke policy to reach my ACE server
3. How to configure rate limiting in API Connect (100 calls/minute per app)
4. How to create a Product and Plan in API Connect that wraps the API
5. How to test the API through the API Connect gateway endpoint
6. What changes in API Connect when I want to publish a v2 of the same API
   while keeping v1 live for existing consumers

Use apim.example.com as the API Connect server hostname.
```

---

## 🔴 Troubleshooting Prompts

### T1 — REST API Returns 404 for All Requests

```
My IBM ACE REST API project is deployed and the integration server is running,
but all requests to /api/v1/orders return HTTP 404. The ACE Integration Server
log shows no BIP errors when the request arrives.

Walk me through the diagnostic steps:
1. How to verify the REST API project's base path is /api/v1 (not /api/v1/)
2. How to check the HTTP listener port in server.conf.yaml
3. How to list all deployed flows using the ACE REST Admin API
4. Whether the flow needs a separate HTTPInput node or if the REST API project
   handles routing automatically
5. How to use curl -v to see the exact response headers and identify whether
   ACE is serving the 404 or a reverse proxy in front of it is
```

---

### T2 — JWT Validation: 401 on Every Request Despite Valid Token

```
My ACE JWT validation flow returns HTTP 401 for every request, even with
a valid token from my Keycloak IdP. When I call the introspection endpoint
directly with the same token, it returns active=true.

Debug this step-by-step:
1. How to capture the exact HTTP request ACE sends to the introspection endpoint
   (Content-Type, body encoding, Authorization header for the client_credentials)
2. Whether Keycloak requires a client_id and client_secret for introspection
   (not just the token)
3. Whether the JSON response from Keycloak uses 'active' (boolean) or 'active' (string)
   — ESQL treats them differently
4. How to use the ACE Flow Exerciser to inspect the introspection response tree
   and verify the field names and types
```

---

### T3 — mTLS: Client Certificate Rejected

```
My ACE server is configured for mTLS with sslClientAuth: required.
My curl command with --cert client.crt --key client.key returns:
  curl: (56) OpenSSL SSL_read: error:14094418 ... tlsv1 alert unknown ca

This means the server rejected my client certificate. What are the possible causes:
1. The client certificate is not signed by the CA in ACE's sslTruststore
2. The CA certificate in sslTruststore is expired
3. The client certificate CN or SAN does not match ACE's expected subject
4. The ACE server is not sending the list of acceptable CAs during the TLS handshake

For each cause, show how to diagnose using: openssl s_client, openssl verify,
and the ACE Integration Server error log.
```

---

### T4 — Rate Limiter Returns 429 to All Clients

```
My ACE in-flow rate limiter (using a DB counter table) started returning
HTTP 429 to all clients, even those that have sent fewer than 100 requests
in the last 60 seconds. The DB table ACE_RLIMIT.RATE_LIMIT has rows with
very high REQUEST_COUNT values for every CLIENT_IP.

What is likely wrong with my rate limiter query? Diagnose:
1. Whether the rolling window WHERE WINDOW_START > CURRENT_TIMESTAMP - INTERVAL '60' SECOND
   is correct or off-by-one
2. Whether concurrent ACE flow threads are double-counting (race condition on the counter)
3. Whether the WINDOW_START column is being updated correctly when new requests arrive
4. How to reset the rate limit counters without restarting ACE
5. Why you should prefer API Connect for rate limiting instead of in-flow DB counters
```

---

### T5 — SOAP Service: ACE Returns 500 for Valid SOAP Request

```
My ACE SOAPInput flow is deployed and the WSDL is accessible at the
correct URL. When I send a valid SOAP 1.1 request using SoapUI, ACE returns
HTTP 500 with an empty SOAP Fault body. No useful error appears in the ACE log.

Walk me through diagnosing SOAP service failures in IBM ACE:
1. How to enable SOAPInput diagnostic tracing in server.conf.yaml
2. Whether the WSDL's targetNamespace and the SOAPAction header must match exactly
3. How to use the ACE Flow Exerciser to test the flow with the raw SOAP XML
   and inspect the parsed XMLNSC tree
4. Common causes of empty SOAP faults (body parsing failure, namespace mismatch,
   schema validation error with no error handler)
5. How to return a properly structured SOAP Fault from an ACE error handler subflow
```
