import datetime
import logging
import socket
import struct
import time
import copy
import threading
from threading import Thread
from typing import Optional, Callable, Any

from gt7dashboard.gt7helper import seconds_to_lap_time
from gt7dashboard.gt7lap import Lap
from gt7dashboard.gt7data import GT7Data
from gt7dashboard.gt7session import GT7Session
from gt7dashboard.gt7salsa import salsa20_dec
from .gt7settings import get_log_level

# Set up logging
logger = logging.getLogger(__name__)
logger.setLevel(get_log_level())


class GT7Communication(Thread):
    def __init__(self, playstation_ip: str):
        # Validate parameter
        if not playstation_ip:
            raise ValueError("PlayStation IP address cannot be empty")

        # Validate IP format (basic check)
        if playstation_ip != "255.255.255.255":
            try:
                socket.inet_aton(playstation_ip)
            except socket.error:
                raise ValueError(f"Invalid IP address format: {playstation_ip}")

        # Thread control
        Thread.__init__(self, name="GT7CommunicationThread")
        self._shall_run = True
        self._shall_restart = False
        self._data_lock = threading.Lock()
        self._current_lap_lock = threading.Lock()
        self.exceptioncount = 0
        # True will always quit with the main process
        self.daemon = True

        self._on_heartbeat_callback = None
        self._on_lapfinish_callback = None
        self._on_reset_callback = None
        self._on_connected_callback = None

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

    def stop(self) -> None:
        """Enhanced stop method with better cleanup"""
        logger.info("Stopping GT7 Communication...")
        self._shall_run = False
        self._shall_restart = False

        # Give the thread time to clean up
        if self.is_alive():
            self.join(timeout=5)  # Increased timeout
            if self.is_alive():
                logger.warning("GT7 Communication thread did not stop gracefully")
            else:
                logger.info("GT7 Communication stopped successfully")

        # Clean up resources
        self._cleanup_resources()

    def _cleanup_resources(self) -> None:
        """Clean up all resources"""
        try:
            with self._current_lap_lock:
                self.current_lap = None

            with self._data_lock:
                self.last_data = None

            # Clear callbacks to prevent memory leaks
            self._on_lapfinish_callback = None
            self._on_heartbeat_callback = None
            self._on_connected_callback = None
            self._on_reset_callback = None

            logger.debug("GT7 Communication resources cleaned up")

        except Exception as e:
            logger.error(f"Error during resource cleanup: {e}")

    # Improved exception handling and resource management
    def run(self):
        """Main communication thread loop with improved error handling"""
        connection_attempts = 0
        max_consecutive_failures = 5
        base_retry_delay = 1  # Start with 1 second delay

        while self._shall_run:
            s = None
            try:
                self._shall_restart = False
                connection_attempts += 1

                logger.debug(f"Creating socket (attempt {connection_attempts})")
                s = self._create_socket()

                # Reset failure count on successful socket creation
                connection_attempts = 0
                base_retry_delay = 1

                # Run the main communication loop
                self._run_communication_loop(s)

            except ConnectionError as e:
                logger.error(f"Connection error: {e}")
                if not self._handle_connection_failure(
                    connection_attempts, base_retry_delay
                ):
                    break

            except socket.error as e:
                logger.error(f"Socket error: {e}")
                if not self._handle_socket_failure(
                    connection_attempts, base_retry_delay
                ):
                    break

            except Exception as e:
                logger.error(
                    f"Unexpected error in GT7Communication: {e}", exc_info=True
                )
                if not self._handle_general_failure(
                    connection_attempts, base_retry_delay
                ):
                    break

            finally:
                self._cleanup_socket(s)

            # Implement exponential backoff for repeated failures
            if connection_attempts >= max_consecutive_failures:
                logger.error(
                    f"Too many consecutive failures ({connection_attempts}), stopping"
                )
                break

            if connection_attempts > 0:
                retry_delay = min(
                    base_retry_delay * (2 ** (connection_attempts - 1)), 30
                )  # Max 30 seconds
                logger.info(
                    f"Waiting {retry_delay}s before retry (attempt {connection_attempts})"
                )
                time.sleep(retry_delay)

    def _create_socket(self) -> socket.socket:
        """Create and configure socket with proper error handling"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            if self.playstation_ip == "255.255.255.255":
                s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

            s.bind(("0.0.0.0", self.receive_port))
            s.settimeout(10)
            return s
        except OSError as e:
            logger.error(f"Failed to create socket: {e}")
            raise ConnectionError(f"Unable to bind to port {self.receive_port}") from e

    def _cleanup_socket(self, s: Optional[socket.socket]) -> None:
        """Safely cleanup socket resources"""
        if s:
            try:
                s.close()
            except Exception as e:
                logger.debug(f"Error closing socket: {e}")

    def _run_communication_loop(self, s: socket.socket) -> None:
        previous_lap = -1
        package_id = 0
        package_nr = 0
        self._check_connection_event()
        while not self._shall_restart and self._shall_run:
            try:
                data, address = s.recvfrom(4096)
                package_nr = package_nr + 1
                ddata = salsa20_dec(data)
                if (
                    len(ddata) > 0
                    and struct.unpack("i", ddata[0x70 : 0x70 + 4])[0] > package_id
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
                                lstlap - self.current_lap.lap_ticks * 1000.0 / 60.0
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

    def restart(self):
        self._shall_restart = True
        self._shall_run = True

    def set_on_heartbeat_callback(self, callback: Optional[Callable[[], None]]) -> None:
        """Register a callback to be called when a heartbeat is sent."""
        self._on_heartbeat_callback = callback

    def _send_hb(self, s: socket.socket) -> None:
        """Send heartbeat to PlayStation"""
        send_data = "A"
        s.sendto(send_data.encode("utf-8"), (self.playstation_ip, self.send_port))
        # Raise the heartbeat event for consumers
        if self._on_heartbeat_callback:
            self._on_heartbeat_callback()

    def is_connected(self) -> bool:
        """Check if currently connected to GT7"""
        return (
            self._last_time_data_received > 0
            and (time.time() - self._last_time_data_received) <= 1
        )

    def get_last_data(self) -> Optional[GT7Data]:
        """Get the last received GT7 data with timeout"""
        timeout = time.time() + 5  # 5 seconds timeout
        while True:
            with self._data_lock:
                if self.last_data is not None:
                    return copy.deepcopy(self.last_data)

            if time.time() > timeout:
                logger.warning("Timeout while waiting for last data")
                return None
            time.sleep(0.01)

    def set_on_lapfinish_callback(
        self, new_lap_callback: Optional[Callable[[Lap], None]]
    ) -> None:
        """Set callback function for lap completion"""
        self._on_lapfinish_callback = new_lap_callback

    def reset(self):
        """
        Resets the current lap, all stored laps and the current session.
        """
        self.current_lap = Lap()
        self.session.reset()
        self.last_data = GT7Data(None)
        if self._on_reset_callback:
            self._on_reset_callback()

    def set_on_reset_callback(self, new_reset_callback):
        self._on_reset_callback = new_reset_callback

    def _log_data(self, data: GT7Data) -> None:
        if data is None:
            logger.warning("Received None data, skipping log")
            return

        if not (data.in_race or self.always_record_data):
            return

        if data.is_paused:
            return

        # Validate critical data before processing
        if not self._validate_data(data):
            logger.warning("Invalid data received, skipping")
            return

        with self._current_lap_lock:
            self._process_lap_data(data)

    def _validate_data(self, data: GT7Data) -> bool:
        """Validate GT7 data before processing"""
        if data is None:
            return False

        try:
            # Check for reasonable speed values
            if (
                data.car_speed < 0 or data.car_speed > 500
            ):  # 500 km/h seems reasonable max
                logger.debug(f"Invalid speed: {data.car_speed}")
                return False

            # Check for reasonable throttle/brake values
            if not (0 <= data.throttle <= 100) or not (0 <= data.brake <= 100):
                logger.debug(f"Invalid throttle/brake: {data.throttle}, {data.brake}")
                return False

            # Check position data for NaN or extreme values
            if any(
                abs(pos) > 10000
                for pos in [data.position_x, data.position_y, data.position_z]
            ):
                logger.debug("Invalid position data")
                return False

            return True
        except (AttributeError, TypeError, ValueError) as e:
            logger.error(f"Data validation error: {e}")
            return False

    def _process_lap_data(self, data: GT7Data) -> None:
        """Process and store lap data from GT7"""
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

        self.current_lap.in_race = data.in_race
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
        self.current_lap.data_tyres_delta_fl.append(delta_fl)
        self.current_lap.data_tyres_delta_fr.append(delta_fr)
        self.current_lap.data_tyres_delta_rl.append(delta_rl)
        self.current_lap.data_tyres_delta_rr.append(delta_rr)

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

    def finish_lap(self, manual: bool = False) -> None:
        """Finishes a lap with proper thread safety"""
        with self._current_lap_lock:
            logger.debug(
                "Finishing lap %d with manual=%s",
                getattr(self.last_data, "current_lap", -1),
                manual,
            )

            # Validate we have a current lap to finish
            if not self.current_lap or len(self.current_lap.data_speed) == 0:
                logger.warning("No valid lap data to finish")
                return

            # Create a deep copy for callback to prevent race conditions
            lap_copy = None

            try:
                # Manual laps have no time assigned, so take current live time as lap finish time.
                # Finish time is tracked in seconds while live time is tracked in ms
                self.current_lap.lap_finish_time = self.current_lap.lap_live_time * 1000

                # Regular finished laps (crossing the finish line in races or time trials)
                # have their lap time stored in last_lap
                self.current_lap.lap_finish_time = self.last_data.last_lap

                # Track recording meta data
                self.current_lap.is_replay = not self.always_record_data
                self.current_lap.is_manual = manual

                self.current_lap.fuel_capacity = self.last_data.fuel_capacity
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
                self.current_lap.estimated_top_speed = (
                    self.last_data.estimated_top_speed
                )

                self.current_lap.lap_end_timestamp = datetime.datetime.now()

                # Race is not in 0th lap, which is before starting the race.
                # We will only persist those laps that have crossed the starting line at least once
                # And those laps which have data for speed logged. This will prevent empty laps.
                if (
                    self.current_lap.lap_finish_time > 0
                    and len(self.current_lap.data_speed) > 0
                ):
                    self.session.add_lap(self.current_lap)
                    lap_copy = copy.deepcopy(self.current_lap)

                # Reset current lap with an empty one
                self.current_lap = Lap()
                if hasattr(self.last_data, "current_fuel"):
                    self.current_lap.fuel_at_start = self.last_data.current_fuel

            except Exception as e:
                logger.error(f"Error finishing lap: {e}", exc_info=True)
                return

        # Call callback outside the lock to prevent deadlocks
        if lap_copy and self._on_lapfinish_callback:
            try:
                self._on_lapfinish_callback(lap_copy)
            except Exception as e:
                logger.error(f"Error in lap callback: {e}", exc_info=True)

    def _handle_connection_failure(self, attempts: int, base_delay: float) -> bool:
        """Handle connection failures with backoff strategy"""
        if attempts >= 5:
            logger.error("Too many connection failures, stopping communication")
            return False
        return True

    def _handle_socket_failure(self, attempts: int, base_delay: float) -> bool:
        """Handle socket failures"""
        if attempts >= 3:
            logger.error("Too many socket failures, stopping communication")
            return False
        return True

    def _handle_general_failure(self, attempts: int, base_delay: float) -> bool:
        """Handle general exceptions"""
        if attempts >= 5:
            logger.error("Too many general failures, stopping communication")
            return False
        return True
