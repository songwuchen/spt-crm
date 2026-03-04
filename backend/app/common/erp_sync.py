"""
ERP Sync Framework — provides a pluggable interface for syncing data with
external ERP/MES systems (e.g., Kingdee K3, SAP, Yonyou).

Integration endpoints are configured in the `integration_endpoints` table.
Each endpoint has a system_code (e.g., 'erp_k3', 'mes_xxx') and auth config.

Usage:
    from app.common.erp_sync import get_erp_client, sync_contract_to_erp

    client = await get_erp_client(db, tenant_id, "erp_k3")
    result = await client.push_contract(contract_data)
"""
import logging
from abc import ABC, abstractmethod
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.admin.models import IntegrationEndpoint

logger = logging.getLogger("spt_crm.erp_sync")


class ERPClientBase(ABC):
    """Base class for ERP integration clients."""

    def __init__(self, endpoint: IntegrationEndpoint):
        self.endpoint = endpoint
        self.base_url = endpoint.base_url or ""
        self.auth_config = endpoint.auth_config_json or {}
        self.system_code = endpoint.system_code

    @abstractmethod
    async def authenticate(self) -> bool:
        """Authenticate with the ERP system. Returns True on success."""
        ...

    @abstractmethod
    async def push_contract(self, contract_data: dict) -> dict:
        """Push a signed contract to the ERP for order creation."""
        ...

    @abstractmethod
    async def push_invoice(self, invoice_data: dict) -> dict:
        """Push invoice data to the ERP."""
        ...

    @abstractmethod
    async def pull_payment(self, reference_no: str) -> dict | None:
        """Pull payment receipt status from the ERP."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the ERP connection is healthy."""
        ...


class GenericERPClient(ERPClientBase):
    """Generic ERP client using REST API with configurable auth.

    Supports auth types: apikey, basic, oauth2.
    Endpoint config in integration_endpoints.auth_config_json:
        apikey:  {"api_key": "xxx", "header_name": "X-API-Key"}
        basic:   {"username": "xxx", "password": "xxx"}
        oauth2:  {"token_url": "https://...", "client_id": "xxx", "client_secret": "xxx"}
    """

    def __init__(self, endpoint: IntegrationEndpoint):
        super().__init__(endpoint)
        self._token: str | None = None

    async def _get_headers(self) -> dict:
        """Build request headers based on auth type."""
        headers = {"Content-Type": "application/json"}
        auth_type = self.endpoint.auth_type or "apikey"

        if auth_type == "apikey":
            header_name = self.auth_config.get("header_name", "X-API-Key")
            api_key = self.auth_config.get("api_key", "")
            headers[header_name] = api_key

        elif auth_type == "basic":
            import base64
            username = self.auth_config.get("username", "")
            password = self.auth_config.get("password", "")
            cred = base64.b64encode(f"{username}:{password}".encode()).decode()
            headers["Authorization"] = f"Basic {cred}"

        elif auth_type == "oauth2":
            if not self._token:
                await self.authenticate()
            if self._token:
                headers["Authorization"] = f"Bearer {self._token}"

        return headers

    async def authenticate(self) -> bool:
        """Authenticate via OAuth2 client credentials flow."""
        if self.endpoint.auth_type != "oauth2":
            return True  # No auth needed for apikey/basic

        token_url = self.auth_config.get("token_url", "")
        client_id = self.auth_config.get("client_id", "")
        client_secret = self.auth_config.get("client_secret", "")

        if not token_url:
            logger.error(f"[{self.system_code}] No token_url configured for OAuth2")
            return False

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(token_url, data={
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret,
                })
                resp.raise_for_status()
                data = resp.json()
                self._token = data.get("access_token")
                logger.info(f"[{self.system_code}] OAuth2 authenticated successfully")
                return bool(self._token)
        except Exception as e:
            logger.error(f"[{self.system_code}] OAuth2 authentication failed: {e}")
            return False

    async def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        """Make an authenticated request to the ERP API."""
        url = f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
        headers = await self._get_headers()

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                if method == "GET":
                    resp = await client.get(url, headers=headers)
                else:
                    resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"[{self.system_code}] HTTP {e.response.status_code}: {e.response.text[:200]}")
            return {"success": False, "error": f"HTTP {e.response.status_code}"}
        except Exception as e:
            logger.error(f"[{self.system_code}] Request failed: {e}")
            return {"success": False, "error": str(e)}

    async def push_contract(self, contract_data: dict) -> dict:
        """Push contract to ERP for sales order creation."""
        path = self.auth_config.get("contract_push_path", "/api/sales-orders")
        logger.info(f"[{self.system_code}] Pushing contract {contract_data.get('contract_no', '')}")
        return await self._request("POST", path, contract_data)

    async def push_invoice(self, invoice_data: dict) -> dict:
        """Push invoice to ERP."""
        path = self.auth_config.get("invoice_push_path", "/api/invoices")
        logger.info(f"[{self.system_code}] Pushing invoice {invoice_data.get('invoice_no', '')}")
        return await self._request("POST", path, invoice_data)

    async def pull_payment(self, reference_no: str) -> dict | None:
        """Pull payment receipt by reference number."""
        path = self.auth_config.get("payment_pull_path", "/api/payments")
        logger.info(f"[{self.system_code}] Pulling payment {reference_no}")
        result = await self._request("GET", f"{path}?ref={reference_no}")
        if result.get("success") is False:
            return None
        return result

    async def health_check(self) -> bool:
        """Check ERP connectivity."""
        path = self.auth_config.get("health_path", "/api/health")
        try:
            result = await self._request("GET", path)
            return result.get("success") is not False
        except Exception:
            return False


