"""
State machine definition for the drone delivery system. Defines all stmpy
transition dicts and state dicts, then exposes them via get_drone_transitions()
and get_drone_states().

State topology:
  Idle
    → Charging          (battery_low)
    → PreFlightChecks   (order_assigned)
  Charging
    → Idle              (charged)
  PreFlightChecks
    → LoadPackage       (checks_passed)
    → Maintenance       (checks_failed)
  LoadPackage
    → InRouteToDropoff  (package_secured)
  InRouteToDropoff
    → Delivering        (Reached_destination)
    → RunDiagnostics    (warning)
    → Maintenance       (crashed)
  RunDiagnostics
    → InRouteToDropoff  (passed_safety_test)
    → ReturnToBase      (failed_safety_test)
  Delivering
    → ReturnToBase      (delivery_done)
  ReturnToBase
    → Idle              (returned)
    → EmergencyLanding  (return_failed)
    → Maintenance       (crashed)
  EmergencyLanding
    → Maintenance       (drone_collected)
  Maintenance
    → Idle              (drone_fixed)
"""

t_init = {
    'source': 'initial',
    'target': 'Idle'
}

t_battery_low = {
    'trigger': 'battery_low',
    'source':  'Idle',
    'target':  'Charging'
}

t_charged = {
    'trigger': 'charged',
    'source':  'Charging',
    'target':  'Idle',
    'effect':  'complete_charging'
}

t_order_assigned = {
    'trigger': 'order_assigned',
    'source':  'Idle',
    'target':  'PreFlightChecks'
}

t_checks_passed = {
    'trigger': 'checks_passed',
    'source':  'PreFlightChecks',
    'target':  'LoadPackage'
}

t_checks_failed = {
    'trigger': 'checks_failed',
    'source':  'PreFlightChecks',
    'target':  'Maintenance'
}

t_drone_fixed = {
    'trigger': 'drone_fixed',
    'source':  'Maintenance',
    'target':  'Idle',
    'effect':  'complete_maintenance'
}

t_crashed_in_route = {
    'trigger': 'crashed',
    'source':  'InRouteToDropoff',
    'target':  'Maintenance'
}

t_crashed_returning = {
    'trigger': 'crashed',
    'source':  'ReturnToBase',
    'target':  'Maintenance'
}

t_package_secured = {
    'trigger': 'package_secured',
    'source':  'LoadPackage',
    'target':  'InRouteToDropoff',
    'effect':  'takeoff'
}

t_reached_destination = {
    'trigger': 'Reached_destination',
    'source':  'InRouteToDropoff',
    'target':  'Delivering'
}

t_delivery_done = {
    'trigger': 'delivery_done',
    'source':  'Delivering',
    'target':  'ReturnToBase'
}

t_warning = {
    'trigger': 'warning',
    'source':  'InRouteToDropoff',
    'target':  'RunDiagnostics'
}

t_passed_safety = {
    'trigger': 'passed_safety_test',
    'source':  'RunDiagnostics',
    'target':  'InRouteToDropoff'
}

t_failed_safety = {
    'trigger': 'failed_safety_test',
    'source':  'RunDiagnostics',
    'target':  'ReturnToBase',
    'effect':  'alert_logistics'
}

t_returned = {
    'trigger': 'returned',
    'source':  'ReturnToBase',
    'target':  'Idle'
}

t_return_failed = {
    'trigger': 'return_failed',
    'source':  'ReturnToBase',
    'target':  'EmergencyLanding'
}

t_drone_collected = {
    'trigger': 'drone_collected',
    'source':  'EmergencyLanding',
    'target':  'Maintenance'
}


s_idle = {
    'name':  'Idle',
    'entry': 'turn_off'
}

s_charging = {
    'name':  'Charging',
    'entry': 'charge'
}

s_maintenance = {
    'name':  'Maintenance',
    'entry': 'fix; alert_logistics'
}

s_load_package = {
    'name':  'LoadPackage',
    'entry': 'load_package'
}

s_in_route = {
    'name':  'InRouteToDropoff',
    'entry': 'flyToDropoff; send_location'
}

s_return_to_base = {
    'name':  'ReturnToBase',
    'entry': 'return_to_base',
    'exit':  'land'
}

s_emergency = {
    'name':  'EmergencyLanding',
    'entry': 'alert_logistics'
}

s_preflight = {'name': 'PreFlightChecks', 'entry': 'run_preflight'}

s_diagnostics = {'name': 'RunDiagnostics'}

s_delivering = {'name': 'Delivering', 'entry': 'deliver_package'}


def get_drone_transitions():
    return [
        t_init, t_battery_low, t_charged,
        t_order_assigned, t_checks_passed, t_checks_failed,
        t_drone_fixed, t_package_secured, t_reached_destination,
        t_delivery_done, t_crashed_in_route, t_crashed_returning,
        t_warning, t_passed_safety, t_failed_safety,
        t_returned, t_return_failed, t_drone_collected
    ]


def get_drone_states():
    return [
        s_idle, s_charging, s_maintenance,
        s_load_package, s_in_route, s_return_to_base,
        s_emergency, s_preflight, s_diagnostics, s_delivering
    ]
