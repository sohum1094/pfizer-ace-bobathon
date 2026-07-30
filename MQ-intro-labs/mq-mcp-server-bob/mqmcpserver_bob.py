#
# Copyright (c) 2025 IBM Corp.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
IBM MQ MCP Server for Bob
This version is specifically configured for IBM Bob integration using stdio transport.
"""

import logging
import httpx
import json
import os

from typing import Any
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("mq-mcp-server-bob")

# MQ Configuration from environment variables
MQ_HOST = os.environ.get("MQ_HOST", "localhost")
MQ_PORT = os.environ.get("MQ_PORT", "9443")
URL_BASE = f"https://{MQ_HOST}:{MQ_PORT}/ibmmq/rest/v3/admin/"

# Authentication credentials
USER_NAME = os.environ.get("MQ_USER", "admin")
PASSWORD = os.environ.get("MQ_PASSWORD", "passw0rd")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@mcp.tool()
async def dspmq() -> str:
    """List available queue managers and their running status.
    
    This tool queries the MQ REST API to retrieve information about all queue managers
    that are local to the mqweb server, including their current state (running/stopped).
    
    Returns:
        str: Formatted list of queue managers with their names and running status
    """
    headers = {
        "Content-Type": "application/json",
        "ibm-mq-rest-csrf-token": "token"
    }    
    
    url = URL_BASE + "qmgr/"

    auth = httpx.BasicAuth(username=USER_NAME, password=PASSWORD)
    async with httpx.AsyncClient(verify=False, auth=auth) as client:
        try:            
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            return prettify_dspmq(response.content)
        except httpx.HTTPStatusError as err:
            logger.error(f"HTTP error occurred: {err}")
            return f"HTTP Error: {err.response.status_code} - {err.response.text}"
        except Exception as err:
            logger.error(f"Error in dspmq: {err}")
            return f"Error: {str(err)}"


@mcp.tool()
async def get_status() -> str:
    """Get MQ status as JSON for dashboard and monitoring purposes.
    
    This tool retrieves the current status of all queue managers in JSON format,
    which can be used for building dashboards or monitoring applications.
    
    Returns:
        str: JSON string containing queue manager status information
    """
    headers = {
        "Content-Type": "application/json",
        "ibm-mq-rest-csrf-token": "token"
    }    
    
    url = URL_BASE + "qmgr/"
    auth = httpx.BasicAuth(username=USER_NAME, password=PASSWORD)
    async with httpx.AsyncClient(verify=False, auth=auth) as client:
        try:            
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            return response.text
        except Exception as err:
            logger.error(f"Error in get_status: {err}")
            return json.dumps({"error": str(err)})


def prettify_dspmq(payload: bytes) -> str:
    """Format the dspmq output for better readability.
    
    Args:
        payload: Raw JSON response from the MQ REST API
        
    Returns:
        str: Formatted output with each queue manager on its own line
    """
    try:
        jsonOutput = json.loads(payload.decode("utf-8"))
        prettifiedOutput = "\n---\n"
        for x in jsonOutput.get('qmgr', []):
            prettifiedOutput += f"name = {x['name']}, running = {x['state']}\n---\n"
        return prettifiedOutput
    except Exception as err:
        logger.error(f"Error prettifying dspmq output: {err}")
        return f"Error formatting output: {str(err)}"


@mcp.tool()
async def runmqsc(qmgr_name: str, mqsc_command: str) -> str:
    """Run an MQSC command against a specific queue manager.
    
    This tool allows you to execute MQSC (MQ Script Commands) against a queue manager
    using the MQ REST API. This is useful for administrative tasks like creating queues,
    channels, or querying MQ objects.
    
    Args:
        qmgr_name: The name of the queue manager to run the command against
        mqsc_command: The MQSC command to execute (e.g., "DISPLAY QLOCAL(*)")
        
    Returns:
        str: Formatted output of the MQSC command execution
        
    Examples:
        - Display all local queues: runmqsc("QM1", "DISPLAY QLOCAL(*)")
        - Display queue manager status: runmqsc("QM1", "DISPLAY QMGR")
        - Create a queue: runmqsc("QM1", "DEFINE QLOCAL(MY.QUEUE)")
    """
    headers = {
        "Content-Type": "application/json",
        "ibm-mq-rest-csrf-token": "a"
    }
    
    data = json.dumps({
        "type": "runCommand",
        "parameters": {
            "command": mqsc_command
        }
    })
    
    url = URL_BASE + f"action/qmgr/{qmgr_name}/mqsc"

    auth = httpx.BasicAuth(username=USER_NAME, password=PASSWORD)
    async with httpx.AsyncClient(verify=False, auth=auth) as client:
        try:            
            response = await client.post(url, data=data, headers=headers, timeout=30.0)
            response.raise_for_status()
            return prettify_runmqsc(response.content)
        except httpx.HTTPStatusError as err:
            logger.error(f"HTTP error in runmqsc: {err}")
            return f"HTTP Error: {err.response.status_code} - {err.response.text}"
        except Exception as err:
            logger.error(f"Error in runmqsc: {err}")
            return f"Error: {str(err)}"


def prettify_runmqsc(payload: bytes) -> str:
    """Format the runmqsc output for better readability.
    
    Handles both z/OS and distributed queue managers with different output formats.
    
    Args:
        payload: Raw JSON response from the MQ REST API
        
    Returns:
        str: Formatted output with each command response on its own line
    """
    try:
        jsonOutput = json.loads(payload.decode("utf-8"))
        prettifiedOutput = "\n---\n"
        
        for x in jsonOutput.get('commandResponse', []):
            text_lines = x.get('text', [])
            if not text_lines:
                continue
                
            # z/OS format detection
            if text_lines[0].startswith("CSQN205I"):
                # Remove leading and trailing messages for z/OS
                if len(text_lines) > 2:
                    text_lines = text_lines[1:-1]
                for y in text_lines:
                    prettifiedOutput += y[15:] + "\n---\n"
            # Distributed format
            else:
                prettifiedOutput += text_lines[0] + "\n---\n"
        
        return prettifiedOutput
    except Exception as err:
        logger.error(f"Error prettifying runmqsc output: {err}")
        return f"Error formatting output: {str(err)}"


if __name__ == "__main__":
    # Run the server using stdio transport for Bob integration
    logger.info("Starting MQ MCP Server for Bob (stdio transport)")
    logger.info(f"Connecting to MQ at {MQ_HOST}:{MQ_PORT}")
    mcp.run(transport='stdio')
