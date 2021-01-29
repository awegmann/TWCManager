# KNX Control Module

## Introduction

The KNX Control Module allows control over the TWCManager Tesla Wall Charger controller using
KNX via an KNX IP-Gateway. By sending packets to KNX addresses, the "charge now" and "charge end" 
can be triggered.

### Status

| Detail          | Value          |
| --------------- | -------------- |
| **Module Name** | KNXControl    |
| **Module Type** | Status         |
| **Status**      | In Development |

## Configuration

The following table shows the available configuration parameters for the KNX Control module.

| Parameter   | Value         |
| ----------- | ------------- |
| enabled     | *required* Boolean value, ```true``` or ```false```. Determines whether we will enable MQTT control. |
| gatewayIP   | *required* The IP address of the KNX gateway. |
| gatewayPort | *required* The port number of the KNX gateway. |
| chargeNowDurationAddress    | *optional* KNX group address to send the charge now duration (in seconds) to. |
| chargeNowDurationDefault    | *optional* Default value for "charge now" duration. This is set as a default on startup. When the first packet arrives on the chargeNowDurationAddress, this value is replaced with the packet data. |
| chargeNowRateAddress    | *required* KNX group address to send the charge now rate in Amps to. |

### JSON Configuration Example

```
"KNX": {
    "enabled": true,
    "gatewayIP": "172.16.0.1",
    "gatewayPort": 6720,
    "chargeNowDurationAddress": "1/1/10",
    "chargeNowDurationDefault": 3600,
    "chargeNowRateAddress": "1/1/11",
}
```

## Starting Charge Now

Whenever a packet arrives for the group address configured in *chargeNowRateAddress*, the value is decodes and together 
with the last duration sent to *chargeNowDurationAddress* (or the default) the "charge now" state
is entered. 

The following table shows, which payload type is expected on the two different addresses and
what the unit of the values are.

| Address                  | Type   | Unit     |
|--------------------------|--------|----------|
| chargeNowRateAddress     | UINT8  | Amps     |
| chargeNowDurationAddress | UINT16 | Seconds  |

### Example

If you want to start "charge now" for ten hours with 16 Amps, you have to

1. send a packet to *chargeNowDurationAddress* with the UINT16 value of '36000'
2. send a packet to *chargeNowRateAddress* with the UINT8 value of '16'

There is now timeout after a packet to *chargeNowDurationAddress*. The duration received
is just stored in memory and used for the next packet to *chargeNowRateAddress* which then triggers
the "charge now" stage. You can also re-trigger the charge now state with different rates
by sending new packets to *chargeNowRateAddress* which just reuses the last 
received duration.

## Stopping Charge

Whenever a value of '0' is received either on *chargeNowDurationAddress* or *chargeNowRateAddress* a currently
enabled charge is stopped.  
