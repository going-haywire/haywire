"""PROTOTYPE client check — wayfinder ticket 09. THROWAWAY.

Exercises the mounted MCP endpoint with the official SDK's own client while
verifying the studio's normal HTTP + socket.io surfaces stay healthy around it.

Run AFTER farmhand_mount_prototype.py is serving on :8099.
"""

import asyncio
import json

import httpx

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

BASE = "http://127.0.0.1:8099"
MCP_URL = f"{BASE}/mcp"


def _tool_json(result) -> dict:
    return json.loads(result.content[0].text)


async def main() -> None:
    print("== 1) studio surfaces BEFORE MCP traffic ==")
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{BASE}/")
        print(f"GET /            -> {r.status_code} {r.headers.get('content-type')}")
        r = await c.get(f"{BASE}/socket.io/?EIO=4&transport=polling")
        print(f"socket.io shake  -> {r.status_code} {r.text[:50]!r}")

    print("== 2) MCP session ==")
    async with streamablehttp_client(MCP_URL) as (read, write, _get_sid):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            print(f"initialize       -> {init.serverInfo.name}, protocol {init.protocolVersion}")
            print(f"  capabilities   -> tools.listChanged={init.capabilities.tools.listChanged}")
            tools = await session.list_tools()
            print(f"tools/list       -> {[t.name for t in tools.tools]}")

            before = _tool_json(await session.call_tool("studio_list_graphs", {}))
            print(f"list before      -> count={before['count']} affinity={before['affinity']}")

            created = _tool_json(await session.call_tool("haystack_create_graph", {}))
            print(f"create           -> {created['created']!r} affinity={created['affinity']}")

            after = _tool_json(await session.call_tool("studio_list_graphs", {}))
            print(
                f"list after       -> count={after['count']} entries={[e['display_name'] for e in after['entries']]}"
            )

    print("== 3) studio surfaces AFTER MCP traffic ==")
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{BASE}/")
        print(f"GET /            -> {r.status_code}")
        r = await c.get(f"{BASE}/socket.io/?EIO=4&transport=polling")
        print(f"socket.io shake  -> {r.status_code} {r.text[:50]!r}")

    print("== DONE ==")


if __name__ == "__main__":
    asyncio.run(main())
