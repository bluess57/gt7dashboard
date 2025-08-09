import datetime
import logging
import socket
import struct
import time
import copy
from threading import Thread
from bokeh.io import curdoc

from gt7dashboard.gt7helper import seconds_to_lap_time
from gt7dashboard.gt7lap import Lap
from gt7dashboard.gt7data import GT7Data
from gt7dashboard.gt7session import GT7Session
from gt7dashboard.gt7salsa import salsa20_dec

# Set up logging
logger = logging.getLogger("gt7communication.py")
logger.setLevel(logging.DEBUG)


class GT7Communication(Thread):
    def __init__(self, playstation_ip):
        # Thread control
        Thread.__init__(self)
        self._shall_run = True
        self._shall_restart = False
        # True will always quit with the main process
        self.daemon = True
        self._on_heartbeat_callback = None
        # Set lap callback function as none
        self.lap_callback_function = None

        self._on_reset_callback = None

        self.playstation_ip = playstation_ip
        self.send_port = 33739
        self.receive_port = 33740
        self._last_time_data_received = 0

        self.current_lap = Lap()
        self.session = GT7Session()
        self.last_data = GT7Data(None)

        # This is used to record race data in any case. This will override the "in_race" flag.
        # When recording data. Useful when recording replays.
        self.always_record_data = True

    def set_on_connected_callback(self, callback):
        """Register a callback to be called when connection is established."""
        self._on_connected_callback = callback

    def _check_connection_event(self):
        connected = self.is_connected()
        if connected and not self._was_connected:
            if self._on_connected_callback:
               self._on_connected_callback()
        self._was_connected = connected

    def stop(self):
        self._shall_run = False
        # Give the thread time to clean up
        if self.is_alive():
            self.join(timeout=2)

    def run(self):
        while self._shall_run:
            s = None
            try:
                self._shall_restart = False
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                # Add socket reuse option
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

                if self.playstation_ip == "255.255.255.255":
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

                s.bind(("0.0.0.0", self.receive_port))
                self._send_hb(s)
                s.settimeout(10)
                previous_lap = -1
                package_id = 0
                package_nr = 0
                self._check_connection_event()
                while not self._shall_restart and self._shall_run:
                    try:
                        data,address = s.recvfrom(4096)
                        package_nr = package_nr + 1
                        ddata = salsa20_dec(data)
                        if (
                            len(ddata) > 0
                            and struct.unpack("i", ddata[0x70 : 0x70 + 4])[0]
                            > package_id
                        ):

                            self.last_data = GT7Data(ddata)
                            self._last_time_data_received = time.time()

                            package_id = self.last_data.package_id
                            bstlap = self.last_data.best_lap
                            lstlap = self.last_data.last_lap
                            curlap = self.last_data.current_lap

                            if curlap == 0:
                                self.session.special_packet_time = 0

                            if curlap > 0 and (
                                self.last_data.in_race or self.always_record_data
                            ):

                                if curlap != previous_lap:
                                    # New lap
                                    previous_lap = curlap

                                    self.session.special_packet_time += (
                                        lstlap
                                        - self.current_lap.lap_ticks * 1000.0 / 60.0
                                    )
                                    self.session.best_lap = bstlap

                                    self.finish_lap()

                            else:
                                # Reset lap
                                self.current_lap = Lap()

                            self._log_data(self.last_data)

                            if package_nr > 100:
                                self._send_hb(s)
                                package_nr = 0
                                self._check_connection_event()

                    except (OSError, TimeoutError) as e:
                        package_nr = 0
                        # Reset package id for new connections
                        package_id = 0
                        # Handler for package exceptions
                        self._send_hb(s)

            except Exception as e:
                # Handler for general socket exceptions
                logger.error(
                    "Error while connecting to %s:%d: %s"
                    % (self.playstation_ip, self.send_port, e)
                )
                s.close()
                # Wait before reconnect
                time.sleep(5)

            finally:
                if s:
                    try:
                        s.close()
                    except:
                        pass

    def restart(self):
        self._shall_restart = True
        self._shall_run = True

    def is_connected(self) -> bool:
        return (
            self._last_time_data_received > 0
            and (time.time() - self._last_time_data_received) <= 1
        )

    def set_on_heartbeat_callback(self, callback):
        """Register a callback to be called when a heartbeat is sent."""
        self._on_heartbeat_callback = callback

    def _send_hb(self, s):
        send_data = "A"
        s.sendto(send_data.encode("utf-8"), (self.playstation_ip, self.send_port))
        # Raise the heartbeat event for consumers
        if self._on_heartbeat_callback:
           self._on_heartbeat_callback()

    def get_last_data(self) -> GT7Data:
        timeout = time.time() + 5  # 5 seconds timeout
        while True:
            if self.last_data is not None:
                return self.last_data

            if time.time() > timeout:
                break

    def _log_data(self, data):
        if not (data.in_race or self.always_record_data):
            return

        if data.is_paused:
            return

        if data.ride_height < self.session.min_body_height:
            self.session.min_body_height = data.ride_height

        if data.car_speed > self.session.max_speed:
            self.session.max_speed = data.car_speed

        if data.throttle == 100:
            self.current_lap.full_throttle_ticks += 1

        if data.brake == 100:
            self.current_lap.full_brake_ticks += 1

        if data.brake == 0 and data.throttle == 0:
            self.current_lap.no_throttle_and_no_brake_ticks += 1
            self.current_lap.data_coasting.append(1)
        else:
            self.current_lap.data_coasting.append(0)

        if data.brake > 0 and data.throttle > 0:
            self.current_lap.throttle_and_brake_ticks += 1

        self.current_lap.lap_ticks += 1

        if (
            data.tyre_temp_FL > 100
            or data.tyre_temp_FR > 100
            or data.tyre_temp_RL > 100
            or data.tyre_temp_RR > 100
        ):
            self.current_lap.tyres_overheated_ticks += 1

        self.current_lap.data_braking.append(data.brake)
        self.current_lap.data_throttle.append(data.throttle)
        self.current_lap.data_speed.append(data.car_speed)

        delta_divisor = data.car_speed
        if data.car_speed == 0:
            delta_divisor = 1

        delta_fl = data.type_speed_FL / delta_divisor
        delta_fr = data.type_speed_FR / delta_divisor
        delta_rl = data.type_speed_RL / delta_divisor
        delta_rr = data.type_speed_FR / delta_divisor

        if delta_fl > 1.1 or delta_fr > 1.1 or delta_rl > 1.1 or delta_rr > 1.1:
            self.current_lap.tyres_spinning_ticks += 1

        self.current_lap.data_tyres.append(delta_fl + delta_fr + delta_rl + delta_rr)

        ## RPM and shifting

        self.current_lap.data_rpm.append(data.rpm)
        self.current_lap.data_gear.append(data.current_gear)

        ## Log Position

        self.current_lap.data_position_x.append(data.position_x)
        self.current_lap.data_position_y.append(data.position_y)
        self.current_lap.data_position_z.append(data.position_z)

        ## Log Boost

        self.current_lap.data_boost.append(data.boost)

        ## Log Yaw Rate

        # This is the interval to collection yaw rate
        interval = 1 * 60  # 1 second has 60 fps and 60 data ticks
        self.current_lap.data_rotation_yaw.append(data.rotation_yaw)

        # Collect yaw rate, skip first interval with all zeroes
        if len(self.current_lap.data_rotation_yaw) > interval:
            yaw_rate_per_second = (
                data.rotation_yaw - self.current_lap.data_rotation_yaw[-interval]
            )
        else:
            yaw_rate_per_second = 0

        self.current_lap.data_absolute_yaw_rate_per_second.append(
            abs(yaw_rate_per_second)
        )

        # Adapted from https://www.gtplanet.net/forum/threads/gt7-is-compatible-with-motion-rig.410728/post-13810797
        self.current_lap.lap_live_time = (self.current_lap.lap_ticks * 1.0 / 60.0) - (
            self.session.special_packet_time / 1000.0
        )

        self.current_lap.data_time.append(self.current_lap.lap_live_time)

        self.current_lap.car_id = data.car_id

    def finish_lap(self, manual=False):
        """
        Finishes a lap with info we only know after crossing the line after each lap
        """
        logger.debug("Finishing lap %d with manual=%s", self.last_data.current_lap, manual)

        if manual:
            # Manual laps have no time assigned, so take current live time as lap finish time.
            # Finish time is tracked in seconds while live time is tracked in ms
            self.current_lap.lap_finish_time = self.current_lap.lap_live_time * 1000
        else:
            # Regular finished laps (crossing the finish line in races or time trials)
            # have their lap time stored in last_lap
            self.current_lap.lap_finish_time = self.last_data.last_lap

        # Track recording meta data
        self.current_lap.is_replay = self.always_record_data
        self.current_lap.is_manual = manual

        self.current_lap.fuel_at_end = self.last_data.current_fuel
        self.current_lap.fuel_consumed = (
            self.current_lap.fuel_at_start - self.current_lap.fuel_at_end
        )
        self.current_lap.lap_finish_time = self.current_lap.lap_finish_time
        self.current_lap.total_laps = self.last_data.total_laps
        self.current_lap.title = seconds_to_lap_time(
            self.current_lap.lap_finish_time / 1000
        )
        self.current_lap.car_id = self.last_data.car_id
        self.current_lap.number = (
            self.last_data.current_lap - 1
        )  # Is not counting the same way as the in-game timetable
        self.current_lap.EstimatedTopSpeed = self.last_data.estimated_top_speed

        self.current_lap.lap_end_timestamp = datetime.datetime.now()

        # Race is not in 0th lap, which is before starting the race.
        # We will only persist those laps that have crossed the starting line at least once
        # And those laps which have data for speed logged. This will prevent empty laps.
        if (
            self.current_lap.lap_finish_time > 0
            and len(self.current_lap.data_speed) > 0
        ):
            self.session.add_lap(self.current_lap)

            # Make a copy of this lap and call the callback function if set
            if self.lap_callback_function:
               curdoc().add_next_tick_callback(self.lap_callback_function(copy.deepcopy(self.current_lap)))

        # Reset current lap with an empty one
        self.current_lap = Lap()
        self.current_lap.fuel_at_start = self.last_data.current_fuel

    def reset(self):
        """
        Resets the current lap, all stored laps and the current session.
        """
        self.current_lap = Lap()
        self.session.reset()
        self.last_data = GT7Data(None)
        if self._on_reset_callback:
           curdoc().add_next_tick_callback(self._on_reset_callback)

    def set_reset_callback(self, new_reset_callback):
        self._on_reset_callback = new_reset_callback

    def set_lap_callback(self, new_lap_callback):
        self.lap_callback_function = new_lap_callback
