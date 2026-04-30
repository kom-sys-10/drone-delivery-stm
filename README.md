# Drone Delivery System

A Raspberry Pi–based drone delivery controller. The drone runs a state machine that manages the full delivery lifecycle — from receiving an order to returning to base — and communicates with a backend over MQTT. A Sense HAT provides LED matrix animations and joystick input for physical control.

## Hardware

- Raspberry Pi (any model with a GPIO header)
- [Raspberry Pi Sense HAT](https://www.raspberrypi.com/products/sense-hat/)

## State Machine

The drone moves through the following states, driven by MQTT commands and joystick input:

```
Idle → PreFlightChecks → LoadPackage → InRouteToDropoff → Delivering → ReturnToBase → Idle
                                              ↓
                                       RunDiagnostics
                                              ↓
                                       (Maintenance / ReturnToBase)
```

Special states: `Charging`, `Maintenance`, `EmergencyLanding`.

## MQTT

| Direction | Topic | Purpose |
|-----------|-------|---------|
| Subscribe | `drones/<id>/command` | Receive commands from backend |
| Publish   | `drones/<id>/status`  | Report state to backend |

**Incoming command shape:**
```json
{ "action": "fetch_order", "data": { "oid": 42, "address": "..." } }
```

Supported actions: `fetch_order`, `get_status`, `charge`.

## Joystick Controls

| Direction | Effect |
|-----------|--------|
| Middle | Advance current state (package secured / arrived / delivery done / landed) |
| Left | Report crash (in flight or returning) — or confirm maintenance complete |
| Right | Confirm charging done |

## Setup

### 1. Install the Sense HAT system package

```bash
sudo apt update
sudo apt install sense-hat
```

### 2. Create a Python virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Python dependencies

```bash
pip install -r src/requirements.txt
```

## Running

Run from the project root directory:

```bash
python src/main.py
```

The drone will connect to the MQTT broker and wait for commands. Press `Ctrl+C` to shut down cleanly.

## Project Structure

```
src/
├── main.py                    # Entry point
├── logic/
│   └── drone_logic.py         # State machine actions and MQTT/joystick handling
├── stm/
│   └── drone_states.py        # State machine definition (states and transitions)
├── mqtt/
│   └── publisher.py           # MQTT client (singleton)
├── controllers/
│   └── senseController.py     # Sense HAT LED animations and joystick listener
└── requirements.txt
```

## Configuration

The MQTT broker address and drone ID are currently hardcoded:

| Setting | Location | Default |
|---------|----------|---------|
| Broker host | `src/mqtt/publisher.py` | `16.171.145.191` |
| Drone ID | `src/logic/drone_logic.py` | `5` |
