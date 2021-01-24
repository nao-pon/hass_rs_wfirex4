"""RS-WFIREX4 Remote platform that has a remotes."""
import socket
import asyncio
import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from homeassistant.const import CONF_HOST, CONF_NAME

from homeassistant.components.remote import (
    PLATFORM_SCHEMA,
    SUPPORT_LEARN_COMMAND,
    RemoteEntity,
)

import logging

DEFAULT_NAME = 'RS-WFIREX4'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Demo config entry."""
    setup_platform(hass, {}, async_add_entities)


def setup_platform(hass, config, add_entities_callback, discovery_info=None):
    """Set up the demo remotes."""
    host = config.get(CONF_HOST)
    name = config.get(CONF_NAME)
    port = 60001

    add_entities_callback(
        [
            Wfirex4Remote(name, True, "mdi:remote", host),
        ]
    )


class Wfirex4Remote(RemoteEntity):
    """Representation of a demo remote."""

    def __init__(self, name, state, icon, host):
        """Initialize the Demo Remote."""
        self._name = name or DEFAULT_NAME
        self._state = state
        self._icon = icon
        self._last_command_sent = None
        self._last_command_result = None
        self._last_learn = None
        self._host = host
        self._port = 60001
        self._uid = host.split('.')[3]

    @property
    def should_poll(self):
        """No polling needed for a demo remote."""
        return False

    @property
    def name(self):
        """Return the name of the device if any."""
        return "{} {}".format(self._name, 'Remote')

    @property
    def unique_id(self):
        return 'wfirex4_{}_remote'.format(self._uid)

    @property
    def icon(self):
        """Return the icon to use for device if any."""
        return self._icon

    @property
    def is_on(self):
        """Return true if remote is on."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return device state attributes."""
        attr = {}
        if self._last_command_sent is not None:
            attr["last_command_sent"] = self._last_command_sent

        if self._last_command_result is not None:
            attr["last_command_result"] = self._last_command_result

        if self._last_learn is not None:
            attr["last_learn"] = self._last_learn

        return attr

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_LEARN_COMMAND

    def turn_on(self, **kwargs):
        """Turn the remote on."""
        self._state = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the remote off."""
        self._state = False
        self.schedule_update_ha_state()

    #def send_command(self, command, **kwargs):
    async def async_send_command(self, command, **kwargs):
        """Send a command to a device."""
        for com in command:
            self._last_command_sent = com
            await self.set_wfirex(com)
        self.schedule_update_ha_state()

    async def async_learn_command(self, **kwargs):
        """Learn a command to a device."""
        await self.learn_wfirex()
        self.schedule_update_ha_state()

    async def set_wfirex(self, wave_data_str):

        self._last_command_result = 'Pending...'

        wave_data = bytes.fromhex(wave_data_str)
        wave_data_len = len(wave_data)
        wave_data_len_hex = wave_data_len.to_bytes(2, 'big')

        payload = b'\x11\x00' + wave_data_len_hex + wave_data
        crc = self.crc8_calc(payload).to_bytes(1, 'big')
        payload_len = len(payload).to_bytes(2, 'big')
        header = b'\xAA' + payload_len
        send_data = header + payload + crc

        reader, writer = await asyncio.open_connection(self._host, self._port)
        writer.write(send_data)
        data = await reader.read(1024)
        writer.close()
        #with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        #    s.connect((self._host, self._port))
        #    s.sendall(send_data)
        #    data = s.recv(1024)
        #    s.close()

        if data:
            self._last_command_result = data.hex()

    async def learn_wfirex(self):
        #with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        #    s.connect((self._host, self._port))
        #    s.settimeout(30)
        #    s.sendall(b'\xaa\x00\x01\x12\x6c')
        #    data = b''
        #    while True:
        #        msg = s.recv(1024)
        #        if len(msg) <= 0:
        #            break
        #        data += msg
        #    s.close()
        reader, writer = await asyncio.open_connection(self._host, self._port)
        writer.write(b'\xaa\x00\x01\x12\x6c')
        data = b''
        while True:
            msg = await reader.read(1024)
            if len(msg) <= 0:
                break
            data += msg
        writer.close()

        self._last_learn = data.hex()[16:]

    def crc8_calc(self, payload_buf): 
        CRC8Table = [
        0x00, 0x85, 0x8F, 0x0A, 0x9B, 0x1E, 0x14, 0x91,
        0xB3, 0x36, 0x3C, 0xB9, 0x28, 0xAD, 0xA7, 0x22,
        0xE3, 0x66, 0x6C, 0xE9, 0x78, 0xFD, 0xF7, 0x72,
        0x50, 0xD5, 0xDF, 0x5A, 0xCB, 0x4E, 0x44, 0xC1,
        0x43, 0xC6, 0xCC, 0x49, 0xD8, 0x5D, 0x57, 0xD2,
        0xF0, 0x75, 0x7F, 0xFA, 0x6B, 0xEE, 0xE4, 0x61,
        0xA0, 0x25, 0x2F, 0xAA, 0x3B, 0xBE, 0xB4, 0x31,
        0x13, 0x96, 0x9C, 0x19, 0x88, 0x0D, 0x07, 0x82,

        0x86, 0x03, 0x09, 0x8C, 0x1D, 0x98, 0x92, 0x17,
        0x35, 0xB0, 0xBA, 0x3F, 0xAE, 0x2B, 0x21, 0xA4,
        0x65, 0xE0, 0xEA, 0x6F, 0xFE, 0x7B, 0x71, 0xF4,
        0xD6, 0x53, 0x59, 0xDC, 0x4D, 0xC8, 0xC2, 0x47,
        0xC5, 0x40, 0x4A, 0xCF, 0x5E, 0xDB, 0xD1, 0x54,
        0x76, 0xF3, 0xF9, 0x7C, 0xED, 0x68, 0x62, 0xE7,
        0x26, 0xA3, 0xA9, 0x2C, 0xBD, 0x38, 0x32, 0xB7,
        0x95, 0x10, 0x1A, 0x9F, 0x0E, 0x8B, 0x81, 0x04,

        0x89, 0x0C, 0x06, 0x83, 0x12, 0x97, 0x9D, 0x18,
        0x3A, 0xBF, 0xB5, 0x30, 0xA1, 0x24, 0x2E, 0xAB,
        0x6A, 0xEF, 0xE5, 0x60, 0xF1, 0x74, 0x7E, 0xFB,
        0xD9, 0x5C, 0x56, 0xD3, 0x42, 0xC7, 0xCD, 0x48,
        0xCA, 0x4F, 0x45, 0xC0, 0x51, 0xD4, 0xDE, 0x5B,
        0x79, 0xFC, 0xF6, 0x73, 0xE2, 0x67, 0x6D, 0xE8,
        0x29, 0xAC, 0xA6, 0x23, 0xB2, 0x37, 0x3D, 0xB8,
        0x9A, 0x1F, 0x15, 0x90, 0x01, 0x84, 0x8E, 0x0B,

        0x0F, 0x8A, 0x80, 0x05, 0x94, 0x11, 0x1B, 0x9E,
        0xBC, 0x39, 0x33, 0xB6, 0x27, 0xA2, 0xA8, 0x2D,
        0xEC, 0x69, 0x63, 0xE6, 0x77, 0xF2, 0xF8, 0x7D,
        0x5F, 0xDA, 0xD0, 0x55, 0xC4, 0x41, 0x4B, 0xCE,
        0x4C, 0xC9, 0xC3, 0x46, 0xD7, 0x52, 0x58, 0xDD,
        0xFF, 0x7A, 0x70, 0xF5, 0x64, 0xE1, 0xEB, 0x6E,
        0xAF, 0x2A, 0x20, 0xA5, 0x34, 0xB1, 0xBB, 0x3E,
        0x1C, 0x99, 0x93, 0x16, 0x87, 0x02, 0x08, 0x8D
        ]
        payload_length = len(payload_buf)
        crc = 0
        for i in range(payload_length):
            crc = CRC8Table[(crc ^ payload_buf[i]) % 256]
        return crc
