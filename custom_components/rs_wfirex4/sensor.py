from __future__ import annotations

import asyncio
import logging
import random
import time
from datetime import timedelta

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.components.sensor.const import SensorStateClass
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    LIGHT_LUX,
    PERCENTAGE,
    UnitOfTemperature,
)
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN, PORT
from .helpers import build_default_name_with_mac, build_device_info, resolve_ip_by_mac

_LOGGER = logging.getLogger(__name__)
CONF_ATTRIBUTION = ""

# ---- Tuning knobs ----
CONNECT_TIMEOUT = 4.0  # Intentionally short; on a LAN, ~3–6s is usually sufficient.
READ_TIMEOUT = 4.0  # Response wait time; on a LAN, ~3–8s is typical.
MAX_ATTEMPTS = 3  # First try + two retries.
BACKOFF_BASE = 0.5  # 0.5s, 1.0s, 2.0s...
BACKOFF_CAP = 2.0  # Cap the backoff to avoid waiting too long.
JITTER = 0.2  # Small random jitter to avoid synchronized retries.
MIN_LEN = 12  # Minimum response length required (we parse up to data[11]).

# Sensor type list
SENSOR_TYPES = {
    "temperature": (
        "Temperature",
        UnitOfTemperature.CELSIUS,
        SensorDeviceClass.TEMPERATURE,
        SensorStateClass.MEASUREMENT,
    ),
    "humidity": (
        "Humidity",
        PERCENTAGE,
        SensorDeviceClass.HUMIDITY,
        SensorStateClass.MEASUREMENT,
    ),
    "light": (
        "Light",
        LIGHT_LUX,
        SensorDeviceClass.ILLUMINANCE,
        SensorStateClass.MEASUREMENT,
    ),
    "reliability": ("Reliability", PERCENTAGE, SensorDeviceClass.POWER_FACTOR, None),
}

_LOGGER = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Setup
async def async_setup_entry(hass, entry, async_add_entities):
    """Set up sensors from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    opts = entry.options

    host = data.get(CONF_HOST)
    mac = format_mac(data.get(CONF_MAC))
    name = data.get(CONF_NAME, build_default_name_with_mac(mac))

    temp_offset = opts.get("temp_offset", data.get("temp_offset", 0.0))
    humi_offset = opts.get("humi_offset", data.get("humi_offset", 0.0))

    # Coordinator is prepared in __init__.py BEFORE async_forward_entry_setups().
    # Keep platform setup lightweight; avoid raising ConfigEntryNotReady here.
    coordinator = hass.data[DOMAIN]["coordinators"].get(mac)
    if coordinator is None:
        # Fallback (should be rare): create a coordinator without forcing a first refresh here.
        scan_interval = opts.get("scan_interval", 60)
        fetcher = hass.data[DOMAIN]["fetchers"].get(mac) or Wfirex4Fetcher(
            host,
            mac,
            temp_offset,
            humi_offset,
            scan_interval,
            entry,
            hass,
        )
        hass.data[DOMAIN]["fetchers"].setdefault(mac, fetcher)
        coordinator = hass.data[DOMAIN]["coordinators"][mac] = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name=name,
            update_interval=timedelta(seconds=scan_interval),
            update_method=fetcher.get_sensor_data,
        )

    # Create entities for each exposed sensor type.
    entities = []
    for sensor_type in SENSOR_TYPES.keys():
        entities.append(WfirexCoordinatorSensor(coordinator, mac, name, sensor_type))
    async_add_entities(entities, update_before_add=True)


async def async_update_entry_host(hass, entry, new_host: str):
    """Update the stored host (IP address) in the ConfigEntry."""
    if entry.data.get("host") != new_host:
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, "host": new_host}
        )
        _LOGGER.info("Updated host for %s to %s", entry.entry_id, new_host)


# ----------------------------------------------------------------------
# Coordinator-based Sensor Entity
class WfirexCoordinatorSensor(CoordinatorEntity, SensorEntity):  # pyright: ignore[reportIncompatibleVariableOverride]
    """Representation of a WFIREX4 sensor managed via DataUpdateCoordinator."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        mac: str,
        name: str,
        sensor_type: str,
    ) -> None:
        """Initialize the WFIREX4 sensor entity.

        Args:
            coordinator: Shared data update coordinator.
            mac: MAC address of the device.
            name: User-defined device name (e.g. "Living").
            sensor_type: Key identifying the type of sensor (e.g. "temperature").
        """
        super().__init__(coordinator)

        self.type = sensor_type

        # Entity name ("Living Temperature")
        self._attr_name = f"{name} {SENSOR_TYPES[self.type][0]}"

        # Unique ID ("wfirex4_112233_temperature")
        mac_suffix = format_mac(mac)
        self._attr_unique_id = f"wfirex4_{mac_suffix}_{self.type}"

        # Device registry
        self._attr_device_info = build_device_info(mac, name)

        # Sensor metadata
        self._attr_native_unit_of_measurement = SENSOR_TYPES[self.type][1]
        self._attr_device_class = SENSOR_TYPES[self.type][2]
        self._attr_state_class = SENSOR_TYPES[self.type][3]
        self._attr_extra_state_attributes = {ATTR_ATTRIBUTION: CONF_ATTRIBUTION}

    @property
    def native_value(self) -> int | float | None:  # pyright: ignore[reportIncompatibleVariableOverride]
        """Return the latest sensor value from the coordinator."""
        data = self.coordinator.data
        if not data:
            return None
        return data.get(self.type)


