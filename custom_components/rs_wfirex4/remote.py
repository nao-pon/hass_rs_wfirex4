"""RS-WFIREX4 Remote platform that has a remotes."""

import asyncio
import logging
import re
from base64 import b64decode
from collections import defaultdict
from itertools import product
from typing import Any

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.persistent_notification import async_create, async_dismiss
from homeassistant.components.remote import (
    ATTR_ALTERNATIVE,
    ATTR_DELAY_SECS,
    ATTR_DEVICE,
    ATTR_NUM_REPEATS,
    DEFAULT_DELAY_SECS,
    RemoteEntity,
    RemoteEntityFeature,
)
from homeassistant.const import ATTR_COMMAND, CONF_HOST, CONF_MAC, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.storage import Store

from .const import DEFAULT_NAME, DOMAIN, PORT
from .helpers import build_default_name_with_mac, build_device_info

CODE_STORAGE_VERSION = 1
FLAG_STORAGE_VERSION = 1
FLAG_SAVE_DELAY = 15

COMMAND_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_COMMAND): vol.All(
            cv.ensure_list, [vol.All(cv.string, vol.Length(min=1))], vol.Length(min=1)
        ),
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_SEND_SCHEMA = COMMAND_SCHEMA.extend(
    {
        vol.Optional(ATTR_DEVICE): vol.All(cv.string, vol.Length(min=1)),
        vol.Optional(ATTR_DELAY_SECS, default=DEFAULT_DELAY_SECS): vol.Coerce(float),
    }
)

