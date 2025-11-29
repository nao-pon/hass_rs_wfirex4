from __future__ import annotations

import asyncio
import logging
import time
from datetime import timedelta

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
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

# Sensor type list
SENSOR_TYPES = {
    "temperature": (
        "Temperature",
        UnitOfTemperature.CELSIUS,
        SensorDeviceClass.TEMPERATURE,
    ),
    "humidity": ("Humidity", PERCENTAGE, SensorDeviceClass.HUMIDITY),
    "light": ("Light", LIGHT_LUX, SensorDeviceClass.ILLUMINANCE),
    "reliability": ("Reliability", PERCENTAGE, SensorDeviceClass.POWER_FACTOR),
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

    # Create fetcher
    scan_interval = opts.get("scan_interval", 60)  # デフォルト60秒
    fetcher = hass.data[DOMAIN]["fetchers"].get(mac)
    if not fetcher:
        fetcher = hass.data[DOMAIN]["fetchers"][mac] = Wfirex4Fetcher(
            host,
            mac,
            temp_offset,
            humi_offset,
            scan_interval,
            entry,
            hass,
        )

    coordinator = hass.data[DOMAIN]["coordinators"].get(mac)
    if not coordinator:
        coordinator = hass.data[DOMAIN]["coordinators"][mac] = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name=name,
            update_interval=timedelta(seconds=scan_interval),  # Coordinator更新間隔
            update_method=fetcher.get_sensor_data,
        )

    await coordinator.async_config_entry_first_refresh()

    # Create entities (replace with actual entities from project)
    entities = []
    for sensor_type in SENSOR_TYPES.keys():
        entities.append(WfirexCoordinatorSensor(coordinator, mac, name, sensor_type))
    async_add_entities(entities, update_before_add=True)


async def async_update_entry_host(hass, entry, new_host: str):
    """ConfigEntry 内の host(IP) を更新"""
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
        self._attr_extra_state_attributes = {ATTR_ATTRIBUTION: CONF_ATTRIBUTION}

    @property
    def native_value(self) -> int | float | None:  # pyright: ignore[reportIncompatibleVariableOverride]
        """Return the latest sensor value from the coordinator."""
        data = self.coordinator.data
        if not data:
            return None
        return data.get(self.type)


# ----------------------------------------------------------------------
# Fetcher with 60-second throttle
# Fetcher
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

    async def get_sensor_data(self):
        async with self._lock:
            now = time.monotonic()
            if now - self._last_fetch_time < self._scan_interval:
                return self.data

            self._last_fetch_time = now
            host_to_connect = self._host

            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(host_to_connect, self._port), timeout=10
                )
            except Exception:
                # HA 内部デバイスレジストリから IP 再取得
                resolved_ip = await resolve_ip_by_mac(self.hass, self._mac)
                if resolved_ip:
                    host_to_connect = resolved_ip
                    try:
                        reader, writer = await asyncio.wait_for(
                            asyncio.open_connection(host_to_connect, self._port),
                            timeout=10,
                        )
                        # 成功したら config entry も更新
                        if self._entry and self.hass:
                            await self._update_entry_host(resolved_ip)
                        self._host = resolved_ip
                    except Exception as err2:
                        raise UpdateFailed(
                            f"Failed to fetch sensor data after resolving IP: {err2}"
                        )
                else:
                    raise UpdateFailed(
                        f"Cannot resolve IP for MAC {self._mac}, device not known in HA"
                    )

            # デバイスからデータ取得
            writer.write(b"\xaa\x00\x01\x18\x50")
            await writer.drain()

            data = b""
            while True:
                msg = await reader.read(1024)
                if not msg:
                    break
                data += msg

            writer.close()
            await writer.wait_closed()

            if data and data[0:1] == b"\xaa":
                humi = int.from_bytes(data[5:7], byteorder="big")
                temp = int.from_bytes(data[7:9], byteorder="big")
                illu = int.from_bytes(data[9:11], byteorder="big")
                acti = int.from_bytes(data[11:12], byteorder="big")

                self.data["temperature"] = temp / 10 + self._temp_offset
                self.data["humidity"] = int(round(humi / 10 + self._humi_offset))
                self.data["light"] = illu
                self.data["reliability"] = int(round(acti / 255.0 * 100.0))
                return self.data
            else:
                _LOGGER.warning("Sensor fetch error.")
                return None

    async def _update_entry_host(self, new_host: str):
        """ConfigEntry 内の host(IP) を更新"""
        if self._entry.data.get("host") != new_host:
            self.hass.config_entries.async_update_entry(
                self._entry, data={**self._entry.data, "host": new_host}
            )
