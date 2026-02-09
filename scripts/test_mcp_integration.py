import httpx
import asyncio
import sys

async def main():
    print("Testing Backend -> MCP Integration...")
    
    # 1. Check Backend Health (should report MCP status)
    async with httpx.AsyncClient() as client:
        try:
            print("Checking Backend Health...")
            resp = await client.get("http://localhost:8011/health", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                mcp_status = data.get("dependencies", {}).get("mcp_server", {}).get("ok")
                print(f"Backend Health: OK. MCP Connected: {mcp_status}")
                if not mcp_status:
                    print("WARNING: MCP Server reported as not connected!")
            else:
                print(f"Backend Health Failed: {resp.status_code}")
                return
        except Exception as e:
            print(f"Failed to connect to Backend: {e}")
            return

    # 2. Check Proxy Endpoint
    async with httpx.AsyncClient() as client:
        try:
            print("Checking Proxy Endpoint (/api/agentic/status)...")
            resp = await client.get("http://localhost:8011/api/agentic/system/status", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                print("Proxy Status: OK")
                print(f"Active Agents: {len(data.get('active_agents', []))}")
            else:
                print(f"Proxy Endpoint Failed: {resp.status_code}")
                # print(resp.text)
        except Exception as e:
            print(f"Failed to connect to Proxy Endpoint: {e}")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
