"""
Core business logic for the drone. DroneLogic is passed as the `obj` to the
stmpy Machine, so every method name referenced in drone_states.py resolves
directly to a method here.

Responsibilities:
  - State entry/exit/effect actions called by the STM (e.g. charge, load_package)
  - Handling incoming MQTT commands dispatched by MQTTPublisher
  - Translating Sense HAT joystick presses into STM triggers
  - Keeping backend_status and stm_state in sync for status reporting
"""

import logging
import threading
from src.mqtt.publisher import get_publisher

try:
    from src.controllers.senseController import SenseController
    _SENSE_AVAILABLE = True
except Exception:
    _SENSE_AVAILABLE = False

logger = logging.getLogger(__name__)

DRONE_ID = 5


class DroneLogic:
    def __init__(self):
        self.stm = None
        self.mqtt = get_publisher()

        self.battery = 100
        self.is_in_maintenance = False
        self.stm_state = "Idle"
        self.backend_status = "idle"
        self.current_order_id = None

        self.mqtt.register_command_callback(self.handle_command)

        self.sense = SenseController() if _SENSE_AVAILABLE else None
        if self.sense:
            self.sense.start_joystick_listener(self._on_joystick)

    def handle_command(self, action: str, data: dict):
        """
        Dispatch an incoming MQTT command to the appropriate handler or STM trigger.
        Called by MQTTPublisher whenever a message arrives on the command topic.
        Recognised actions: 'get_status', 'fetch_order', 'charge'.
        """
        logger.info(f"[drone_{DRONE_ID}] Command: {action}")
        if action == "get_status":
            if self.sense:
                threading.Thread(
                    target=self.sense.show_status_ping,
                    args=({"status": self.backend_status, "battery": self.battery},
                          self._restore_display),
                    daemon=True
                ).start()
            self.send_status()
        elif action == "fetch_order":
            self._handle_fetch_order(data)
        elif action == "charge":
            if self.stm:
                self.stm.send("battery_low")

    def _handle_fetch_order(self, data: dict):
        self.current_order_id = data.get("oid")
        logger.info(f"[drone_{DRONE_ID}] Fetch order #{self.current_order_id}: {data.get('address')}")
        if self.stm:
            self.stm.send("order_assigned")

    def _on_joystick(self, direction: str):
        """
        Map a joystick press to an STM trigger based on the current state.
        Middle button advances the active workflow step; left reports a crash
        or completes maintenance; right confirms charging done.
        """
        if not self.stm:
            return

        if direction == 'middle':
            trigger_map = {
                'LoadPackage':      'package_secured',
                'InRouteToDropoff': 'Reached_destination',
                'Delivering':       'delivery_done',
                'ReturnToBase':     'returned',
            }
            if self.stm_state in trigger_map:
                trigger = trigger_map[self.stm_state]
                logger.info(f"[drone_{DRONE_ID}] Joystick middle in {self.stm_state} → {trigger}")
                self.stm.send(trigger)

        elif direction == 'left':
            if self.stm_state in ('InRouteToDropoff', 'ReturnToBase'):
                logger.warning(f"[drone_{DRONE_ID}] Crash reported in {self.stm_state}!")
                self.stm.send("crashed")
            elif self.stm_state == 'Maintenance':
                logger.info(f"[drone_{DRONE_ID}] Maintenance complete")
                self.stm.send("drone_fixed")

        elif direction == 'right':
            if self.stm_state == 'Charging':
                logger.info(f"[drone_{DRONE_ID}] Charging complete")
                self.stm.send("charged")

    def _restore_display(self):
        if not self.sense:
            return
        if self.stm_state == "Idle":
            self.sense.show_idle()
        elif self.stm_state == "Charging":
            self.sense.show_charging()
        elif self.stm_state == "Maintenance":
            self.sense.show_maintenance()

    def send_status(self):
        logger.info(
            f"[drone_{DRONE_ID}] Status: {self.backend_status}, "
            f"battery={self.battery}%, maintenance={self.is_in_maintenance}"
        )
        self.mqtt.publish_status(self.backend_status, self.battery, self.is_in_maintenance)

    def turn_off(self):
        self.stm_state = "Idle"
        self.backend_status = "idle"
        logger.info(f"[drone_{DRONE_ID}] Idle — systems powered down")
        if self.sense:
            self.sense.show_idle()

    def charge(self):
        self.stm_state = "Charging"
        self.backend_status = "charging"
        logger.info(f"[drone_{DRONE_ID}] Charging — press joystick right when done")
        self.mqtt.publish_status("charging", self.battery, self.is_in_maintenance)
        if self.sense:
            self.sense.show_charging()

    def complete_charging(self):
        self.battery = 100
        logger.info(f"[drone_{DRONE_ID}] Charging complete")
        self.mqtt.publish_status("charging_complete", self.battery, self.is_in_maintenance)

    def fix(self):
        self.stm_state = "Maintenance"
        self.backend_status = "maintenance"
        self.is_in_maintenance = True
        logger.info(f"[drone_{DRONE_ID}] In maintenance")
        if self.sense:
            self.sense.stop_spinning()
            self.sense.stop_dropping()
            self.sense.stop_picking()
            self.sense.show_maintenance()
        self.mqtt.publish_status("maintenance", self.battery, self.is_in_maintenance)

    def complete_maintenance(self):
        self.is_in_maintenance = False
        logger.info(f"[drone_{DRONE_ID}] Maintenance complete — returning to idle")
        self.mqtt.publish_status("maintenance_complete", self.battery, False)

    def alert_logistics(self):
        logger.warning(f"[drone_{DRONE_ID}] ALERT: logistics notified")
        self.mqtt.publish_status("damaged", self.battery, self.is_in_maintenance,
                                 self.current_order_id)

    def run_preflight(self):
        """
        Begin pre-flight checks. Fires 'checks_passed' automatically after 1.5 s
        because no physical sensor validation is implemented; the delay simulates
        a real check cycle.
        """
        self.stm_state = "PreFlightChecks"
        self.backend_status = "preflight"
        logger.info(f"[drone_{DRONE_ID}] Running pre-flight checks...")
        threading.Timer(
            1.5,
            lambda: self.stm.send("checks_passed") if self.stm else None
        ).start()

    def load_package(self):
        self.stm_state = "LoadPackage"
        self.backend_status = "loading"
        logger.info(f"[drone_{DRONE_ID}] Loading package...")
        if self.sense:
            self.sense.start_picking()

    def flyToDropoff(self):
        self.stm_state = "InRouteToDropoff"
        self.backend_status = "in_transit"
        logger.info(f"[drone_{DRONE_ID}] Flying to dropoff — press joystick on arrival")
        self.mqtt.publish_status("in_transit", self.battery, self.is_in_maintenance,
                                 self.current_order_id)
        if self.sense:
            self.sense.stop_picking()
            self.sense.start_spinning()

    def send_location(self):
        pass

    def return_to_base(self):
        self.stm_state = "ReturnToBase"
        self.backend_status = "returning"
        logger.info(f"[drone_{DRONE_ID}] Returning to base — press joystick when landed")
        if self.sense:
            self.sense.stop_dropping()
            self.sense.start_spinning()

    def land(self):
        logger.info(f"[drone_{DRONE_ID}] Landed at base")
        if self.sense:
            self.sense.stop_spinning()

    def takeoff(self):
        logger.info(f"[drone_{DRONE_ID}] Takeoff!")

    def deliver_package(self):
        self.stm_state = "Delivering"
        self.backend_status = "delivering"
        logger.info(f"[drone_{DRONE_ID}] Delivering — press joystick when done to return")
        self.mqtt.publish_status("delivery_complete", self.battery, self.is_in_maintenance,
                                 self.current_order_id)
        if self.sense:
            self.sense.stop_spinning()
            self.sense.start_dropping()
