"""Config flow for rs_wfirex4 integration."""

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
)
from homeassistant.core import callback
from homeassistant.helpers.device_registry import format_mac

from .const import (
    CONF_HUMI_OFFSET,
    CONF_TEMP_OFFSET,
    DEFAULT_HUMI_OFFSET,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TEMP_OFFSET,
    DOMAIN,
)
from .helpers import build_default_name_with_mac, test_connection


class WFireX4ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for WFireX4."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step when a user adds the integration manually."""
        discovery = self.context.get("discovery_info", {})
        if user_input is not None:
            mac = format_mac(user_input[CONF_MAC])
            user_input[CONF_MAC] = mac

            await self.async_set_unique_id(mac.replace(":", ""))
            self._abort_if_unique_id_configured()

            title = user_input.get(CONF_NAME, build_default_name_with_mac(mac))
            return self.async_create_entry(title=title, data=user_input)

        mac = discovery.get(CONF_MAC, "")
        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=discovery.get(CONF_HOST, "")): str,
                vol.Required(CONF_MAC, default=mac): str,
                vol.Required(
                    CONF_NAME,
                    default=discovery.get(CONF_NAME, build_default_name_with_mac(mac)),
                ): str,
                vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
                vol.Optional(CONF_TEMP_OFFSET, default=DEFAULT_TEMP_OFFSET): vol.Coerce(
                    float
                ),
                vol.Optional(CONF_HUMI_OFFSET, default=DEFAULT_HUMI_OFFSET): vol.Coerce(
                    float
                ),
            }
        )

        return self.async_show_form(step_id="user", data_schema=data_schema)

    async def async_step_import(self, user_input):
        """Import from configuration.yaml (SOURCE_IMPORT)."""
        mac = format_mac(user_input.get(CONF_MAC, ""))
        user_input[CONF_MAC] = mac

        await self.async_set_unique_id(mac.replace(":", ""))
        self._abort_if_unique_id_configured()

        title = user_input.get(CONF_NAME, build_default_name_with_mac(mac))
        options = {
            CONF_SCAN_INTERVAL: user_input.get(
                CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
            ),
            CONF_TEMP_OFFSET: user_input.get(CONF_TEMP_OFFSET, DEFAULT_TEMP_OFFSET),
            CONF_HUMI_OFFSET: user_input.get(CONF_HUMI_OFFSET, DEFAULT_HUMI_OFFSET),
        }
        return self.async_create_entry(title=title, data=user_input, options=options)

    async def async_step_dhcp(self, discovery_info):
        """Handle DHCP discovery — start config flow when MAC prefix matches."""
        host = discovery_info.ip
        mac = discovery_info.macaddress

        # Optional: avoid false positives by testing connection
        try:
            await test_connection(self.hass, host, mac)
        except Exception:
            # Do not start config flow if device is unreachable
            return self.async_abort(reason="cannot_connect")

        await self.async_set_unique_id(format_mac(mac).replace(":", ""))
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        self.context["discovery_info"] = {
            CONF_HOST: host,
            CONF_MAC: mac,
            CONF_NAME: build_default_name_with_mac(mac),
        }

        return await self.async_step_user()

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return WFireX4OptionsFlow()


class WFireX4OptionsFlow(config_entries.OptionsFlow):
    """Options flow to edit scan_interval and offsets."""

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            # Save options
            return self.async_create_entry(title="", data=user_input)

        data = self.config_entry.data
        options = self.config_entry.options

        scan_interval = options.get(
            CONF_SCAN_INTERVAL, data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )
        temp_offset = options.get(
            CONF_TEMP_OFFSET, data.get(CONF_TEMP_OFFSET, DEFAULT_TEMP_OFFSET)
        )
        humi_offset = options.get(
            CONF_HUMI_OFFSET, data.get(CONF_HUMI_OFFSET, DEFAULT_HUMI_OFFSET)
        )

        schema = vol.Schema(
            {
                vol.Optional(CONF_SCAN_INTERVAL, default=scan_interval): int,
                vol.Optional(CONF_TEMP_OFFSET, default=temp_offset): vol.Coerce(float),
                vol.Optional(CONF_HUMI_OFFSET, default=humi_offset): vol.Coerce(float),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
