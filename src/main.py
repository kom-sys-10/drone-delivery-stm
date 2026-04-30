"""Production entry point. Wires DroneLogic into a stmpy state machine and blocks until keyboard interrupt."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
import time
from stmpy import Driver, Machine
from src.stm.drone_states import get_drone_states, get_drone_transitions
from src.logic.drone_logic import DroneLogic, DRONE_ID

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    logic = DroneLogic()
    machine = Machine(
        name=str(DRONE_ID),
        transitions=get_drone_transitions(),
        states=get_drone_states(),
        obj=logic,
    )
    logic.stm = machine

    driver = Driver()
    driver.add_machine(machine)
    driver.start()

    logger.info(f"Drone {DRONE_ID} running — waiting for backend commands")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        driver.stop()


if __name__ == "__main__":
    main()
