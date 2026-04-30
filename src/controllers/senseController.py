"""
Controls the Raspberry Pi Sense HAT LED matrix and joystick for the drone.
Each drone state maps to a display: spinning blades when in flight, pickup/dropoff
animations when loading or delivering, static icons for idle, charging, and
maintenance states. All animations run in background daemon threads so they
never block the STM.
"""

from sense_hat import SenseHat
import time
import threading


class SenseController:
    def __init__(self):
        self.sense = SenseHat()
        self.sense.low_light = False
        self._stop_spin = threading.Event()
        self._spin_thread = None
        self._stop_pick = threading.Event()
        self._pick_thread = None
        self._stop_drop = threading.Event()
        self._drop_thread = None
        self._stop_joystick = threading.Event()
        self._joystick_thread = None

    def disconnect(self):
        self.stop_joystick_listener()
        self.sense.clear()

    def _spin_loop(self, speed: float):
        """
        Animate rotating propeller blades on the 8×8 LED grid until
        self._stop_spin is set.

        Grid layout:
          P . . . . . . P    P = propeller hub (corners)
          . \\ . . . . / .    arms connect diagonally to body
          . . . . . . . .
          . . . B B . . .    B = drone body (2×2 centre)
          . . . B B . . .
          . . . . . . . .
          . / . . . . \\ .
          P . . . . . . P

        Each propeller cycles through 4 blade phases (—, \\, |, /).
        A dimmed trail pixel one phase behind simulates motion blur.
        """
        W  = (255, 255, 255)
        DW = (60,  60,  60)
        Y  = (255, 200,  0)
        A  = (80,  80,  80)

        prop_phases = [
            [(-1,  0), ( 1,  0)],
            [(-1, -1), ( 1,  1)],
            [( 0, -1), ( 0,  1)],
            [( 1, -1), (-1,  1)],
        ]
        prop_centers = [(1, 1), (6, 1), (1, 6), (6, 6)]
        body_pixels  = [(3, 3), (4, 3), (3, 4), (4, 4)]
        arm_pixels   = [(2, 2), (5, 2), (2, 5), (5, 5)]

        phase = 0
        while not self._stop_spin.is_set():
            grid = [(0, 0, 0)] * 64
            for x, y in body_pixels:
                grid[y * 8 + x] = Y
            for x, y in arm_pixels:
                grid[y * 8 + x] = A
            curr_offsets = prop_phases[phase % 4]
            prev_offsets = prop_phases[(phase - 1) % 4]
            for cx, cy in prop_centers:
                grid[cy * 8 + cx] = W
                for dx, dy in prev_offsets:
                    nx, ny = cx + dx, cy + dy
                    if 0 <= nx < 8 and 0 <= ny < 8:
                        grid[ny * 8 + nx] = DW
                for dx, dy in curr_offsets:
                    nx, ny = cx + dx, cy + dy
                    if 0 <= nx < 8 and 0 <= ny < 8:
                        grid[ny * 8 + nx] = W
            self.sense.set_pixels(grid)
            phase += 1
            time.sleep(speed)

        self.sense.clear()

    def spin_blades(self, duration: float = 5.0, speed: float = 0.08):
        self._stop_spin.clear()
        threading.Timer(duration, self._stop_spin.set).start()
        self._spin_loop(speed)

    def start_spinning(self, speed: float = 0.08):
        self.stop_spinning()
        self._stop_spin.clear()
        self._spin_thread = threading.Thread(target=self._spin_loop, args=(speed,), daemon=True)
        self._spin_thread.start()

    def stop_spinning(self):
        self._stop_spin.set()
        if self._spin_thread and self._spin_thread.is_alive():
            self._spin_thread.join(timeout=1.0)
        self._spin_thread = None

    def start_picking(self):
        self.stop_picking()
        self._stop_pick.clear()
        self._pick_thread = threading.Thread(target=self._pick_loop, daemon=True)
        self._pick_thread.start()

    def _pick_loop(self):
        while not self._stop_pick.is_set():
            self.show_pickup()

    def stop_picking(self):
        self._stop_pick.set()
        if self._pick_thread and self._pick_thread.is_alive():
            self._pick_thread.join(timeout=5.0)
        self._pick_thread = None

    def start_dropping(self):
        self.stop_dropping()
        self._stop_drop.clear()
        self._drop_thread = threading.Thread(target=self._drop_loop, daemon=True)
        self._drop_thread.start()

    def _drop_loop(self):
        while not self._stop_drop.is_set():
            self.show_dropoff()

    def stop_dropping(self):
        self._stop_drop.set()
        if self._drop_thread and self._drop_thread.is_alive():
            self._drop_thread.join(timeout=5.0)
        self._drop_thread = None

    def show_pickup(self):
        O  = (0,   0,   0)
        DR = (0, 120, 255)
        PK = (255, 140,  0)
        W  = (200, 200, 200)
        G  = (0,  255,  0)

        drone_px = [(3, 0), (4, 0), (3, 1), (4, 1)]

        package_px = [
            (1,5),(2,5),(3,5),(4,5),(5,5),(6,5),
            (1,6),                        (6,6),
            (1,7),(2,7),(3,7),(4,7),(5,7),(6,7),
        ]

        arrow_shaft = [(3,2),(4,2),(3,3),(4,3)]
        arrow_head  = [(2,4),(3,4),(4,4),(5,4),(3,5),(4,5)]

        def _base_grid():
            grid = [O] * 64
            for x, y in drone_px:
                grid[y * 8 + x] = DR
            for x, y in package_px:
                grid[y * 8 + x] = PK
            return grid

        self.sense.set_pixels(_base_grid())
        time.sleep(0.6)

        for _ in range(3):
            grid = _base_grid()
            for x, y in arrow_shaft + arrow_head:
                grid[y * 8 + x] = W
            self.sense.set_pixels(grid)
            time.sleep(0.25)
            self.sense.set_pixels(_base_grid())
            time.sleep(0.15)

        for _ in range(2):
            self.sense.clear(PK)
            time.sleep(0.15)
            self.sense.clear()
            time.sleep(0.1)

        for offset in range(1, 6):
            grid = [O] * 64
            for x, y in drone_px:
                grid[y * 8 + x] = DR
            for x, y in package_px:
                ny = y - offset
                if 0 <= ny < 8:
                    grid[ny * 8 + x] = PK
            self.sense.set_pixels(grid)
            time.sleep(0.12)

        for _ in range(3):
            self.sense.clear(G)
            time.sleep(0.2)
            self.sense.clear()
            time.sleep(0.15)

        self.sense.clear()

    def show_dropoff(self):
        O  = (0,   0,   0)
        DR = (0, 120, 255)
        PK = (255, 140,  0)
        W  = (200, 200, 200)
        B  = (0,  180, 255)

        drone_px = [(3, 0), (4, 0), (3, 1), (4, 1)]

        package_start = [
            (1,2),(2,2),(3,2),(4,2),(5,2),(6,2),
            (1,3),                        (6,3),
            (1,4),(2,4),(3,4),(4,4),(5,4),(6,4),
        ]

        arrow_head  = [(3,2),(4,2),(2,3),(3,3),(4,3),(5,3)]
        arrow_shaft = [(3,4),(4,4),(3,5),(4,5)]

        grid = [O] * 64
        for x, y in drone_px:
            grid[y * 8 + x] = DR
        for x, y in package_start:
            grid[y * 8 + x] = PK
        self.sense.set_pixels(grid)
        time.sleep(0.6)

        for offset in range(1, 4):
            grid = [O] * 64
            for x, y in drone_px:
                grid[y * 8 + x] = DR
            for x, y in package_start:
                ny = y + offset
                if 0 <= ny < 8:
                    grid[ny * 8 + x] = PK
            self.sense.set_pixels(grid)
            time.sleep(0.18)

        for _ in range(2):
            self.sense.clear((220, 220, 220))
            time.sleep(0.15)
            self.sense.clear()
            time.sleep(0.1)

        for _ in range(3):
            grid = [O] * 64
            for x, y in drone_px:
                grid[y * 8 + x] = DR
            for x, y in arrow_head + arrow_shaft:
                grid[y * 8 + x] = W
            self.sense.set_pixels(grid)
            time.sleep(0.25)
            grid2 = [O] * 64
            for x, y in drone_px:
                grid2[y * 8 + x] = DR
            self.sense.set_pixels(grid2)
            time.sleep(0.15)

        for _ in range(3):
            self.sense.clear(B)
            time.sleep(0.2)
            self.sense.clear()
            time.sleep(0.15)

        self.sense.clear()

    def start_joystick_listener(self, on_press):
        """
        Start a background thread that polls for Sense HAT joystick events and
        calls on_press(direction) on each initial press. direction is one of
        'up', 'down', 'left', 'right', 'middle'. Hold and release events are ignored.
        """
        self.stop_joystick_listener()
        self._stop_joystick.clear()
        self._joystick_thread = threading.Thread(
            target=self._joystick_loop, args=(on_press,), daemon=True
        )
        self._joystick_thread.start()

    def stop_joystick_listener(self):
        self._stop_joystick.set()
        if self._joystick_thread and self._joystick_thread.is_alive():
            self._joystick_thread.join(timeout=1.0)
        self._joystick_thread = None

    def _joystick_loop(self, on_press):
        while not self._stop_joystick.is_set():
            for event in self.sense.stick.get_events():
                if event.action == 'pressed':
                    on_press(event.direction)
            time.sleep(0.05)

    def show_charging(self):
        G = (  0, 200,  50)
        Y = (255, 220,   0)
        K = (  0,   0,   0)

        terminal   = [(3, 0), (4, 0)]
        top_wall   = [(1, 1), (2, 1), (3, 1), (4, 1), (5, 1), (6, 1)]
        bot_wall   = [(1, 6), (2, 6), (3, 6), (4, 6), (5, 6), (6, 6)]
        left_wall  = [(1, 2), (1, 3), (1, 4), (1, 5)]
        right_wall = [(6, 2), (6, 3), (6, 4), (6, 5)]
        bolt       = [(4, 2), (3, 3), (4, 3), (2, 4), (3, 4), (3, 5)]

        grid = [K] * 64
        for x, y in terminal + top_wall + bot_wall + left_wall + right_wall:
            grid[y * 8 + x] = G
        for x, y in bolt:
            grid[y * 8 + x] = Y
        self.sense.set_pixels(grid)

    def show_maintenance(self):
        O = (255, 100,   0)
        K = (  0,   0,   0)

        body = [
            (3, 1), (4, 1),
            (3, 2), (4, 2),
            (3, 3), (4, 3),
            (3, 4), (4, 4),
        ]
        dot = [
            (3, 6), (4, 6),
        ]

        grid = [K] * 64
        for x, y in body + dot:
            grid[y * 8 + x] = O
        self.sense.set_pixels(grid)

    def show_idle(self):
        W = (255, 255, 255)
        Y = (255, 200,   0)
        A = ( 80,  80,  80)
        O = (  0,   0,   0)

        prop_centers  = [(1, 1), (6, 1), (1, 6), (6, 6)]
        body_pixels   = [(3, 3), (4, 3), (3, 4), (4, 4)]
        arm_pixels    = [(2, 2), (5, 2), (2, 5), (5, 5)]
        blade_offsets = [(-1, 0), (1, 0)]

        grid = [O] * 64
        for x, y in body_pixels:
            grid[y * 8 + x] = Y
        for x, y in arm_pixels:
            grid[y * 8 + x] = A
        for cx, cy in prop_centers:
            grid[cy * 8 + cx] = W
            for dx, dy in blade_offsets:
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < 8 and 0 <= ny < 8:
                    grid[ny * 8 + nx] = W
        self.sense.set_pixels(grid)

    def show_status_ping(self, status_data: dict, on_complete=None):
        """
        Scroll a status summary on the LED matrix when the backend requests a
        status ping. Calls on_complete() after the scroll finishes so the caller
        can restore the previous display.
        """
        status = status_data.get("status", "?")
        battery = status_data.get("battery", "?")
        message = f"D5 {status} {battery}%"
        self.sense.show_message(
            message,
            text_colour=(0, 180, 255),
            back_colour=(0, 0, 0),
            scroll_speed=0.07,
        )
        self.sense.clear()
        if on_complete:
            on_complete()
        else:
            self.show_idle()

    def set_low_light(self, enabled: bool):
        self.sense.low_light = enabled

    def set_rotation(self, degrees: int):
        self.sense.set_rotation(degrees)