SERVICE_LEARN_SCHEMA = COMMAND_SCHEMA.extend(
    {
        vol.Required(ATTR_DEVICE): vol.All(cv.string, vol.Length(min=1)),
        vol.Optional(ATTR_ALTERNATIVE, default=False): cv.boolean,
    }
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    """Set up remote from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]

    host = data.get(CONF_HOST)
    mac = format_mac(data.get(CONF_MAC))
    name = data.get(CONF_NAME, build_default_name_with_mac(mac))

    remote_entity = Wfirex4Remote(
        host,
        mac,
        name,
        Store(hass, CODE_STORAGE_VERSION, "rs_wfirex4_codes"),
        Store(hass, FLAG_STORAGE_VERSION, f"rs_wfirex4_{mac.replace(':', '')}_flags"),
    )
    async_add_entities([remote_entity], update_before_add=False)
    hass.async_create_task(remote_entity.async_load_storage_files())


class Wfirex4Remote(RemoteEntity):
    """Representation of a RS-WFIREX4 remote."""

    def __init__(self, host: str, mac: str, name: str, code, flag):
        """Initialize the RS-WFIREX4 Remote."""
        self._name = name or DEFAULT_NAME
        self._host = host
        self._port = PORT
        self._code_storege: Store[Any] = code
        self._flag_storage: Store[Any] = flag
        self._codes = {}
        self._flags = defaultdict(int)
        self._attr_is_on = True
        self._codeRegx = re.compile(r"^[0-9a-f]{32,}$")

        self._attr_name = "{} {}".format(self._name, "Remote")
        self._attr_unique_id = "wfirex4_{}_remote".format(mac)
        self._attr_icon = "mdi:remote"
        self._attr_should_poll = False
        self._attr_supported_features = RemoteEntityFeature.LEARN_COMMAND
        self._attr_extra_state_attributes = {}

        self._attr_device_info = build_device_info(mac, name)

    def turn_on(self, **kwargs):
        """Turn the remote on."""
        self._attr_is_on = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the remote off."""
        self._attr_is_on = False
        self.schedule_update_ha_state()

    def get_code(self, command, device):
        """Get Hex code"""

        def data_packet(value):
            """Decode a data packet given for a Broadlink remote."""
            value = cv.string(value)
            extra = len(value) % 4
            if extra > 0:
                value = value + ("=" * (4 - extra))
            return b64decode(value)

        if command.startswith("b64:"):
            try:
                code, is_toggle_cmd = data_packet(command[4:]).hex(), False
            except ValueError as err:
                raise ValueError("Invalid code") from err

        elif self._codeRegx.match(command):
            code, is_toggle_cmd = command, False

        else:
            if device is None:
                raise KeyError("You need to specify a device")

            try:
                code = self._codes[device][command]
            except KeyError as err:
                raise KeyError("Command not found") from err

            # For toggle commands, alternate between codes in a list.
            if isinstance(code, list):
                code = code[self._flags[device]]
                is_toggle_cmd = True
            else:
                is_toggle_cmd = False

        return code, is_toggle_cmd

    @callback
    def get_flags(self):
        """Return a dictionary of toggle flags.

        A toggle flag indicates whether the remote should send an
        alternative code.
        """
        return self._flags

    async def async_load_storage_files(self):
        """Load codes and toggle flags from storage files."""
        try:
            self._codes.update(await self._code_storege.async_load() or {})
        except HomeAssistantError:
            _LOGGER.error(
                "Failed to create '%s Remote' entity: Storage error",
                "{} {}".format(self._name, "Remote"),
            )
            # self._code_storege = None

    async def async_send_command(self, command, **kwargs):
        """Send a list of commands to a device."""
        kwargs[ATTR_COMMAND] = command
        kwargs = SERVICE_SEND_SCHEMA(kwargs)
        commands = kwargs[ATTR_COMMAND]
        device = kwargs.get(ATTR_DEVICE)
        repeat = kwargs[ATTR_NUM_REPEATS]
        delay = kwargs[ATTR_DELAY_SECS]

        last_code = ""

        if not self._attr_is_on:
            _LOGGER.warning(
                "remote.send_command canceled: %s entity is turned off", self.entity_id
            )
            return

        should_delay = False

        for _, cmd in product(range(repeat), commands):
            if should_delay:
                await asyncio.sleep(delay)

            try:
                code, is_toggle_cmd = self.get_code(cmd, device)

            except (KeyError, ValueError) as err:
                _LOGGER.error("Failed to send '%s' to %s: %s", cmd, device, err)
                should_delay = False
                continue

            try:
                await self.set_wfirex(code)
                last_code = code

            except Exception:
                # @todo
                continue

            should_delay = True
            if is_toggle_cmd:
                self._flags[device] ^= 1

        self._flag_storage.async_delay_save(self.get_flags, FLAG_SAVE_DELAY)

        if last_code:
            self._attr_extra_state_attributes["last_command_sent"] = last_code
            self.schedule_update_ha_state()

    async def async_learn_command(self, **kwargs):
        """Learn a command to a device."""
        if await self.learn_wfirex(**kwargs):
            self.schedule_update_ha_state()

    async def set_wfirex(self, wave_data_str):
        self._attr_extra_state_attributes["last_command_result"] = "Pending..."

        wave_data = bytes.fromhex(wave_data_str)
        wave_data_len = len(wave_data)
        wave_data_len_hex = wave_data_len.to_bytes(2, "big")

        payload = b"\x11\x00" + wave_data_len_hex + wave_data
        crc = self.crc8_calc(payload).to_bytes(1, "big")
        payload_len = len(payload).to_bytes(2, "big")
        header = b"\xaa" + payload_len
        send_data = header + payload + crc

        reader, writer = await asyncio.open_connection(self._host, self._port)
        writer.write(send_data)
        await writer.drain()
        data = await reader.read(1024)
        writer.close()
        await writer.wait_closed()

        if data:
            self._attr_extra_state_attributes["last_command_result"] = data.hex()

    async def learn_wfirex(self, **kwargs):
        """Learn a list of commands from a remote."""
        kwargs = SERVICE_LEARN_SCHEMA(kwargs)
        commands = kwargs[ATTR_COMMAND]
        device = kwargs[ATTR_DEVICE]
        toggle = kwargs[ATTR_ALTERNATIVE]

        async def learn_command(command):
            reader, writer = await asyncio.open_connection(self._host, self._port)
            writer.write(b"\xaa\x00\x01\x12\x6c")
            await writer.drain()

            notify_id = f"{DOMAIN}_learn_command"
            async_create(
                self.hass,
                f"Press the '{command}' button.",
                title="Learn command",
                notification_id=notify_id,
            )

            data = b""
            while True:
                msg = await reader.read(1024)
                if len(msg) <= 0:
                    break
                data += msg
            writer.close()
            await writer.wait_closed()

            async_dismiss(self.hass, notification_id=notify_id)

            if data and data[0:1] == b"\xaa":
                code = data.hex()[16:]
                self._attr_extra_state_attributes["last_learn"] = code
                return code
            else:
                raise Exception("Did not get the correct response.")

        if not self._attr_is_on:
            _LOGGER.warning(
                "remote.learn_command canceled: %s entity is turned off", self.entity_id
            )
            return False

        should_store = False

        for command in commands:
            try:
                code = await learn_command(command)
                if toggle:
                    code = [code, await learn_command(command)]

                self._codes.setdefault(device, {}).update({command: code})
                should_store = True
            except Exception as err:
                _LOGGER.error("Failed to learn '%s': %s", command, err)
                continue

        if self._code_storege and should_store:
            await self._code_storege.async_save(self._codes)

        return True

    def crc8_calc(self, payload_buf):
        CRC8Table = [
            0x00,
            0x85,
            0x8F,
            0x0A,
            0x9B,
            0x1E,
            0x14,
            0x91,
            0xB3,
            0x36,
            0x3C,
            0xB9,
            0x28,
            0xAD,
            0xA7,
            0x22,
            0xE3,
            0x66,
            0x6C,
            0xE9,
            0x78,
            0xFD,
            0xF7,
            0x72,
            0x50,
            0xD5,
            0xDF,
            0x5A,
            0xCB,
            0x4E,
            0x44,
            0xC1,
            0x43,
            0xC6,
            0xCC,
            0x49,
            0xD8,
            0x5D,
            0x57,
            0xD2,
            0xF0,
            0x75,
            0x7F,
            0xFA,
            0x6B,
            0xEE,
            0xE4,
            0x61,
            0xA0,
            0x25,
            0x2F,
            0xAA,
            0x3B,
            0xBE,
            0xB4,
            0x31,
            0x13,
            0x96,
            0x9C,
            0x19,
            0x88,
            0x0D,
            0x07,
            0x82,
            0x86,
            0x03,
            0x09,
            0x8C,
            0x1D,
            0x98,
            0x92,
            0x17,
            0x35,
            0xB0,
            0xBA,
            0x3F,
            0xAE,
            0x2B,
            0x21,
            0xA4,
            0x65,
            0xE0,
            0xEA,
            0x6F,
            0xFE,
            0x7B,
            0x71,
            0xF4,
            0xD6,
            0x53,
            0x59,
            0xDC,
            0x4D,
            0xC8,
            0xC2,
            0x47,
            0xC5,
            0x40,
            0x4A,
            0xCF,
            0x5E,
            0xDB,
            0xD1,
            0x54,
            0x76,
            0xF3,
            0xF9,
            0x7C,
            0xED,
            0x68,
            0x62,
            0xE7,
            0x26,
            0xA3,
            0xA9,
            0x2C,
            0xBD,
            0x38,
            0x32,
            0xB7,
            0x95,
            0x10,
            0x1A,
            0x9F,
            0x0E,
            0x8B,
            0x81,
            0x04,
            0x89,
            0x0C,
            0x06,
            0x83,
            0x12,
            0x97,
            0x9D,
            0x18,
            0x3A,
            0xBF,
            0xB5,
            0x30,
            0xA1,
            0x24,
            0x2E,
            0xAB,
            0x6A,
            0xEF,
            0xE5,
            0x60,
            0xF1,
            0x74,
            0x7E,
            0xFB,
            0xD9,
            0x5C,
            0x56,
            0xD3,
            0x42,
            0xC7,
            0xCD,
            0x48,
            0xCA,
            0x4F,
            0x45,
            0xC0,
            0x51,
            0xD4,
            0xDE,
            0x5B,
            0x79,
            0xFC,
            0xF6,
            0x73,
            0xE2,
            0x67,
            0x6D,
            0xE8,
            0x29,
            0xAC,
            0xA6,
            0x23,
            0xB2,
            0x37,
            0x3D,
            0xB8,
            0x9A,
            0x1F,
            0x15,
            0x90,
            0x01,
            0x84,
            0x8E,
            0x0B,
            0x0F,
            0x8A,
            0x80,
            0x05,
            0x94,
            0x11,
            0x1B,
            0x9E,
            0xBC,
            0x39,
            0x33,
            0xB6,
            0x27,
            0xA2,
            0xA8,
            0x2D,
            0xEC,
            0x69,
            0x63,
            0xE6,
            0x77,
            0xF2,
            0xF8,
            0x7D,
            0x5F,
            0xDA,
            0xD0,
            0x55,
            0xC4,
            0x41,
            0x4B,
            0xCE,
            0x4C,
            0xC9,
            0xC3,
            0x46,
            0xD7,
            0x52,
            0x58,
            0xDD,
            0xFF,
            0x7A,
            0x70,
            0xF5,
            0x64,
            0xE1,
            0xEB,
            0x6E,
            0xAF,
            0x2A,
            0x20,
            0xA5,
            0x34,
            0xB1,
            0xBB,
            0x3E,
            0x1C,
            0x99,
            0x93,
            0x16,
            0x87,
            0x02,
            0x08,
            0x8D,
        ]
        payload_length = len(payload_buf)
        crc = 0
        for i in range(payload_length):
            crc = CRC8Table[(crc ^ payload_buf[i]) % 256]
        return crc
