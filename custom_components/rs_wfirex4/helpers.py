"""Helper utilities for rs_wfirex4 integration."""

import asyncio
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo, format_mac

from .const import DEFAULT_NAME, DOMAIN, PORT

_LOGGER = logging.getLogger(__name__)


def build_device_info(mac: str, name: str | None = None) -> DeviceInfo:
    """Return DeviceInfo for a device identified by its MAC."""
    return DeviceInfo(
        identifiers={(DOMAIN, mac)},
        manufacturer="RATOC Systems",
        model="RS-WFIREX4",
        name=name or build_default_name_with_mac(mac),
    )


def build_default_name_with_mac(mac: str):
    """Return Default name with last three digits of the MAC address."""
    return f"{DEFAULT_NAME} ({format_mac(mac)[-8:].replace(':', '')})"


async def resolve_ip_by_mac(hass, mac: str) -> str | None:
    """Resolve IP by MAC address using HomeAssistant's device registry."""
    mac = mac.lower()
    dev_reg = dr.async_get(hass)

    for device in dev_reg.devices.values():
        for conn in device.connections:
            if conn[1].lower() == mac:
                if device.ip_addresses:
                    return device.ip_addresses[0]

    return None


async def test_connection(hass: HomeAssistant, host: str, mac: str) -> str | None:
    """
    Try connecting to host:60001.
    If fails, attempt resolve_ip_by_mac and return new IP if successful.
    Return:
      - host (str): confirmed reachable host
      - new_host (str): resolved IP when host=NG but MAC=OK
      - None → connection failed completely
    """

    # 1. First try configured host
    if host:
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(host, PORT), timeout=5
            )
            writer.close()
            await writer.wait_closed()
            return host
        except Exception:
            _LOGGER.debug("Connection test failed for %s", host)

    # 2. Resolve by MAC (fallback)
    if mac:
        try:
            new_ip = await resolve_ip_by_mac(hass, mac)
            if new_ip:
                _LOGGER.warning("Resolved new IP %s for MAC %s", new_ip, mac)
                _, writer = await asyncio.wait_for(
                    asyncio.open_connection(new_ip, PORT), timeout=5
                )
                writer.close()
                await writer.wait_closed()
                return new_ip
        except Exception:
            _LOGGER.debug("Connection test via MAC %s failed", mac)

    return None
