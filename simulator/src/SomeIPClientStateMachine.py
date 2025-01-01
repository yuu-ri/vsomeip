import time
import random
import socket


class SomeIPClientStateMachine:
    INITIAL_DELAY_MIN = 1  # Minimum initial delay for Searching for Service
    INITIAL_DELAY_MAX = 2  # Maximum initial delay for Searching for Service
    REPETITIONS_BASE_DELAY = 1  # Base delay for repetitions
    REPETITIONS_MAX = 3  # Maximum repetitions in the Repetition Phase
    TTL = 5  # Time-to-Live for a service announcement

    def __init__(self, udp_ip="127.0.0.1", udp_port=30491):
        self.state = "NotRequested"
        self.substate = None
        self.udp_ip = udp_ip
        self.udp_port = udp_port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.udp_ip, self.udp_port))
        self.sock.settimeout(0.1)  # Non-blocking with a 100ms timeout
        self.timer = None
        self.run = 0
        self.service_seen = False
        self.service_ready = False
        self.ifstatus_up_and_configured = False  # Simulates the ifstatus condition

    def set_timer(self, delay):
        """Set a timer for the current state."""
        self.timer = time.time() + delay

    def reset_timer(self, delay):
        """Reset the timer with a new delay."""
        self.set_timer(delay)

    def timer_expired(self):
        """Check if the timer has expired."""
        return self.timer and time.time() >= self.timer

    def send_find_service(self):
        """Send a FindService request."""
        message = "FindService"
        self.sock.sendto(message.encode(), (self.udp_ip, 30490))
        print("Client: Sent FindService")

    def receive_offer_service(self):
        print("""Receive OfferService message (non-blocking).""")
        try:
            data, addr = self.sock.recvfrom(1024)
            print(data)
            if data.decode() == "OfferService":
                print("Client: Received OfferService")
                return True
        except socket.timeout:
            pass
        return False

    def receive_stop_offer_service(self):
        """Simulate receiving a StopOfferService message."""
        try:
            data, addr = self.sock.recvfrom(1024)
            if data.decode() == "StopOfferService":
                print("Client: Received StopOfferService")
                return True
        except socket.timeout:
            pass
        return False

    def transition_to_state(self, state, substate=None):
        """Generic method for transitioning to a new state."""
        self.state = state
        self.substate = substate
        print(f"Client: Transitioning to {state} {substate if substate else ''}")

    def handle_service_not_seen(self):
        """Handle ServiceNotSeen state."""
        if self.receive_offer_service():
            self.set_timer(self.TTL)
            self.transition_to_state("NotRequested", "ServiceSeen")

    def handle_service_seen(self):
        """Handle ServiceSeen state."""
        if not self.ifstatus_up_and_configured:
            self.transition_to_state("NotRequested", "ServiceNotSeen")
        elif self.timer_expired():
            self.transition_to_state("NotRequested", "ServiceNotSeen")
        elif self.receive_stop_offer_service():
            self.transition_to_state("NotRequested", "ServiceNotSeen")
        elif self.ifstatus_up_and_configured:
            self.transition_to_state("Main", "ServiceReady")

    def internal_service_request(self):
        return True

    def handle_not_requested(self):
        """Handle the NotRequested state."""
        if not self.service_seen:
            self.handle_service_not_seen()
        elif self.service_seen:
            self.handle_service_seen()
        elif self.internal_service_request() and not self.ifstatus_up_and_configured:
            self.transition_to_state("RequestedButNotReady")

    def handle_searching_for_service(self):
        """Handle transitions for SearchingForService state."""
        if self.substate == "InitialWaitPhase":
            if self.timer_expired():
                self.send_find_service()
                self.transition_to_state("SearchingForService", "RepetitionPhase")
                self.run = 0
                self.set_timer(self.REPETITIONS_BASE_DELAY)

        elif self.substate == "RepetitionPhase":
            if self.timer_expired():
                if self.run < self.REPETITIONS_MAX:
                    self.send_find_service()
                    self.run += 1
                    delay = self.REPETITIONS_BASE_DELAY * (2 ** self.run)
                    print(f"Repetition {self.run}. Next delay: {delay:.2f} seconds")
                    self.set_timer(delay)
                else:
                    self.transition_to_state("Stopped")
            elif self.receive_offer_service():
                self.transition_to_state("Main", "ServiceReady")
                self.set_timer(self.TTL)

    def handle_requested_but_not_ready(self):
        """Handle transitions for RequestedButNotReady state."""
        if self.ifstatus_up_and_configured:
            self.transition_to_state("SearchingForService", "InitialWaitPhase")
            delay = random.uniform(self.INITIAL_DELAY_MIN, self.INITIAL_DELAY_MAX)
            self.set_timer(delay)

    def handle_stopped(self):
        """Handle transitions for the Stopped state."""
        if self.receive_offer_service():
            print("Client: Received OfferService. Transitioning to Service Ready.")
            self.transition_to_state("Main", "ServiceReady")
            self.reset_timer(self.TTL)

    def handle_main_phase(self):
        """Handle transitions for the Main state."""
        if self.substate == "ServiceReady":
            if self.timer_expired():
                print("Client: TTL expired. Transitioning to Searching for Service.")
                self.transition_to_state("SearchingForService", "InitialWaitPhase")
                delay = random.uniform(self.INITIAL_DELAY_MIN, self.INITIAL_DELAY_MAX)
                self.set_timer(delay)
            elif self.receive_stop_offer_service():
                self.transition_to_state("Stopped")
            elif self.receive_offer_service():
                self.reset_timer(self.TTL)
        elif self.substate == "Stopped":
            self.handle_stopped()

    def run_state_machine(self):
        """Run the state machine."""
        while True:
            if self.state == "NotRequested":
                self.handle_not_requested()

            elif self.state == "SearchingForService":
                self.handle_searching_for_service()

            elif self.state == "RequestedButNotReady":
                self.handle_requested_but_not_ready()

            elif self.state == "Main":
                self.handle_main_phase()

            time.sleep(0.1)  # Small delay to prevent 100% CPU utilization


# Example usage:
client_state_machine = SomeIPClientStateMachine()
client_state_machine.ifstatus_up_and_configured = True  # Simulates the ifstatus condition
client_state_machine.run_state_machine()
