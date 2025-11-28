"""Helper utilities for rs_wfirex4 integration."""

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo


def build_device_info(mac: str, name: str | None = None) -> DeviceInfo:
    """Return DeviceInfo for a device identified by its MAC."""
    return DeviceInfo(
        identifiers={("rs_wfirex4", mac)},
        manufacturer="RATOC Systems",
        model="WFIREX4",
        name=name or f"WFIREX4 ({mac[-6]})",
    )


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
