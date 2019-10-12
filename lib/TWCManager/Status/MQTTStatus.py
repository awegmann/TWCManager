# MQTT Status Output
# Publishes the provided key and value pair to the provided topic prefix

class MQTTStatus:

  import time
  import paho.mqtt.client as mqtt

  brokerIP        = None
  brokerPort      = 1883
  connectionState = 0
  debugLevel      = 0
  msgQueue        = []
  msgQueueBuffer  = []
  msgQueueMax     = 16
  msgRate         = {}
  msgRatePerTopic = 60
  password        = None
  status          = False
  serverTLS       = None
  topicPrefix     = None
  username        = None

  def __init__(self, debugLevel, config):
    self.debugLevel  = debugLevel
    self.status      = config.get('enabled', False)
    self.brokerIP    = config.get('brokerIP', None)
    self.topicPrefix = config.get('topicPrefix', None)
    self.username    = config.get('username', None)
    self.password    = config.get('password', None)

  def debugLog(self, minlevel, message):
    if (self.debugLevel >= minlevel):
      print("MQTTStatus: (" + str(minlevel) + ") " + message)

  def setStatus(self, twcid, key, value):
    if (self.status):
      topic = self.topicPrefix+ "/" + str(twcid.decode("utf-8"))
      topic = topic + "/" + key

      # Perform rate limiting first (as there are some very chatty topics).
      # For each message that comes through, we take the topic name and check
      # when we last sent a message. If it was less than msgRatePerTopic
      # seconds ago, we dampen it.
      if (topic in self.msgRate): 
        if ((self.time.time() - self.msgRate[topic]) < self.msgRatePerTopic):
          return True
        else:
          self.msgRate[topic] = self.time.time()
      else:
        self.msgRate[topic] = self.time.time()

      # Now, we push the message that we'd like to send into the
      # list of messages to be published once a connection is established
      msg = { "topic": topic, "payload": value }
      self.msgQueue.append(msg.copy())

      # If msgQueue size exceeds msgQueueMax, trim the list size
      # This will discard MQTT messages in environments where the MQTT
      # broker cannot accept the rate of MQTT messages sent
      if (len(self.msgQueue) > (self.msgQueueMax + 8)):
        del self.msgQueue[:self.msgQueueMax]

      # Now, we attempt to establish a connection to the MQTT broker
      if (self.connectionState == 0):
        self.debugLog(10, "MQTT Status: Attempting to Connect")
        try:
          client = self.mqtt.Client()
          if (self.username and self.password):
            client.username_pw_set(self.username, self.password)
          client.on_connect = self.mqttConnected
          client.connect_async(self.brokerIP, port=self.brokerPort, keepalive=30)
          self.connectionState = 1
          client.loop_start()
        except ConnectionRefusedError as e:
          self.debugLog(4, "Error connecting to MQTT Broker to publish topic values")
          self.debugLog(10, str(e))
          return False
        except OSError as e:
          self.debugLog(4, "Error connecting to MQTT Broker to publish topic values")
          self.debugLog(10, str(e))
          return False

  def mqttConnected(self, client, userdata, flags, rc):
    # This callback function is called once the MQTT client successfully
    # connects to the MQTT server. It will then publish all queued messages
    # to the server, and then disconnect.

    self.debugLog(10, "Connected to MQTT Broker with RC: " + str(rc))
    self.debugLog(11, "Copy Message Buffer")
    self.msgQueueBuffer = self.msgQueue.copy()
    self.debugLog(11, "Clear Message Buffer")
    self.msgQueue.clear()

    for msg in self.msgQueueBuffer:
      self.debugLog(8, "Publishing MQTT Topic " + str(msg['topic']))
      try:
        client.publish(msg['topic'], payload=msg['payload'])
      except e:
        self.debugLog(4, "Error publishing MQTT Topic Status")
        self.debugLog(10, str(e))

    client.loop_stop()
    self.msgQueueBuffer.clear()
    self.connectionState = 0
    client.disconnect()
