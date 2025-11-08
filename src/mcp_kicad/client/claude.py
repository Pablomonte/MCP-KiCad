#!/usr/bin/env python3
"""
KiCad MCP Client - AI assistant for KiCad PCB design using Anthropic Claude
"""

import asyncio
import json
import os
import sys
from typing import Optional, List, Dict, Any

from anthropic import Anthropic
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class KiCadAIClient:
    """AI client for KiCad using MCP and Claude"""

    def __init__(self, api_key: str):
        self.client = Anthropic(api_key=api_key)
        self.session: Optional[ClientSession] = None
        self.available_tools: List[Dict[str, Any]] = []
        self.conversation_history: List[Dict[str, Any]] = []

    async def connect_to_server(self, server_script_path: str):
        """Connect to the MCP server"""

        # Setup server parameters
        server_params = StdioServerParameters(
            command="python3",
            args=[server_script_path],
            env=None
        )

        # Connect using stdio
        stdio_transport = await stdio_client(server_params)
        self.stdio, self.write = stdio_transport

        # Create session
        self.session = ClientSession(self.stdio, self.write)

        # Initialize session
        await self.session.__aenter__()

        # List available tools from server
        tools_result = await self.session.list_tools()

        # Convert MCP tools to Claude format
        self.available_tools = []
        for tool in tools_result.tools:
            self.available_tools.append({
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.inputSchema
            })

        print(f"Connected to KiCad MCP Server")
        print(f"Available tools: {', '.join(t['name'] for t in self.available_tools)}\n")

    async def call_tool(self, tool_name: str, tool_arguments: Dict[str, Any]) -> str:
        """Call a tool on the MCP server"""

        if self.session is None:
            raise RuntimeError("Not connected to server")

        result = await self.session.call_tool(tool_name, tool_arguments)

        # Extract text content from result
        if result.content:
            return result.content[0].text
        return "{}"

    async def chat(self, user_message: str) -> str:
        """Send a message to Claude and handle tool calls"""

        # Add user message to history
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })

        # Initial request to Claude
        response = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4096,
            tools=self.available_tools,
            messages=self.conversation_history
        )

        # Process response and handle tool calls
        while response.stop_reason == "tool_use":
            # Extract assistant message with tool calls
            assistant_message = {
                "role": "assistant",
                "content": response.content
            }
            self.conversation_history.append(assistant_message)

            # Process each tool call
            tool_results = []
            for content_block in response.content:
                if content_block.type == "tool_use":
                    tool_name = content_block.name
                    tool_input = content_block.input
                    tool_use_id = content_block.id

                    print(f"\nCalling tool: {tool_name}")
                    print(f"Arguments: {json.dumps(tool_input, indent=2)}")

                    # Call the tool via MCP
                    try:
                        result_text = await self.call_tool(tool_name, tool_input)
                        print(f"Result: {result_text}\n")

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "content": result_text
                        })
                    except Exception as e:
                        error_msg = f"Error calling tool: {str(e)}"
                        print(f"Error: {error_msg}\n")

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "content": json.dumps({"error": error_msg}),
                            "is_error": True
                        })

            # Add tool results to conversation
            self.conversation_history.append({
                "role": "user",
                "content": tool_results
            })

            # Get next response from Claude
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4096,
                tools=self.available_tools,
                messages=self.conversation_history
            )

        # Final response without tool calls
        assistant_message = {
            "role": "assistant",
            "content": response.content
        }
        self.conversation_history.append(assistant_message)

        # Extract text response
        final_response = ""
        for content_block in response.content:
            if hasattr(content_block, "text"):
                final_response += content_block.text

        return final_response

    async def close(self):
        """Close the connection"""
        if self.session:
            await self.session.__aexit__(None, None, None)


async def main():
    """Main entry point for the client"""

    # Load environment variables
    load_dotenv()

    # Get API key
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not found in environment")
        print("Please create a .env file with your API key:")
        print("  ANTHROPIC_API_KEY=your_key_here")
        sys.exit(1)

    # Get server script path
    if len(sys.argv) < 2:
        server_script = "kicad_mcp_server.py"
        print(f"Using default server script: {server_script}")
    else:
        server_script = sys.argv[1]

    # Verify server script exists
    if not os.path.exists(server_script):
        print(f"Error: Server script not found: {server_script}")
        sys.exit(1)

    # Create client
    client = KiCadAIClient(api_key)

    try:
        # Connect to server
        print("Connecting to KiCad MCP Server...")
        await client.connect_to_server(server_script)

        # Print welcome message
        print("=" * 70)
        print("KiCad AI Assistant")
        print("=" * 70)
        print("\nYou can ask me to help with your PCB design!")
        print("Examples:")
        print("  - 'List all components on the board'")
        print("  - 'Place R1 at position 10, 20 mm'")
        print("  - 'Show me the netlist'")
        print("  - 'Give me layout suggestions for an LED circuit'")
        print("\nType 'quit' or 'exit' to end the session.\n")

        # Chat loop
        while True:
            try:
                user_input = input("You: ").strip()

                if not user_input:
                    continue

                if user_input.lower() in ["quit", "exit", "q"]:
                    print("\nGoodbye!")
                    break

                # Get response from AI
                response = await client.chat(user_input)

                # Print response
                print(f"\nAssistant: {response}\n")

            except KeyboardInterrupt:
                print("\n\nGoodbye!")
                break
            except EOFError:
                break
            except Exception as e:
                print(f"\nError: {str(e)}\n")

    finally:
        # Cleanup
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
