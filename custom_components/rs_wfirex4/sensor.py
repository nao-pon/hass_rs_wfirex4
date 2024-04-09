"""
Hass.io RS-WFIREX4 Sensors

Special thanks to https://github.com/NeoSloth/wfirex4
 and https://www.gcd.org/blog/2020/09/1357/
"""

import asyncio
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_HOST,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    PERCENTAGE,
    LIGHT_LUX,
    UnitOfTemperature,
)

from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_call_later

import logging
import async_timeout
import random

# ------------------------------------------------------------------------------
# Config
from . import CONF_TEMP_OFFSET, CONF_HUMI_OFFSET

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


# ------------------------------------------------------------------------------
# Setup Entities
async def async_setup_platform(hass, configs, async_add_entities, config=None):
    """Representation of a RS-WFIREX4 sensors."""
    if config == None:
        return

    host = config.get(CONF_HOST)
    name = config.get(CONF_NAME)
    uid = config.get("uid")

    if host == None or name == None or uid == None:
        return

    entities = []
    for sensor_type in SENSOR_TYPES.keys():
        entities.append(Wfirex4SensorEntity(name, sensor_type, uid))

    async_add_entities(entities)

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # Class of Data fetcher
    fetcher = Wfirex4Fetcher(hass, host, entities, config)

    # Call first task and start loop
    hass.async_create_task(fetcher.fetching_data())


# ------------------------------------------------------------------------------
# Define Entity
class Wfirex4SensorEntity(Entity):
    def __init__(self, name, sensor_type, uid):
        self.client_name = name
        self.type = sensor_type
        self._uid = uid

        self._attr_state = None
        self._attr_name = "{} {}".format(self.client_name, SENSOR_TYPES[self.type][0])
        self._attr_unique_id = "wfirex4_{}_{}".format(self._uid, self.type)
        self._attr_should_poll = False
        self._attr_device_class = SENSOR_TYPES[self.type][2]
        self._attr_extra_state_attributes = {ATTR_ATTRIBUTION: CONF_ATTRIBUTION}
        self._attr_unit_of_measurement = SENSOR_TYPES[self.type][1]

    # @property
    # def name(self):
    #     return "{} {}".format(self.client_name, SENSOR_TYPES[self.type][0])

    # @property
    # def unique_id(self):
    #     return "wfirex4_{}_{}".format(self._uid, self.type)

    # @property
    # def state(self):
    #     return self._state

    # @property
    # def should_poll(self):
    #     return False

    # @property
    # def device_class(self):
    #     return SENSOR_TYPES[self.type][2]

    # @property
    # def extra_state_attributes(self):
    #     return {
    #         ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
    #     }

    # @property
    # def unit_of_measurement(self):
    #     return SENSOR_TYPES[self.type][1]


# ------------------------------------------------------------------------------
# Fetcher Class
class Wfirex4Fetcher:
    def __init__(self, hass, host, entities, config):
        self.data = {}
        self.hass = hass
        self.entities = entities
        self._host = host
        self._port = 60001
        self._interval = config.get(CONF_SCAN_INTERVAL)
        self._temp_offset = config.get(CONF_TEMP_OFFSET)
        self._humi_offset = config.get(CONF_HUMI_OFFSET)

    # Data fetch, update and loop
    async def fetching_data(self, *_):
        def try_again(err: str):
            # Retry
            secs = random.randint(30, 60)
            _LOGGER.error("Retrying in %i seconds: %s", secs, err)
            async_call_later(self.hass, secs, self.fetching_data)

        try:
            with async_timeout.timeout(15):
                await self.get_sensor_data()

        except (asyncio.TimeoutError, Exception) as err:
            # Error then retry
            try_again(err)

        else:
            # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
            # call updating_devices()
            await self.updating_devices()

            # make loop with fetch interval
            async_call_later(self.hass, self._interval, self.fetching_data)

    # Do update sensors data
    async def updating_devices(self, *_):
        # Do nothing if empty
        if not self.data:
            return

        for checkEntity in self.entities:
            newState = None

            if checkEntity.type in self.data.keys():
                newState = self.data[checkEntity.type]

            # Chenged data
            if newState != checkEntity._attr_state:
                checkEntity._attr_state = newState
                checkEntity.async_schedule_update_ha_state()

    # Get sensors data
    async def get_sensor_data(self, *_):
        import math

        con = asyncio.open_connection(self._host, self._port)
        try:
            reader, writer = await asyncio.wait_for(con, timeout=10)
            writer.write(b"\xAA\x00\x01\x18\x50")
            await writer.drain()
            data = b""
            while True:
                msg = await reader.read(1024)
                if len(msg) <= 0:
                    break
                data += msg
            writer.close()
            await writer.wait_closed()

        except:
            raise

        else:
            if data and data[0:1] == b"\xAA":
                humi = int.from_bytes(data[5:7], byteorder="big")
                temp = int.from_bytes(data[7:9], byteorder="big")
                illu = int.from_bytes(data[9:11], byteorder="big")
                acti = int.from_bytes(data[11:12], byteorder="big")

                self.data["temperature"] = round(temp) / 10 + self._temp_offset
                self.data["humidity"] = int(round(humi / 10 + self._humi_offset))
                self.data["light"] = illu
                self.data["reliability"] = int(round(acti / 255.0 * 100.0))
            else:
                raise Exception("Sensor fetch error.")