# -------- Client Registry --------

_CLIENT_REGISTRY: dict[str, type[ERPClientBase]] = {
    "erp_k3": GenericERPClient,
    "erp_sap": GenericERPClient,
    "erp_yonyou": GenericERPClient,
    "mes": GenericERPClient,
}


def register_erp_client(system_code: str, client_class: type[ERPClientBase]):
    """Register a custom ERP client implementation."""
    _CLIENT_REGISTRY[system_code] = client_class


async def get_erp_client(db: AsyncSession, tenant_id: str, system_code: str) -> ERPClientBase | None:
    """Get an ERP client for the given tenant and system.

    Returns None if no active endpoint is configured.
    """
    ep = (await db.execute(
        select(IntegrationEndpoint).where(
            IntegrationEndpoint.tenant_id == tenant_id,
            IntegrationEndpoint.system_code == system_code,
            IntegrationEndpoint.status == "active",
        )
    )).scalar_one_or_none()

    if not ep:
        logger.debug(f"No active endpoint for tenant={tenant_id}, system={system_code}")
        return None

    client_cls = _CLIENT_REGISTRY.get(system_code, GenericERPClient)
    return client_cls(ep)


# -------- High-Level Sync Functions --------

async def sync_contract_to_erp(db: AsyncSession, tenant_id: str, contract_data: dict) -> dict:
    """Sync a signed contract to the configured ERP system.

    Looks for any ERP endpoint (erp_k3, erp_sap, etc.) and pushes the contract.
    Returns the sync result or an error dict.
    """
    for code in ("erp_k3", "erp_sap", "erp_yonyou"):
        client = await get_erp_client(db, tenant_id, code)
        if client:
            result = await client.push_contract(contract_data)
            logger.info(f"Contract synced to {code}: {result}")
            return {"system": code, "result": result}

    return {"success": False, "error": "No ERP endpoint configured"}


async def sync_invoice_to_erp(db: AsyncSession, tenant_id: str, invoice_data: dict) -> dict:
    """Sync an invoice to the configured ERP system."""
    for code in ("erp_k3", "erp_sap", "erp_yonyou"):
        client = await get_erp_client(db, tenant_id, code)
        if client:
            result = await client.push_invoice(invoice_data)
            return {"system": code, "result": result}

    return {"success": False, "error": "No ERP endpoint configured"}
