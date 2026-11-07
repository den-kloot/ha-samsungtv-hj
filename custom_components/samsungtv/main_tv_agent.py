"""Samsung MainTVAgent2 UPnP service (2014/2015 H/J-series TVs).

H/J-series TVs paired with the "encrypted" method expose the vendor service
``urn:samsung.com:service:MainTVAgent2:1`` (discovered via SSDP and already
stored in the config entry as ``ssdp_main_tv_agent_location``). Once the TV is
paired it answers:

- ``GetSourceList``            -> XML list of inputs (SourceType, ID, Connected)
- ``GetCurrentExternalSource`` -> the active input (e.g. ``HDMI4``)
- ``SetMainTVSource``          -> switch directly to an input

Before pairing the TV answers these with UPnP error 501, so every call here is
best effort: callers must fall back to the key-based behaviour on error.
"""

from __future__ import annotations

from dataclasses import dataclass

from async_upnp_client.aiohttp import AiohttpSessionRequester
from async_upnp_client.client import UpnpService
from async_upnp_client.client_factory import UpnpFactory
from async_upnp_client.exceptions import UpnpError
from defusedxml import ElementTree

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import LOGGER, UPNP_SVC_MAIN_TV_AGENT


@dataclass(frozen=True, slots=True)
class MainTVSource:
    """One input of the TV as reported by GetSourceList."""

    source_type: str
    source_id: int
    connected: bool


class MainTVAgent:
    """Thin async wrapper around the MainTVAgent2 UPnP service."""

    def __init__(self, service: UpnpService) -> None:
        """Initialize with an already resolved UPnP service."""
        self._service = service
        self.sources: dict[str, MainTVSource] = {}

    @classmethod
    async def async_create(
        cls, hass: HomeAssistant, location: str
    ) -> MainTVAgent | None:
        """Create the agent from the SSDP location, or None if unavailable."""
        requester = AiohttpSessionRequester(async_get_clientsession(hass))
        # non_strict: Samsung TVs send values that violate their own SCPD
        factory = UpnpFactory(requester, non_strict=True)
        try:
            device = await factory.async_create_device(location)
        except UpnpError as err:
            LOGGER.debug("Unable to create MainTVAgent2 device: %r", err)
            return None
        if not device.has_service(UPNP_SVC_MAIN_TV_AGENT):
            LOGGER.debug("Device at %s has no MainTVAgent2 service", location)
            return None
        return cls(device.service(UPNP_SVC_MAIN_TV_AGENT))

    async def async_update_sources(self) -> dict[str, MainTVSource]:
        """Fetch the input list (raises UpnpError, e.g. 501 when not paired)."""
        result = await self._service.action("GetSourceList").async_call()
        self.sources = _parse_source_list(result.get("SourceList") or "")
        return self.sources

    async def async_get_current_source(self) -> str | None:
        """Return the active input type, e.g. 'HDMI4' (raises UpnpError)."""
        result = await self._service.action("GetCurrentExternalSource").async_call()
        if result.get("Result") != "OK":
            return None
        return result.get("CurrentExternalSource") or None

    async def async_set_source(self, source_type: str) -> bool:
        """Switch to an input from the last fetched list (raises UpnpError)."""
        source = self.sources[source_type]
        result = await self._service.action("SetMainTVSource").async_call(
            Source=source.source_type, ID=source.source_id, UiID=-1
        )
        return result.get("Result") == "OK"


def _parse_source_list(xml: str) -> dict[str, MainTVSource]:
    """Parse the XML document returned in the SourceList out-argument."""
    sources: dict[str, MainTVSource] = {}
    if not xml:
        return sources
    try:
        root = ElementTree.fromstring(xml.encode())
    except ElementTree.ParseError as err:
        LOGGER.debug("Unable to parse MainTVAgent2 source list: %r", err)
        return sources
    for node in root.iter("Source"):
        source_type = (node.findtext("SourceType") or "").strip()
        source_id = (node.findtext("ID") or "").strip()
        if not source_type or not source_id.lstrip("-").isdigit():
            continue
        sources[source_type] = MainTVSource(
            source_type=source_type,
            source_id=int(source_id),
            connected=(node.findtext("Connected") or "").strip() == "Yes",
        )
    return sources
