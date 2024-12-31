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
        self.state = "NotReady"
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

    def set_timer(self, delay):
        """Set a timer for the current state."""
        self.timer = time.time() + delay

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

    def clear_all_timers(self):
        """Clear all active timers."""
        self.timer = None
        print("Server State Machine: All timers cleared.")

    def transition_to_not_ready(self, service_status_changed=False):
        """
        Transition from Ready to Not Ready.
        Only send StopOfferService if service_status changes to False.
        """
        if service_status_changed:
            self.send_stop_offer_service()
        self.clear_all_timers()
        self.state = "NotReady"
        print("Server State Machine: Transitioned to NotReady.")

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

    def transition_to_state(self, state, substate=None):
        """Generic method for transitioning to a new state."""
        self.state = state
        self.substate = substate
        print(f"Server: Transitioning to {state} {substate if substate else ''}")

    def handle_not_ready(self):
        """Handle the NotReady state."""
        if self.ifstatus_up_and_configured and self.service_status_up:
            self.transition_to_state("Ready", "InitialWaitPhase")
            delay = random.uniform(self.INITIAL_DELAY_MIN, self.INITIAL_DELAY_MAX)
            self.set_timer(delay)

    def handle_ready(self):
        """Handle transitions for the Ready state."""
        if not self.ifstatus_up_and_configured:
            self.transition_to_not_ready()
        elif not self.service_status_up:
            self.transition_to_not_ready(service_status_changed=True)
        elif self.substate == "InitialWaitPhase":
            if self.timer_expired():
                self.transition_to_state("Ready", "RepetitionPhase")
                self.run = 0
                self.set_timer(self.REPETITIONS_BASE_DELAY)

        elif self.substate == "RepetitionPhase":
            if self.timer_expired():
                if self.run < self.REPETITIONS_MAX:
                    self.send_offer_service()
                    self.run += 1
                    delay = self.REPETITIONS_BASE_DELAY * (2 ** self.run)
                    print(f"Repetition {self.run}. Next delay: {delay:.2f} seconds")
                    self.set_timer(delay)
                else:
                    self.transition_to_state("Ready", "MainPhase")
                    self.set_timer(self.CYCLIC_ANNOUNCE_DELAY)
            elif self.receive_find_service():
                self.send_offer_service()
                self.set_timer(self.REPETITIONS_BASE_DELAY)

        elif self.substate == "MainPhase":
            if self.timer_expired():
                self.send_offer_service()
                self.set_timer(self.CYCLIC_ANNOUNCE_DELAY)
            elif self.receive_find_service():
                self.send_offer_service()
                self.reset_timer(self.CYCLIC_ANNOUNCE_DELAY)

    def run_state_machine(self):
        """Run the state machine."""
        while True:
            if self.state == "NotReady":
                self.handle_not_ready()

            elif self.state == "Ready":
                self.handle_ready()

            time.sleep(0.1)  # Small delay to prevent 100% CPU utilization


# Example usage:
server_state_machine = SomeIPServerStateMachine()
server_thread = threading.Thread(target=server_state_machine.run_state_machine, daemon=True)
server_thread.start()
server_state_machine.ifstatus_up_and_configured = True  # Simulate network interface status
server_state_machine.service_status_up = True  # Simulate service status
time.sleep(20)  # Small delay to prevent 100% CPU utilization
server_state_machine.service_status_up = False # Simulate service status
server_thread.join()


