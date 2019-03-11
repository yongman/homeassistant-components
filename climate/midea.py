"""
Midea空调 BY 菲佣 1.0
"""
from datetime import timedelta
from base64 import b64encode, b64decode
import asyncio
import binascii
import logging
import socket

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.components.climate import (
    ATTR_TARGET_TEMP_HIGH, ATTR_TARGET_TEMP_LOW, DOMAIN,
    ClimateDevice, PLATFORM_SCHEMA, STATE_AUTO,
    STATE_COOL, STATE_HEAT, SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_TARGET_TEMPERATURE_HIGH, SUPPORT_TARGET_TEMPERATURE_LOW,
    SUPPORT_OPERATION_MODE)
from homeassistant.const import (
    TEMP_CELSIUS, TEMP_FAHRENHEIT, ATTR_TEMPERATURE, ATTR_UNIT_OF_MEASUREMENT,
    CONF_NAME, CONF_HOST, CONF_MAC, CONF_TIMEOUT)
from homeassistant.helpers import condition
from homeassistant.helpers.event import (
    async_track_state_change, async_track_time_interval)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['sensor']

DEFAULT_TOLERANCE = 0.3
DEFAULT_NAME = 'Midea Thermostat'

DEFAULT_TIMEOUT = 10
DEFAULT_RETRY = 3

DEFAULT_MIN_TMEP = 17
DEFAULT_MAX_TMEP = 30
DEFAULT_STEP = 1

CONF_SENSOR = 'target_sensor'
CONF_TARGET_TEMP = 'target_temp'
devtype = 0x2712

SUPPORT_FLAGS = (SUPPORT_TARGET_TEMPERATURE | SUPPORT_OPERATION_MODE)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_MAC): cv.string,
    vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
    vol.Required(CONF_SENSOR): cv.entity_id,
    vol.Optional(CONF_TARGET_TEMP): vol.Coerce(float)
})

