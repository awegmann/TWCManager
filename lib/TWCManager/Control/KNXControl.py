"""
KNXControl is the control interface implementation for KNX automation bus. It supports the start now
command.

Control setup example:
      "KNX": {
        "enabled": true,
        "gatewayIP": "172.16.0.1",
        "gatewayPort": "6720",
        "chargeNowDurationAddress": "1/1/10",
        "chargeNowDurationDefault": "3600",
        "chargeNowRateAddress": "1/1/11",
      }

    01/2021 Andreas Wegmann
"""
import asyncio
import ipaddress
import re
import threading

import knxdclient


def is_valid_port(val):
    """
    Check if given value is a valid port number.

    Parameters:
        val(int or str): value to check

    Returns:
        bool: True if val is a valid port number, False otherwise
    """
    if not val:
        return False
    if type(val) == int and 0 < val < 2 ** 16:
        return True
    else:
        return 0 < int(val) < 2 ** 16


def is_knx_address(val):
    """
    Rough estimation if the given value is a KNX address.

    Parameters:
        val(int or string): Address to be checked

    Returns:
        bool: True if given address is valid, False otherwise
    """
    if not val:
        return False
    return re.match(r"\d{1,3}/\d{1,3}/\d{1,3}", val) is not None


class KNXControl:
    enabled = False
    master = None

    @property
    def is_properly_configured(self) -> bool:
        try:
            ip = ipaddress.ip_address(self.gatewayIP)
        except ValueError:
            self.master.debugLog(1, "KNXControl", f"gatewayIP:{self.gatewayIP} is not a correct IP address.")
            return False

        if not is_valid_port(self.gatewayPort):
            self.master.debugLog(1, "KNXControl", f" gatewayPort: {self.gatewayPort} is not a correct port.")
            return False

        if not is_knx_address(self.chargeNowRateAddress):
            self.master.debugLog(1,
                                 "KNXControl",
                                 f"chargeNowRateAddress: {self.chargeNowRateAddress} is not a correct KNX address.")
            return False

        return True

    def __init__(self, master):
        self.master = master
        try:
            self.configConfig = master.config["config"]
        except KeyError:
            self.configConfig = {}
        try:
            self.configKnx = master.config["control"]["KNX"]
        except KeyError:
            self.configKnx = {}
        self.gatewayIP = self.configKnx.get("gatewayIP", None)
        self.gatewayPort = self.configKnx.get("gatewayPort", None)
        self.chargeNowDurationAddress = self.configKnx.get("chargeNowDurationAddress", None)
        self.chargeNowRateAddress = self.configKnx.get("chargeNowRateAddress", None)
        self.chargeNowDuration = self.configKnx.get("chargeNowDurationDefault", None)
        self.status = self.configKnx.get("enabled", False)

        # Unload if this module is disabled or misconfigured
        if not self.status:
            self.master.releaseModule("lib.TWCManager.Control", "KNXControl")
            return None

        if not self.is_properly_configured:
            raise RuntimeError("KNX modules not configured correctly.")

        if is_knx_address(self.chargeNowRateAddress):
            self.chargeNowRateAddress = self.group_address_from_string(self.chargeNowRateAddress)

        if is_knx_address(self.chargeNowDurationAddress):
            self.chargeNowDurationAddress = self.group_address_from_string(self.chargeNowDurationAddress)

        t = threading.Thread(target=self.start_server, daemon=True)
        t.start()

    @staticmethod
    def group_address_from_string(s: str) -> knxdclient.GroupAddress:
        """
        Converts a given string in format "main/middle/sub" to a GroupAddress object.
        Parameters:
            s(str): String to be converted
        Returns:
            Object of type knxdclient.GroupAddress
        """
        adr_tuple = (int(n) for n in s.split('/'))
        return knxdclient.GroupAddress(*adr_tuple)

    async def knx_packet_handler(self, packet: knxdclient.ReceivedGroupAPDU) -> None:
        """
        The KNX packet receiver handler. This function is called for every received packet
        on the KNX bus. It checks if the packet is a write command for either the charge now rate or the
        charge now duration.
        In case it is for the duration the duration time (in seconds) is stored in
        self.chargeNowDuration.
        In case it is a write command for the charge now rate address, the charge now is triggered by
        calling setChargeNowTimeEnd and setChargeNowAmps on the master.
        """
        self.master.debugLog(11, "KNXControl", "Received group telegram: {}".format(packet))
        self.master.debugLog(11, "KNXControl",
                             f"Comparing with {self.chargeNowRateAddress} and {self.chargeNowDurationAddress}")

        if self.is_valid_chargenow_cmd(packet, self.chargeNowRateAddress):
            amps = int(knxdclient.decode_value(packet.payload.value, knxdclient.KNXDPT.FLOAT32))
            if amps == 0:
                self.master.debugLog(1, "KNXControl", f"Got chargeNowRate of 0. canceling charge.")
                self.master.resetChargeNowAmps()
            else:
                self.master.debugLog(1, "KNXControl",
                                     f"Got chargeNowRate. Setting amps to {amps}, duration to {self.chargeNowDuration}")
                self.master.setChargeNowTimeEnd(self.chargeNowDuration)
                self.master.setChargeNowAmps(amps)
        elif self.is_valid_chargenow_cmd(packet, self.chargeNowDurationAddress):
            duration = knxdclient.decode_value(packet.payload.value, knxdclient.KNXDPT.UINT16)
            if duration <= 0:
                self.master.debugLog(1, "KNXControl", f"Got chargeNowDuration <0. canceling charge.")
                self.master.resetChargeNowAmps()
            else:
                self.chargeNowDuration = duration
                self.master.debugLog(8, "KNXControl",
                                     f"Got chargeNowDuration. Setting duration for next charge to {self.chargeNowDuration}")
        else:
            self.master.debugLog(8, "KNXControl", "not a chargeNowRate")

    def is_valid_chargenow_cmd(self, packet, dst) -> bool:
        """
        Check if the given packet is a valid KNX write to the charge now address.
        Parameters:
            packet: object to be checked
        Returns:
            True if packet is a valid charge now cmd packet
        """
        return packet.dst == dst and type(
            packet.payload) == knxdclient.KNXGroupAPDU and packet.payload.type == knxdclient.KNXDAPDUType.WRITE

    async def knx_server_loop(self) -> None:
        """
        The asynchronous KNX server loop. Creates a new KNXDConnection object object, registers the receiver handler
        and handles connection to the gateway. If the gateway is not reachable, a new connection attempt is made
        every 30 seconds.
        """
        self.master.debugLog(8, "KNXControl", "creating client")
        connection = knxdclient.KNXDConnection()

        self.master.debugLog(8, "KNXControl", "created client")
        connection.register_telegram_handler(self.knx_packet_handler)

        self.master.debugLog(8, "KNXControl", "registerd handler")
        while True:
            try:
                self.master.debugLog(8, "KNXControl", f"trying to connect to {self.gatewayIP}:{self.gatewayPort}")
                await connection.connect(host=self.gatewayIP, port=self.gatewayPort)
                self.master.debugLog(8, "KNXControl", "connected")

                run_task = asyncio.create_task(connection.run())

                self.master.debugLog(8, "KNXControl", "creating receiver socket")
                await connection.open_group_socket()

                self.master.debugLog(8, "KNXControl", "entering loop")
                await run_task
            except OSError as e:
                self.master.debugLog(2, "KNXControl", "connect failed. waiting before next try...")
                await asyncio.sleep(30)
            except:
                self.master.debugLog(2, "KNXControl", "catched unexpected exception. try to reconnect...")
                await asyncio.sleep(1)

    def start_server(self):
        """
        The thread function called by the __init__() function. Creates a new asyncio event loop and runs
        self.knx_server_loop().
        """
        event_loop = asyncio.new_event_loop()
        event_loop.run_until_complete(self.knx_server_loop())
