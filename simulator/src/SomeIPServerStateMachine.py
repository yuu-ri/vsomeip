import time
import random
import socket
import threading

class SomeIPServerStateMachine:
    INITIAL_DELAY_MIN = 1  # Minimum delay for Initial Wait Phase
    INITIAL_DELAY_MAX = 2  # Maximum delay for Initial Wait Phase
    REPETITIONS_BASE_DELAY = 1  # Base delay for Repetition Phase
    REPETITIONS_MAX = 3  # Maximum repetitions in Repetition Phase
    CYCLIC_ANNOUNCE_DELAY = 5  # Delay for cyclic announcements in Main Phase

    def __init__(self, udp_ip="127.0.0.1", udp_port=30490):
        self.state = "Initial"
        self.substate = None
        self.udp_ip = udp_ip
        self.udp_port = udp_port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.udp_ip, self.udp_port))
        self.sock.settimeout(0.1)  # Non-blocking with a 100ms timeout
        self.timer = None
        self.run = 0
        self.ifstatus_up_and_configured = False  # Simulates the ifstatus condition
        self.service_status_up = False  # Simulates the service status
        self.stop_event = threading.Event()

    def set_timer(self, delay):
        """Set a timer for the current state."""
        self.timer = time.time() + delay

    def set_timer_in_range(self, min_delay, max_delay):
        """Set a timer with a random delay in the specified range."""
        delay = random.uniform(min_delay, max_delay)
        self.set_timer(delay)
        print(f"Server: Timer set for {delay:.2f} seconds.")

    def reset_timer(self, delay):
        """Reset the timer with a new delay."""
        self.set_timer(delay)

    def timer_expired(self):
        """Check if the timer has expired."""
        return self.timer and time.time() >= self.timer

    def send_offer_service(self):
        """Send an OfferService message."""
        message = "OfferService"
        self.sock.sendto(message.encode(), ("127.0.0.1", 30491))  # Assuming client listens on this port
        print("Server: Sent OfferService")

    def send_stop_offer_service(self):
        """Send a StopOfferService message."""
        message = "StopOfferService"
        self.sock.sendto(message.encode(), ("127.0.0.1", 30491))
        print("Server: Sent StopOfferService")

    def wait_and_send_offer_service(self):
        """Simulate waiting and sending an OfferService message."""
        time.sleep(0.1)  # Simulated wait
        self.send_offer_service()

    def clear_all_timers(self):
        """Clear all active timers."""
        self.timer = None
        print("Server State Machine: All timers cleared.")

    def handle_initial_entry_ready(self):
        """Handle the initial entry point for the Ready state."""
        print("Server: Handling initial Ready state.")
        self.substate = "InitialWaitPhase"
        self.handle_initial_entry_initial_wait_phase()
        print("Server: Transitioned to Ready -> InitialWaitPhase.")

    def handle_initial_entry_initial_wait_phase(self):
        """Handle the initial entry point for the InitialWaitPhase substate."""
        self.set_timer_in_range(self.INITIAL_DELAY_MIN, self.INITIAL_DELAY_MAX)
        print("Server: Handling initial InitialWaitPhase.")

    def handle_initial_entry_repetition_phase(self):
        """Handle the initial entry point for the RepetitionPhase substate."""
        print("Server: Handling initial RepetitionPhase.")
        self.run = 0
        self.set_timer(self.REPETITIONS_BASE_DELAY)

    def handle_initial_entry_main_phase(self):
        """Handle the initial entry point for the MainPhase substate."""
        print("Server: Handling initial MainPhase.")
        self.set_timer(self.CYCLIC_ANNOUNCE_DELAY)
        self.send_offer_service()

    def handle_not_ready(self):
        """Handle the Not Ready state."""
        if self.ifstatus_up_and_configured and self.service_status_up:
            self.state = "Ready"
            self.handle_initial_entry_ready()

    def handle_initial_wait_phase(self):
        """Handle the Initial Wait Phase substate."""
        if self.timer_expired():
            self.send_offer_service()
            self.substate = "RepetitionPhase"
            self.handle_initial_entry_repetition_phase()

    def handle_repetition_phase(self):
        """Handle the Repetition Phase substate."""
        if self.timer_expired():
            if self.run < self.REPETITIONS_MAX:
                self.send_offer_service()
                self.run += 1
                delay = self.REPETITIONS_BASE_DELAY * (2 ** self.run)
                self.set_timer(delay)
                print(f"Server: Repetition {self.run}, next delay: {delay:.2f} seconds.")
            else:
                self.substate = "MainPhase"
                self.handle_initial_entry_main_phase()
        elif self.receive_find_service():
            self.wait_and_send_offer_service()
            self.set_timer(self.REPETITIONS_BASE_DELAY)

    def handle_main_phase(self):
        """Handle the Main Phase substate."""
        if self.timer_expired():
            self.send_offer_service()
            self.set_timer(self.CYCLIC_ANNOUNCE_DELAY)
        elif self.receive_find_service():
            self.wait_and_send_offer_service()
            self.reset_timer(self.CYCLIC_ANNOUNCE_DELAY)

    def handle_ready(self):
        """Handle the Ready state."""
        if not self.ifstatus_up_and_configured:
            self.state = "NotReady"
            self.substate = None
            self.clear_all_timers()
            print("Server: Transitioned to NotReady.")
        elif not self.service_status_up:
            self.state = "NotReady"
            self.substate = None
            self.send_stop_offer_service()
            self.clear_all_timers()
            print("Server: Transitioned to NotReady with StopOfferService.")
        if self.substate == "InitialWaitPhase":
            self.handle_initial_wait_phase()
        elif self.substate == "RepetitionPhase":
            self.handle_repetition_phase()
        elif self.substate == "MainPhase":
            self.handle_main_phase()

    def receive_find_service(self):
        """Receive FindService message (non-blocking)."""
        try:
            data, addr = self.sock.recvfrom(1024)
            if data.decode() == "FindService":
                print("Server: Received FindService")
                return True
        except socket.timeout:
            pass
        return False

    def handle_initial_entry(self):
        print("---LY---")
        """
        Handle entry points of the state machine.
        """
        print(self.ifstatus_up_and_configured, self.service_status_up)
        if not self.ifstatus_up_and_configured or not self.service_status_up:
            self.state = "NotReady"
        elif self.ifstatus_up_and_configured and self.service_status_up:
            self.state = "Ready"
            print("handle_initial_entry_ready")
            self.handle_initial_entry_ready()

    def run_state_machine(self):
        print("""Run the state machine.""")
        while not self.stop_event.is_set():
            if self.state == "Initial":
                print("handle_initial_entry")
                self.handle_initial_entry()
            elif self.state == "NotReady":
                print("handle_not_ready")
                self.handle_not_ready()
            elif self.state == "Ready":
                print("handle_ready")
                self.handle_ready()

            time.sleep(0.1)  # Small delay to prevent 100% CPU utilization

    def stop(self):
        self.stop_event.set()

if __name__ == '__main__':
    # Example usage:
    server_state_machine = SomeIPServerStateMachine()
    server_thread = threading.Thread(target=server_state_machine.run_state_machine, daemon=True)
    server_thread.start()
    server_state_machine.ifstatus_up_and_configured = True  # Simulate network interface status
    server_state_machine.service_status_up = True  # Simulate service status
    time.sleep(20)  # Small delay to prevent 100% CPU utilization
    server_state_machine.service_status_up = False # Simulate service status
    server_thread.join()