@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the generic thermostat platform."""
    import broadlink
    ip_addr = config.get(CONF_HOST)
    mac_addr = binascii.unhexlify(
        config.get(CONF_MAC).encode().replace(b':', b''))

    name = config.get(CONF_NAME)
    sensor_entity_id = config.get(CONF_SENSOR)
    target_temp = config.get(CONF_TARGET_TEMP)

    broadlink_device = broadlink.rm((ip_addr, 80), mac_addr, devtype)
    broadlink_device.timeout = config.get(CONF_TIMEOUT)
    try:
        broadlink_device.auth()
    except socket.timeout:
        _LOGGER.error("Failed to connect to device")

    async_add_devices([DemoClimate(
            hass, name, target_temp, None, None, None, None, None,
            None, 'off', None, DEFAULT_MAX_TMEP, DEFAULT_MIN_TMEP, 
            broadlink_device, sensor_entity_id)])


class DemoClimate(ClimateDevice):
    """Representation of a demo climate device."""

    def __init__(self, hass, name, target_temperature, target_humidity,
                away, hold, current_fan_mode, current_humidity,
                current_swing_mode, current_operation, aux,
                target_temp_high, target_temp_low,
                broadlink_device, sensor_entity_id):
                 
        """Initialize the climate device."""
        self.hass = hass
        self._name = name if name else DEFAULT_NAME
        self._target_temperature = target_temperature
        self._target_humidity = target_humidity
        self._away = away
        self._hold = hold
        self._current_humidity = current_humidity
        self._current_fan_mode = current_fan_mode
        self._current_operation = current_operation
        self._aux = aux
        self._current_swing_mode = current_swing_mode
        self._fan_list = ['On Low', 'On High', 'Auto Low', 'Auto High', 'Off']
        self._operation_list = ['heat', 'cool', 'auto', 'off']
        self._swing_list = ['Auto', '1', '2', '3', 'Off']
        self._target_temperature_high = target_temp_high
        self._target_temperature_low = target_temp_low
        self._max_temp = target_temp_high + 1
        self._min_temp = target_temp_low - 1
        self._target_temp_step = DEFAULT_STEP

        self._unit_of_measurement = TEMP_CELSIUS
        self._current_temperature = None

        self._device = broadlink_device

        async_track_state_change(
            hass, sensor_entity_id, self._async_sensor_changed)
        
        sensor_state = hass.states.get(sensor_entity_id)
        if sensor_state:
            self._async_update_temp(sensor_state)

    @callback
    def _async_update_temp(self, state):
        """Update thermostat with latest state from sensor."""
        unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)

        try:
            self._current_temperature = self.hass.config.units.temperature(
                float(state.state), unit)
        except ValueError as ex:
            _LOGGER.error('Unable to update from sensor: %s', ex)

    @asyncio.coroutine
    def _async_sensor_changed(self, entity_id, old_state, new_state):
        """Handle temperature changes."""
        if new_state is None:
            return

        self._async_update_temp(new_state)
        yield from self.async_update_ha_state()

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return self._min_temp

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return self._max_temp
    
    @property
    def target_temperature_step(self):
        return self._target_temp_step
    
    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def name(self):
        """Return the name of the climate device."""
        return self._name

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature


    @property
    def target_temperature_high(self):
        """Return the highbound target temperature we try to reach."""
        return self._target_temperature_high

    @property
    def target_temperature_low(self):
        """Return the lowbound target temperature we try to reach."""
        return self._target_temperature_low

    @property
    def current_humidity(self):
        """Return the current humidity."""
        return self._current_humidity

    @property
    def target_humidity(self):
        """Return the humidity we try to reach."""
        return self._target_humidity

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        return self._current_operation

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return self._operation_list

    @property
    def is_away_mode_on(self):
        """Return if away mode is on."""
        return self._away

    @property
    def current_hold_mode(self):
        """Return hold mode setting."""
        return self._hold

    @property
    def is_aux_heat_on(self):
        """Return true if away mode is on."""
        return self._aux

    @property
    def current_fan_mode(self):
        """Return the fan setting."""
        return self._current_fan_mode

    @property
    def fan_list(self):
        """Return the list of available fan modes."""
        return self._fan_list

    def set_temperature(self, **kwargs):
        """Set new target temperatures."""
        if kwargs.get(ATTR_TEMPERATURE) is not None:
            self._target_temperature = kwargs.get(ATTR_TEMPERATURE)
        if kwargs.get(ATTR_TARGET_TEMP_HIGH) is not None and \
           kwargs.get(ATTR_TARGET_TEMP_LOW) is not None:
            self._target_temperature_high = kwargs.get(ATTR_TARGET_TEMP_HIGH)
            self._target_temperature_low = kwargs.get(ATTR_TARGET_TEMP_LOW)

        if self._target_temperature < self._target_temperature_low:
            self._current_operation = 'off'
            self._target_temperature = self._target_temperature_low
        elif self._target_temperature > self._target_temperature_high:
            self._current_operation = 'off'
            self._target_temperature = self._target_temperature_high
        elif self._current_temperature and (self._current_operation == "off" or self._current_operation == "idle"):
            self.set_operation_mode('auto')
            return
        
        self._sendpacket()
        self.schedule_update_ha_state()
        
        

    def set_humidity(self, humidity):
        """Set new target temperature."""
        self._target_humidity = humidity
        self.schedule_update_ha_state()

    def set_swing_mode(self, swing_mode):
        """Set new target temperature."""
        self._current_swing_mode = swing_mode
        self.schedule_update_ha_state()

    def set_fan_mode(self, fan):
        """Set new target temperature."""
        self._current_fan_mode = fan
        self.schedule_update_ha_state()

    def set_operation_mode(self, operation_mode):
        """Set new target temperature."""
        self._current_operation = operation_mode
        self._sendpacket()
        self.schedule_update_ha_state()

    @property
    def current_swing_mode(self):
        """Return the swing setting."""
        return self._current_swing_mode

    @property
    def swing_list(self):
        """List of available swing modes."""
        return self._swing_list

    def turn_away_mode_on(self):
        """Turn away mode on."""
        self._away = True
        self.schedule_update_ha_state()

    def turn_away_mode_off(self):
        """Turn away mode off."""
        self._away = False
        self.schedule_update_ha_state()

    def set_hold_mode(self, hold):
        """Update hold mode on."""
        self._hold = hold
        self.schedule_update_ha_state()

    def turn_aux_heat_on(self):
        """Turn away auxillary heater on."""
        self._aux = True
        self.schedule_update_ha_state()

    def turn_aux_heat_off(self):
        """Turn auxillary heater off."""
        self._aux = False
        self.schedule_update_ha_state()
    
    def _auth(self, retry=2):
        try:
            auth = self._device.auth()
        except socket.timeout:
            auth = False
        if not auth and retry > 0:
            return self._auth(retry-1)
        return auth    

    def _sendpacket(self,retry=2):
        """Send packet to device."""
        cool = ("JgDKAI6SEDgPFA85DjkPFA8UDzkPFA8UDzkOFQ8UDzkOOQ8UDzkPOA8UDzkOOQ84DzkOOQ84DxUOOQ8UDxUOFQ8UDxQPFQ4VDxQPFA8VDhUPFA8UDxUOOQ84EDgPOBA4DzcQOA85D62Okw84DxQPOQ84DxUOFQ45DxQPFQ45DxQPFQ45DzgPFQ45DzgPFA85DzgPOQ45DzgPOQ8UDzgPFQ4VDxQPFA8VDhUPFA8UDxUOFQ8UDxQPFQ4VDzgPOQ45DzgQOA84DzkOOQ8ADQUAAAAAAAAAAAAAAAAAAA==",
"JgDMAAZ0jZMPOA8UDzkPOBATDxUOOQ8UDxUOORATDxUOOQ84DxQPOQ84DxQPOQ84DzkOOQ84DzkOFQ84DxUOFQ4VDxQPFQ4VDhUPFA8VDjkPFA8UDxUOFQ84DzkOOQ8UDzkOOQ84EDgPrY6TDzgPFQ45DzcQFQ4VDzgPFQ4VDjkPFA8VDjkQNw8VDjkPOA8VDjkPOA85DjkPOQ45DxQPOBISDhUPFA8UDxUOFQ8UDxUPFA45DxQPFQ4VDxQPOA85DzgPFQ45DzgPNxA5DwANBQAAAAAAAAAAAAAAAA==",
"JgDKAI6SDzkPFA85DjkPFA8UDzkOFQ8UDzkOFQ8UDzgPOQ8UDzgPOQ8UDzgQOA84DzkOOQ84DxUOOQ8UDxUOFQ8UDxQPFQ4VDhUPOA85DhUPFA8VDhUPOA85DhUPFA84DzkPOA85Dq6Okw84DxQPOQ84DxQPFQ45DxQPFQ45DxQPFA85DzgPFA85DzgPFQ45DzgPOQ45DzgPOQ4VDzgPFQ4VDxQQEw8VDhUPFA8VDjkPOA8UDxUOFQ8UDzkPOA8UDxUOOQ84DzkOOQ8ADQUAAAAAAAAAAAAAAAAAAA==",
"JgDOAAsAA8uOkw45DxQPOQ45DxQPFA85DxQPFA85DhUPFA85DzgPFA85DjkPFA85DjkPOA85DjkPOA8VDjkPFA8VDhUPFA8UDxUOFQ8UDzkOFQ4VDxQPFQ4VDzgPOQ4VDzgPOQ45DzgPOQ6ujpMPOA8VDjkQNxAUDhUPOA8UDxUOOQ8UDxUOOBA4DxUOOQ84DxUOOQ84DzkPOA85DjkPFBA4DhUPFA8UDxUOFQ8UDxQPFQ45DxQPFA8VDhUPFA85DjkPFA85DjkQNw85DjkPAA0FAAAAAAAAAAAAAA==",
"JgDKAI2TDzkPFA84DzkOFQ8UDzgPFQ4VDzgPFQ4VDzgPOQ4VDzgQOBATDzgPOQ45DzgQOA84DxQPOQ4VDxQPFQ4VDhUPFA8UDzkPOA8VDhUOFQ8UDxUOOQ8UDxQPOQ45DzkOOQ84D66Nkw85DxQPOA84EBIRFA83EBUPFA85DhUPFA84DzkPFA85DjkPFA84DzkPOA85DjkPOA8VDjkPFA8VDhUOFQ8UDxUOFQ45EDcPFQ4VDxQPFQ4VDjkPFA8VDjkPOA85DzgPOA8ADQUAAAAAAAAAAAAAAAAAAA==",
"JgDKAI6TDjkPFA84DzkPFA8UDzkOFQ8UDzkOFQ8UDzkPOA8UDzkOOQ8UDzkOOQ84DzkOOQ84EBQOOQ8UDxUOFQ8UDxQPFQ4VDzgPOQ45DxQPFQ4VDhUPOA8VDhUPFA85DjkPOA85Dq6Okw84EBQOOQ84DxUOFQ45DxQPFQ45DxQPFA85DzgPFA85DzgPFA85DzgPOQ45DzgQOA4VDzgPFQ4VDxQPFA8UDxUPFA85DjkPOA8VDhUOFQ8UDzkOFQ8UDxQPOQ45EDgOOQ8ADQUAAAAAAAAAAAAAAAAAAA==",
"JgDKAI6TDzgPFA85DzgPFA8UDzkOFQ8UDzkOFQ8UDzkOORATDzkOOQ8UDzkOOQ84EDgOOQ84DxUOOQ8UEBQOFQ8UDxQPFQ4VDzgQFA45DxQPFQ4VDhUPOA8VDjkQEw85DjkPOA85Dq6Okw84DxUOORA3DxUOFQ84DxQPFQ45DxQPFQ45DzgPFQ45DzgQFA45DzgPOQ45DzkPOA8UDzkOFQ4VDxQPFQ4VDxQPFA85DhUPOA8VDhUOFQ8UDzkOFQ84DxUOOQ84DzkOOQ8ADQUAAAAAAAAAAAAAAAAAAA==",
"JgDKAI2TDjkPFA85DjkPFA8VDjkPFA8UDzkPFA8UDzkOOQ8UDzkOOQ8UDzcQOQ84DzkPOA85DhMROA8TEBUOFQ8UDxQPFQ4VDzgPFQ4VDxQPFA8VDhUPOA8VDjkPOA85DjkPOA85D62OkxA3DxUOOQ84DxUOFQ84DxUOFQ84DxQPFQ45DzgPFQ45DzkOFQ45EDgOOQ84DzkOOQ8UDzkOFQ8UDxQPFQ4VDxQPFA85DxQQEw8VDhUPFA8UDzkOFQ84DzkOOQ85DjkPOA8ADQUAAAAAAAAAAAAAAAAAAA==",
"JgDKAI2TDzkOFQ84DzkPFA8UDzkOFQ8UDzgQFA4VDzgQOA4VDzgPOQ4VDzgPOQ45DzgPOQ84DxQPOQ8UDxQPFQ4VDxQPFA85DjkQEw8VDhUPFA8UDxUOFQ8UDzkOOQ84DzkOOQ84D66Okw45DxQPOQ45DxQPFA85DxQPFA85DhUPFA83EDkPFA85DjkPFA85DjkPOBA4DjkQNw8VDjkPFBAUDhUOFRATDxUOOQ84EBQOFQ4VDxQPFQ4VDhUPFA85DjkPOA85DzgPOQ4ADQUAAAAAAAAAAAAAAAAAAA==",
"JgDKAI2TDzkOFQ84EDgPFA8UDzgPFQ4VDzgQFA8UDzgQOA4VDzgPOQ8UDzgQOA84DzgQOA45EBMPOQ4VDxQQFA4VDxQPFA85DjkPFA85DhUPFA8UDxUOFQ8UDzkPFA84EDgOOQ84D66Okw45EBMPOQ45DxQPFA85DxQPFA85DhUPFA85DjkQEw85DjkPFA85DjkPOA85DjkQNxAUDzgPFA8VDxQPFA8UDxUOOQ84DxUOOQ8UDxUOFQ8UDxQPFQ45DxQPOQ45DzgQOA4ADQUAAAAAAAAAAAAAAAAAAA==",
"JgDQAAcACZoHWI2TDzkPFA84DzkPFA8UDzkOFQ8UDzkOFQ8UDzkOOQ8UDzkOOQ8UDzkOOQ84DzcQOQ84DxUOOQ8UDxUOFQ8UDxQPFQ45DxQPFQ45DxQPFA8VDhUPFA85DjkPFA85DjkPOA85Dq6Okw84DxUOOQ84DxUOFQ84DxUOFQ45DxQPFQ45DzgPFQ45DzgPFQ45DzgPOQ45DzgPOQ8UDzgPFQ4VDxQPFA8VDhUPOA8VDhUPOA8UDxUOFQ8UDxQPOQ45DxQPOQ45DzkOOQ8ADQUAAAAAAAAAAA==",
"JgDKAI2TDzkPFA84DzkPFA8UDzkOFQ8UDzkOFQ8UDzgPOQ4VDzgPOQ8UDzgPOQ84DzkOOQ84DxUOOQ8UDxUOFQ4VDxQPFQ45DxQPFA8VDhUPFA8UDxUOFQ84DzkOOQ84DzkPOA85Dq6Okw84DxQPOQ84DxUOFQ45DxQPFQ45DxQPFQ45DzgQFA45DzgPFQ45DzgPOQ45DzgPNxAVEDcQFA4VDxQPFA8VDhUPOA8UDxUOFQ8UDxUOFQ8UDxQPOQ45DzgPOQ84DzgPOQ8ADQUAAAAAAAAAAAAAAAAAAA==",
"JgDKAI6TDjkPFA85DjgQFA8UDzkOFQ8UDzkOFQ8UDzkOOQ8UDzkOOQ8UDzkOOQ84DzkOOQ84DxUOOQ8UDxUOFQ4VDxQPFQ45DxQPOA8VDhUPFA8VDhUPFA84DxUOOQ84DzkPOA85Dq6Okw84EBMPOQ84DxQPFQ45DxQPFQ45DxQPFA85DzgPEhE5DzgPFQ45DzgPOQ45DzgQOA4VDzgPFQ4VDxQPFA8VDhUPOA8UDzkPFA8UDxUOFQ8UDxQPOQ4VDzcQOQ84DzkOOQ8ADQUAAAAAAAAAAAAAAAAAAA==",
"JgDKAI2TDzkOFQ84DzkOFQ8UDzkOFQ4VDzgPFQ4VDzgPOQ4VDzgPOQ4VDzgPOQ43ETgPOQ45DxQPOQ4VDxQPFQ4VDxQPFA85DhUPOA85DhUPFA8VDhUOFQ84EBQOFQ84DzkOOQ84EK2Okw45EBMPOQ45DxQPFA85DxQPFA85DhUPFA85DjkPFA85DzgPFA85DjkPOA85DjkPOA8VDjkQEw8VDhUPFA8UDxUOOQ8UDzkOOQ8UDxQPFQ4VDxQPOA8VDhUPOBA4DzgPOQ8ADQUAAAAAAAAAAAAAAAAAAA==")
        off = "JgDMAI2TDjkPFA85DzgQEw8VDjkPFA8UDzkOFQ8UDzkOORATDzkOFBE3DzkOORA2EBUOOQ8FBC8QOA4VDxQPFQ4VDjkPFBAUDjkQNxA4DhUPFA8VDhUPFA8UDxUOFQ45DzkPOA84DzkOq5GTDzgPFA85DzgPFQ8UDjkQEw8VDjkQExATDzkPOA8UDzkPFA85DjkPOBA4DhUPOBA4DjkPFA8UDxUOFQ84DxUOFQ84DzkOORATDxUOFQ8UDxQPFQ4VDxQPOBA4DzgPOQ84DwANBQAAAAAAAAAAAAAAAA=="
        heat = ("JgDKAA45DxQPOQ84DxQPFA85DxQPFBA4DhUPFA85DjkPFA85DzgPFA85DjkPOA85DjkPOA8VDjkPFA8VDhUOFQ8UDxUOFQ8UDxQPFQ45DzgQFA4VDgYHKhE5DzgPOA8VDhUOORA3D66Okw45EBMQOA84DxQPFQ45DxQPFQ45DxQQEw85DzgPFA85DjkPFA85DjkQNw85DzgQOA8UDzgQEw8VDhUPFA8VDhUOFQ8UDxUOFQ45EDcQEhAVDzgPOQ45EDcQFA4VDzgPOQ4ADQUAAAAAAAAAAAAAAAAAAA==",
"JgDKAI2UDjgQFA85DzgPFA8UDzkOFQ8UDzkOFQ8UDzgQOA8UDzgPOQ4VDzgPOQ84DzkOORA3EBQOORATDxUOFQ4VDxQPFQ4VDhUPFA85DzQVNg8VDhUPOA82ETkPFA8VDhUPOBA3EquOkw45EBMPOQ45DxQPFQ45DxQQFA45DxQQEw85ETYQEw46DzgPFA85DjkQOA45DzgPOQ4VDzgPFQ4VDhUQEw8VDhUOFQ8UDxUOORA3DzkPFA8UDzkOOBE3DxUOFQ4VDzgQOA8ADQUAAAAAAAAAAAAAAAAAAA==",
"JgDKAI2UDzgPFA84DzkPFA8UDzkPFA8UDzkPFA8UDzgPOQ8UDzkOOQ8UDzkOOQ84EDgPOBA3EBQOORATDxUOFQ4VDxQPFA8VDxQPOA85DjkPOQ4VDhUPOBA4DhUPFA8UDxUOOQ84EK2Okw84EBMPOQ84EBMPFQ45DxQPFA85DhUPFA85DjkPFA85DjkQEw85DjkPOBA4DjkPOA8VDjkQEw8VDhUPFA8UDxUOFQ4VDzgQOA84DzkOFQ8UDzgQOA4VDxQPFQ4VDjgQOQ8ADQUAAAAAAAAAAAAAAAAAAA==",
"JgDKAI2TDzgPFQ45EDcQFA4VDzgQFA4VDjkQExAUDjkPOA8VDzgQNw8VDjkQNxA4DzgPOQ84DxQPOBAUDhUPFA8VDhUPFA8UDxUOOQ8UDzkOOQ8UDxQPOQ84DxQPOQ8UEBMPOQ84D62OkxA4DhUPOBA4DxQPFA85DhUPFA84DxUOFQ84DzkOFQ84DzkOFQ84EDgPOBA3DzkPOBATDzkPFA8UEBQOFQ4VDxQPFQ4VDzgPFQ45DzgQEw8VDjkQNw8VDjkQEw8VDjkQNxAADQUAAAAAAAAAAAAAAAAAAA==",
"JgDKAI2TDzkPFA84DzkPFA8UDzkPFA8UDzgPFQ4VDzgPOQ4VDzgPOQ4VDzgPOQ84EDcPOQ45DxQPOQ8UDxQPFA8VDhUPFA8VDjkPOA8VDjkPOBAUDhUPOBATEBQOOQ8UDxUOOQ84EK2Okw45DxQPOQ84EBMPFA85DxQPFA85DhUPFBA4DjkPFA85DjkQEw85DjkPOBA4DjkPOQ4VDjQUFA8VDhUPFA8UDxUOFQ84EDgOFQ84DzkOFQ8UDzkPFA8UDzgPFQ4VDzgPOQ4ADQUAAAAAAAAAAAAAAAAAAA==",
"JgDKAI2TDzgQFA84DzgQFA8UDjkQEw8VDjkQEw8VDjkPOBATDzkQNw8VDjkQNw85DjkPOBA4DxQQNw8VDhUPFA8UDxUOFQ8UDzkPOA84DzkOORATEBQPOBATDxQPFQ8UDxQPOQ45EKyPkhA0EhUPOA84DxUOFQ84EBQPFA84DxMQFQ45DzgPFQ45DzkOFQ84DzgQOA45DzkOOQ8UDzkOFQ8UDxQPFQ4VDxQPFA85DzgPOQ45DzgPFQ4VDjkPFA8VDhUOFQ8UDzkOORAADQUAAAAAAAAAAAAAAAAAAA==",
"JgDKAI6SDzkQEw84DzkPFA8UEDgOFQ8UDzkOFQ8UDzkOOQ8UEDgOOQ8UDzkPOA84DzkOORA3DxUOOQ8UDxUOFQ4VDxQPFQ4VETYPFBA4DzgPOQ4VDxQPOA8VDzgPFBAUDhUPOA85Dq6Okw84DxQPOQ45EBQPFA84DxQPFQ45DxQPFQ45DjkPFA85DjgQFA85DjkPOBA4DzgPORATDzgQEw8VDhUPFA8VDhUPFA84DxURNg84DzkQEw8UDzkOFQ84DxQPFQ4VDzgPOQ4ADQUAAAAAAAAAAAAAAAAAAA==",
"JgDKAI2TDzgPFA85DjkPFA8VDjkPFBATDzgPFQ8UDzkOORATDzkOOQ8UDzkOOQ84EDgPOA85DxQPOA8UDxUPFA8UDxQPFQ8UDzgQFA4VDzgPOQ4VDxQQNxAUDjkQNw8VDhUPOBA4Dq6Okw84EBQOOQ84DxUOFQ84EBMPFQ45DxQPFQ45EDYQFQ45DzgQFA45EDcPOQ45EDcPOQ8UDzgQFA4VDxQPFQ4VDhUPFA85DxQPFA84DzcRFA8UDzkPFA84DzkOFQ8UDzkPOA8ADQUAAAAAAAAAAAAAAAAAAA==",
"JgDKAI2TDjkQEw85DjkPFA8VDjkPFA8VDjkPFA8UDzkOORATDzkOORATDzkOOQ85DzgPOBA4DxQPOBAUDhUOFQ8UDxUOFQ45DzkPFA8UDzgQOA8UDxQPFQ4VDzgRNw8UDxQPOBA4D62Okw84DxUOOBA4DxUOFQ84EBQOFQ84DxUOFQ84EDgPFA84EDYRFA45EDgPOA84DzkPOA8UDzkOFQ8UDxQPFQ8UDxQPOQ84EBMPFBA4DzgPFQ4VDhUPFA85DjkPFA8VDjkPOBAADQUAAAAAAAAAAAAAAAAAAA==",
"JgDKAI6TDzgPFA85DzgQEw8UDzkPFA8UDzkPFA8UDzkPOBATDzkOORATDzkPOBA3DzkPOBA2EBUOORATDxUOFQ8UDxQPFQ45DzgPFQ45DzgPOQ4VDxQQFA4VDzgQExISDhYOOBA4D62Okw84DxUOOQ84EBQOFQ84EBMPFQ45DxQPFQ45EDcQFA45DzgPFQ45EDcPOQ84DzgPOQ4VDzgQFA8UDxQPFA8VDxQPOBA4DxQPOA85DjkPFBAUDhUPFA84DxUOFQ8UDzkOOQ8ADQUAAAAAAAAAAAAAAAAAAA==",
"JgDKAI2TDzgPFA85DjkQEw8VDjkPFA8UDzkPFA8UDzkOOQ8UDzkPOBATDzkOOQ84EDgOOQ85DxQPOA8UDxUOFQ8UDxQPFQ45DxQPFQ45DzgPOQ8UDxQPFBA4DzgPFA8VDhUPOBA4Dq6Okw84DxUOOQ84EBQOFQ84EBQOFQ45DxQPFQ45EDcQFA45DzgPFQ45EDcQOA45DzgQOA4VDzgQFA4VDxQPFA8VDhUPOA8VDhUPOBA4DzgPFA8UDxUOOQ84EBQOFQ8UDzkPOA8ADQUAAAAAAAAAAAAAAAAAAA==",
"JgDOAI2TDjcSEw85DjkPFBAUDjkPFA8VDjkPFA8UEDgOORESDzkOOQ8UDjoOOQ84DzkPOA85DhUPOBAUDhUOFQ8UDxUOFQ45DhUPFQ4VDzgPOQ8UDxQPFA85DzgSNQ8VDhUPOBA4Dq6Okw45DxUOOQ84DxUNFg84DxUOFQ45DxQPFQ45DzgQFA84DzgPFQ45EDcPOQ45DzkOOQ8UDzgPFQ4WDhQPFQ4VDhUPOA8VDhUPFA85ETYOFQ8UDxUOORA3DzkPFA8UDzkOOQ8AA2sEAA0FAAAAAAAAAAAAAA==",
"JgDKAI2TEDgOFQ84DzkOFQ8UEDgOFQ8UEDgPFA4VDzgQOA4VDjkPOQ4VDzgQOA45EDcPOQ84DxQPOQ4VDxQPFQ8UDhUPFA85DhUPOA8VDjkPOA8VDhUOFQ85DhUOOQ8UDxUOOQ84D66Pkg84DxQPOQ84DxQPFA85DxQPFA85DxQPFA85DjkPFA85DjkPFA85DjkPOA85DjkPOA8VDjkPFA8VDhUPFA8UDxUOOQ8UDzkOFQ84DzkOFQ8UEBMQOA8UDzgPFQ4VDjkPOQ4ADQUAAAAAAAAAAAAAAAAAAA==",
"JgDKAI2TDzkPFBA3DzkPFA8UDzkPFBATEDcPFQ4VDzgQOA8UDzUSOQ4VDzgPOQ84DzkQNw84DxUOOQ4VDxQPFQ4VDxQPFA46DxQPOA85DjkPOA8VDhUPFA85DxQOFQ8UDxUOOQ84D66Okw45DxQQOA45EBMQEw85DxQPFBM1DhUREg85DjkPFA85DzgPFA85DzQTOA85DzgPOBAUDjkPFA8VDhUOFQ8UDxUOORATDzkPOA84EDgOFQ4VDxQPORATDxQQFA4VDjkPOQ8ADQUAAAAAAAAAAAAAAAAAAA==")
        
        if (self._current_operation == 'idle') or (self._current_operation =='off'):
            sendir = b64decode(off)
        elif self._current_operation == 'heat':
            sendir = b64decode(heat[int(self._target_temperature) - self._target_temperature_low])
        elif self._current_operation == 'cool':
            sendir = b64decode(cool[int(self._target_temperature) - self._target_temperature_low])
        else:
            if self._current_temperature and (self._current_temperature < self._target_temperature_low):
                sendir = b64decode(heat[int(self._target_temperature) - self._target_temperature_low])
            else:
                sendir = b64decode(cool[int(self._target_temperature) - self._target_temperature_low])
        
        try:
            self._device.send_data(sendir)
        except (socket.timeout, ValueError) as error:
            if retry < 1:
                _LOGGER.error(error)
                return False
            if not self._auth():
                return False
            return self._sendpacket(retry-1)
        return True