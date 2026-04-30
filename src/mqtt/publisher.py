"""
Singleton MQTT client for the drone. Handles the connection to the broker,
routes incoming command messages to the registered callback, and publishes
status updates to the backend.
"""

import paho.mqtt.client as mqtt
import json
import threading
import time
import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)

DRONE_ID = 5


class MQTTPublisher:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, host: str = "16.171.145.191", port: int = 1883):
        if hasattr(self, '_initialized') and self._initialized:
            return
        self.host = host
        self.port = port
        self._client = None
        self._connected = False
        self._initialized = True
        self._command_callback: Optional[Callable[[str, dict], None]] = None
        self._connect()

    def _connect(self):
        self._client = mqtt.Client()
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message
        try:
            self._client.connect(self.host, self.port, 60)
            self._client.loop_start()
        except Exception as e:
            logger.error(f"MQTT connection error: {e}")

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info("MQTT connected")
            self._connected = True
            client.subscribe(f"drones/{DRONE_ID}/command", qos=1)
            logger.info(f"Subscribed to drones/{DRONE_ID}/command")
        else:
            logger.error(f"MQTT connection failed with code {rc}")

    def _on_disconnect(self, client, userdata, rc):
        logger.warning(f"MQTT disconnected (code {rc})")
        self._connected = False

    def _on_message(self, client, userdata, msg):
        """
        Parse an incoming JSON command and forward it to the registered callback.
        Expects payload shape: {"action": str, "data": dict}.
        Malformed or unhandled messages are logged and dropped silently.
        """
        try:
            print(f"MQTT message received: topic={msg.topic} payload={msg.payload}")
            payload = json.loads(msg.payload.decode())
            action = payload.get("action")
            data = payload.get("data", {})
            logger.info(f"Command received: action={action} data={data}")
            if self._command_callback:
                self._command_callback(action, data)
        except Exception as e:
            logger.error(f"Error processing command: {e}")

    def register_command_callback(self, callback: Callable[[str, dict], None]):
        """Register the function called for every incoming command message. Receives (action: str, data: dict)."""
        self._command_callback = callback

    def publish(self, topic: str, payload: dict) -> bool:
        if not self._connected:
            for _ in range(10):
                time.sleep(0.5)
                if self._connected:
                    break
            if not self._connected:
                logger.error(f"MQTT not connected, dropping: {topic}")
                return False
        try:
            result = self._client.publish(topic, json.dumps(payload), qos=1)
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.debug(f"Published {topic}: {payload}")
                return True
            logger.error(f"Publish failed {topic}: {result.rc}")
            return False
        except Exception as e:
            logger.error(f"Publish error: {e}")
            return False

    def publish_status(self, status: str, battery: int, is_in_maintenance: bool,
                       oid: Optional[int] = None) -> bool:
        """Publish drone state to the backend. This is the only topic the backend reads."""
        payload = {
            "status": status,
            "batteryLevel": battery,
            "isInMaintenance": is_in_maintenance,
        }
        if oid is not None:
            payload["oid"] = oid
        return self.publish(f"drones/{DRONE_ID}/status", payload)

    def stop(self):
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()


_publisher: Optional[MQTTPublisher] = None


def get_publisher(host: str = "16.171.145.191", port: int = 1883) -> MQTTPublisher:
    global _publisher
    if _publisher is None:
        _publisher = MQTTPublisher(host, port)
    return _publisher
