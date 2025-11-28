"""rs_wfirex4 integration entrypoints."""

from __future__ import annotations

import asyncio
import logging

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, PORT
from .helpers import resolve_ip_by_mac

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "remote"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the integration via YAML (import flow)."""
    if DOMAIN not in config:
        return True

    for entry_conf in config[DOMAIN]:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data=entry_conf,
            )
        )

    return True


async def _test_connection(hass: HomeAssistant, host: str, mac: str) -> str | None:
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
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(new_ip, PORT), timeout=5
                )
                writer.close()
                await writer.wait_closed()
                return new_ip
        except Exception:
            _LOGGER.debug("Connection test via MAC %s failed", mac)

    return None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up config entry with connection check BEFORE forwarding platforms."""

    hass.data.setdefault(
        DOMAIN,
        {
            "coordinators": {},
            "fetchers": {},
        },
    )

    host = entry.data.get(CONF_HOST, "")
    mac = entry.data.get(CONF_MAC, "").upper()

    # -----------------------
    # 1. Check connection
    # -----------------------
    try:
        reachable_host = await _test_connection(hass, host, mac)
    except Exception as err:
        _LOGGER.exception("Unexpected error during pre-setup connection test")
        raise ConfigEntryNotReady from err

    if not reachable_host:
        # Home Assistant は自動リトライするので OK
        raise ConfigEntryNotReady("Device not reachable during setup")

    # -----------------------
    # 2. Save if IP changed
    # -----------------------
    if reachable_host != host:
        new_data = {**entry.data, CONF_HOST: reachable_host}
        hass.config_entries.async_update_entry(entry, data=new_data)
        host = reachable_host
        _LOGGER.info("Updated host for %s to %s", entry.entry_id, host)

    # -----------------------
    # 3. forward to platform
    # -----------------------
    hass.data[DOMAIN][entry.entry_id] = entry.data

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
