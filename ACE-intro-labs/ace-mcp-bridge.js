#!/usr/bin/env node

/**
 * MCP Bridge Server for IBM App Connect Enterprise
 * This server acts as an MCP-compliant bridge to the ACE REST API
 */

const { Server } = require('@modelcontextprotocol/sdk/server/index.js');
const { StdioServerTransport } = require('@modelcontextprotocol/sdk/server/stdio.js');
const {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} = require('@modelcontextprotocol/sdk/types.js');
const https = require('https');
const http = require('http');

// ACE server configuration from environment
const ACE_URL = process.env.ACE_MCP_URL || 'http://127.0.0.1:7750/server';
const REJECT_UNAUTHORIZED = process.env.NODE_TLS_REJECT_UNAUTHORIZED !== '0';

// Create MCP server
const server = new Server(
  {
    name: 'ace-mcp-bridge',
    version: '1.0.0',
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

// Helper function to make HTTP/HTTPS requests to ACE server
function makeAceRequest(method, path, data = null) {
  return new Promise((resolve, reject) => {
    const url = new URL(path, ACE_URL);
    const isHttps = url.protocol === 'https:';
    const client = isHttps ? https : http;
    
    const options = {
      hostname: url.hostname,
      port: url.port,
      path: url.pathname + url.search,
      method: method,
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json, text/event-stream',
      },
      rejectUnauthorized: REJECT_UNAUTHORIZED,
    };

    if (data) {
      const jsonData = JSON.stringify(data);
      options.headers['Content-Length'] = Buffer.byteLength(jsonData);
    }

    const req = client.request(options, (res) => {
      let body = '';
      res.on('data', (chunk) => body += chunk);
      res.on('end', () => {
        try {
          const response = JSON.parse(body);
          resolve(response);
        } catch (e) {
          resolve({ data: body, statusCode: res.statusCode });
        }
      });
    });

    req.on('error', reject);
    
    if (data) {
      req.write(JSON.stringify(data));
    }
    
    req.end();
  });
}

// List available tools
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: 'ace_api_call',
        description: 'Make a call to the IBM App Connect Enterprise REST API',
        inputSchema: {
          type: 'object',
          properties: {
            method: {
              type: 'string',
              description: 'HTTP method (GET, POST, PUT, DELETE, etc.)',
              enum: ['GET', 'POST', 'PUT', 'DELETE', 'PATCH'],
            },
            path: {
              type: 'string',
              description: 'API endpoint path (e.g., /apiv2/servers)',
            },
            body: {
              type: 'object',
              description: 'Request body for POST/PUT/PATCH requests',
            },
          },
          required: ['method', 'path'],
        },
      },
      {
        name: 'list_remote_tools',
        description: 'List all available tools from the remote MCP server',
        inputSchema: {
          type: 'object',
          properties: {},
        },
      },
      {
        name: 'call_remote_tool',
        description: 'Call a tool on the remote MCP server',
        inputSchema: {
          type: 'object',
          properties: {
            tool_name: {
              type: 'string',
              description: 'Name of the tool to call',
            },
            arguments: {
              type: 'object',
              description: 'Arguments to pass to the tool',
            },
          },
          required: ['tool_name', 'arguments'],
        },
      },
    ],
  };
});

// Handle tool calls
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  if (request.params.name === 'ace_api_call') {
    const { method, path, body } = request.params.arguments;
    
    try {
      const response = await makeAceRequest(method, path, body);
      
      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify(response, null, 2),
          },
        ],
      };
    } catch (error) {
      return {
        content: [
          {
            type: 'text',
            text: `Error calling ACE API: ${error.message}`,
          },
        ],
        isError: true,
      };
    }
  }
  
  if (request.params.name === 'list_remote_tools') {
    try {
      const response = await makeAceRequest('POST', '/server', {
        jsonrpc: '2.0',
        method: 'tools/list',
        params: {},
        id: 1,
      });
      
      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify(response, null, 2),
          },
        ],
      };
    } catch (error) {
      return {
        content: [
          {
            type: 'text',
            text: `Error listing remote tools: ${error.message}`,
          },
        ],
        isError: true,
      };
    }
  }
  
  if (request.params.name === 'call_remote_tool') {
    const { tool_name, arguments: toolArgs } = request.params.arguments;
    
    try {
      const response = await makeAceRequest('POST', '/server', {
        jsonrpc: '2.0',
        method: 'tools/call',
        params: {
          name: tool_name,
          arguments: toolArgs,
        },
        id: 1,
      });
      
      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify(response, null, 2),
          },
        ],
      };
    } catch (error) {
      return {
        content: [
          {
            type: 'text',
            text: `Error calling remote tool: ${error.message}`,
          },
        ],
        isError: true,
      };
    }
  }
  
  throw new Error(`Unknown tool: ${request.params.name}`);
});

// Start the server
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch((error) => {
  console.error('Fatal error:', error);
  process.exit(1);
});

// Made with Bob
