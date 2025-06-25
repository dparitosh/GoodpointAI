import httpx
import logging
import time
from typing import Optional, List
from fastapi import HTTPException
from .models import NiFiProcessGroupSummary, NiFiFlowResponse, NiFiStatusResponse

logger = logging.getLogger(__name__)

class NiFiClient:
    def __init__(self, base_url: str, username: Optional[str] = None, password: Optional[str] = None):
        self.base_url = base_url
        self.username = username
        self.password = password
        self._token = None
        self._token_expiry = 0

    async def _get_token(self):
        if self.username and self.password:
            if self._token and self._token_expiry > time.time():
                return self._token
            try: # nosec B501
                # nosec start
                # B501: Consider using httpx with verify=True for production environments.
                async with httpx.AsyncClient(base_url=self.base_url, verify=False) as client: # verify=False for self-signed certs, use proper certs in prod
                    response = await client.post("/access/token", data={"username": self.username, "password": self.password})
                    response.raise_for_status()
                    self._token = response.text # Assuming JWT token
                    self._token_expiry = time.time() + 55 * 60 # Token typically valid for 1 hour, refresh after 55 min
                    logger.info("Successfully obtained NiFi access token.")
                    return self._token
            except httpx.HTTPStatusError as e:
                logger.error(f"Failed to get NiFi token: {e.response.status_code} - {e.response.text}")
                raise HTTPException(status_code=500, detail="Failed to authenticate with NiFi.")
            except httpx.RequestError as e:
                logger.error(f"Network error while trying to get NiFi token: {e}")
                raise HTTPException(status_code=500, detail="Network error connecting to NiFi.")
        return None

    async def _request(self, method: str, path: str, **kwargs):
        headers = kwargs.pop("headers", {})
        token = await self._get_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        
        try: # nosec B501
            # nosec start
            # B501: Consider using httpx with verify=True for production environments.
            async with httpx.AsyncClient(base_url=self.base_url, headers=headers, verify=False) as client: # verify=False for self-signed certs, use proper certs in prod
                response = await client.request(method, path, **kwargs)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"NiFi API error for {path}: {e.response.status_code} - {e.response.text}")
            raise HTTPException(status_code=e.response.status_code, detail=f"NiFi API error: {e.response.text}")
        except httpx.RequestError as e:
            logger.error(f"Network error connecting to NiFi at {path}: {e}")
            raise HTTPException(status_code=500, detail=f"Network error connecting to NiFi: {e}")

    async def get_root_process_group_id(self) -> str:
        response = await self._request("GET", "/flow/about")
        return response.get("controllerContext", {}).get("id")

    async def get_process_groups(self) -> List[NiFiProcessGroupSummary]:
        root_id = await self.get_root_process_group_id()
        response = await self._request("GET", f"/flow/process-groups/{root_id}")
        process_groups_data = response.get("processGroupFlow", {}).get("flow", {}).get("processGroups", [])
        return [NiFiProcessGroupSummary(id=pg['id'], name=pg['component']['name']) for pg in process_groups_data]

    async def get_flow_diagram(self, process_group_id: str) -> NiFiFlowResponse:
        response = await self._request("GET", f"/flow/process-groups/{process_group_id}/flow")
        return NiFiFlowResponse(**response)

    async def get_status(self, process_group_id: str) -> NiFiStatusResponse:
        response = await self._request("GET", f"/flow/process-groups/{process_group_id}/status")
        return NiFiStatusResponse(**response)

    async def _update_processor_state(self, processor_id: str, state: str):
        """Helper to update processor state, handling NiFi's revision mechanism."""
        try:
            proc_details = await self._request("GET", f"/processors/{processor_id}")
            current_revision = proc_details.get('revision', {'version': 0})
            
            payload = {
                "revision": current_revision,
                "state": state,
                "component": {
                    "id": processor_id,
                    "state": state
                }
            }
            return await self._request("PUT", f"/processors/{processor_id}", json=payload)
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to update processor {processor_id} state due to conflict or other error: {e.response.text}")
            raise HTTPException(status_code=e.response.status_code, detail=f"Failed to update processor state: {e.response.text}")

    async def start_processor(self, processor_id: str):
        return await self._update_processor_state(processor_id, "RUNNING")

    async def stop_processor(self, processor_id: str):
        return await self._update_processor_state(processor_id, "STOPPED")