# ----------------------------------------------------------------------
# Fetcher (rate-limited by scan_interval)
class Wfirex4Fetcher:
    def __init__(
        self,
        host,
        mac,
        temp_offset=0,
        humi_offset=0,
        scan_interval=60,
        entry=None,
        hass=None,
    ):
        self.data = {}
        self._host = host
        self._mac = mac
        self._port = PORT
        self._temp_offset = temp_offset
        self._humi_offset = humi_offset
        self._scan_interval = scan_interval
        self._last_fetch_time = 0
        self._lock = asyncio.Lock()
        self._entry = entry
        self.hass = hass

    def apply_config(
        self,
        *,
        host: str,
        temp_offset: float,
        humi_offset: float,
        scan_interval: int,
        entry,
        hass,
    ) -> None:
        """Apply updated config/option values to an existing fetcher instance."""
        self._host = host
        self._temp_offset = temp_offset
        self._humi_offset = humi_offset
        self._scan_interval = scan_interval
        self._entry = entry
        self.hass = hass

    async def _fetch_once(self, host: str) -> bytes:
        """Open a TCP connection, send a request, read the minimum response, then close."""
        reader = writer = None
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, self._port),
                timeout=CONNECT_TIMEOUT,
            )

            # Send a request frame.
            writer.write(b"\xaa\x00\x01\x18\x50")
            await writer.drain()

            # Read only what we need; the device may keep the connection open.
            data = b""
            while len(data) < MIN_LEN:
                chunk = await asyncio.wait_for(reader.read(1024), timeout=READ_TIMEOUT)
                if not chunk:
                    break
                data += chunk

            return data

        finally:
            if writer is not None:
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    pass

    async def get_sensor_data(self):
        async with self._lock:
            now = time.monotonic()
            if now - self._last_fetch_time < self._scan_interval:
                return self.data

            # Record the attempt time. Even on failure, wait scan_interval to avoid hammering the device.
            self._last_fetch_time = now

            host_to_connect = self._host
            last_err = None
            tried_resolve = False

            for attempt in range(1, MAX_ATTEMPTS + 1):
                try:
                    data = await self._fetch_once(host_to_connect)

                    if len(data) >= MIN_LEN and data[0:1] == b"\xaa":
                        humi = int.from_bytes(data[5:7], byteorder="big")
                        temp = int.from_bytes(data[7:9], byteorder="big")
                        illu = int.from_bytes(data[9:11], byteorder="big")
                        acti = int.from_bytes(data[11:12], byteorder="big")

                        self.data["temperature"] = temp / 10 + self._temp_offset
                        self.data["humidity"] = int(
                            round(humi / 10 + self._humi_offset)
                        )
                        self.data["light"] = illu
                        self.data["reliability"] = int(round(acti / 255.0 * 100.0))
                        return self.data

                    raise UpdateFailed(f"Invalid/short response (len={len(data)})")

                except asyncio.CancelledError:
                    # HA may cancel during shutdown or startup timeouts; do not swallow cancellation.
                    raise

                except Exception as err:
                    last_err = err

                    # On the first failure only, try resolving a new IP from the MAC (handles IP changes elsewhere).
                    if not tried_resolve:
                        tried_resolve = True
                        try:
                            resolved_ip = await resolve_ip_by_mac(self.hass, self._mac)
                        except Exception:
                            resolved_ip = None

                        if resolved_ip and resolved_ip != host_to_connect:
                            host_to_connect = resolved_ip
                            # If successful, persist the resolved IP back into the config entry.
                            if self._entry and self.hass:
                                try:
                                    await self._update_entry_host(resolved_ip)
                                except Exception:
                                    pass
                            self._host = resolved_ip
                            # Retry immediately (no backoff) after switching to a new IP.
                            continue

                    # Light exponential backoff (+jitter) before the next retry.
                    if attempt < MAX_ATTEMPTS:
                        delay = min(BACKOFF_BASE * (2 ** (attempt - 1)), BACKOFF_CAP)
                        delay += random.uniform(0, JITTER)
                        await asyncio.sleep(delay)

            # All attempts exhausted.
            raise UpdateFailed(
                f"Failed to fetch sensor data from {host_to_connect}:{self._port} "
                f"after {MAX_ATTEMPTS} attempts. Last error: {last_err}"
            )

    async def _update_entry_host(self, new_host: str):
        """Update the stored host (IP address) in the ConfigEntry."""
        if self._entry.data.get("host") != new_host:
            self.hass.config_entries.async_update_entry(
                self._entry, data={**self._entry.data, "host": new_host}
            )
