import time
import random
import socket
import threading

class ClientServiceStateMachine:
    INITIAL_DELAY_MIN = 1
    INITIAL_DELAY_MAX = 2
    REPETITIONS_BASE_DELAY = 1
    REPETITIONS_MAX = 4
    TTL = 5

    def __init__(self, udp_ip="127.0.0.1", udp_port=30491):
        self.state = "Initial"
        self.substate = None
        self.service_requested = False
        self.udp_ip = udp_ip
        self.udp_port = udp_port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.udp_ip, self.udp_port))
        self.sock.settimeout(0.1)  # Non-blocking with a 100ms timeout
        self.timer = None
        self.run = 0
        self.ifstatus_up_and_configured = False
        self.stop_event = threading.Event()

    def set_timer(self, delay):
        self.timer = time.time() + delay

    def reset_timer(self, delay):
        self.set_timer(delay)

    def timer_expired(self):
        return self.timer and time.time() >= self.timer

    def cancel_timer(self):
        self.timer = None

    def set_timer_in_range(self, min_delay, max_delay):
        delay = min_delay + (max_delay - min_delay) * random.random()
        self.set_timer(delay)

    def send_find_service(self):
        message = "FindService"
        self.sock.sendto(message.encode(), (self.udp_ip, 30490))
        print("Client: Sent FindService")

    def receive_offer_service(self):
        try:
            data, addr = self.sock.recvfrom(1024)
            if data.decode() == "OfferService":
                print("Client: Received OfferService")
                return True
        except socket.timeout:
            pass
        return False

    def receive_stop_offer_service(self):
        try:
            data, addr = self.sock.recvfrom(1024)
            if data.decode() == "StopOfferService":
                print("Client: Received StopOfferService")
                return True
        except socket.timeout:
            pass
        return False

    def transition_to_state(self, state, substate=None):
        self.state = state
        self.substate = substate
        print(f"Client: Transitioning to {state} {substate if substate else ''}")

    def handle_initial(self):
        if not self.service_requested:
            self.state = "NotRequested"
        elif self.service_requested and not self.ifstatus_up_and_configured:
            self.state = "RequestedButNotReady"
        elif self.service_requested and self.ifstatus_up_and_configured:
            self.state = "SearchingForService"
            self.handle_searching_for_service_initial_entry()

    def handle_not_requested(self):
        if self.service_requested and not self.ifstatus_up_and_configured:
            self.state = "RequestedButNotReady"

    def handle_requested_but_not_ready(self):
        if self.ifstatus_up_and_configured:
            self.transition_to_state("SearchingForService")
            self.handle_searching_for_service_initial_entry()

    def handle_searching_for_service_initial_entry(self):
        self.transition_to_state("SearchingForService", "InitialWaitPhase")
        self.set_timer_in_range(self.INITIAL_DELAY_MIN, self.INITIAL_DELAY_MAX)

    def handle_initial_wait_phase(self):
        if self.timer_expired():
            self.send_find_service()
            self.transition_to_state("SearchingForService", "RepetitionPhase")
            self.run = 0
            self.set_timer(self.REPETITIONS_BASE_DELAY * (2 ** self.run))

    def handle_repetition_phase(self):
        if self.timer_expired():
            if self.run < self.REPETITIONS_MAX:
                self.send_find_service()
                self.run += 1
                self.set_timer(self.REPETITIONS_BASE_DELAY * (2 ** self.run))
            else:
                self.transition_to_state("Stopped")
        elif self.receive_stop_offer_service():
            self.transition_to_state("Stopped")

    def handle_searching_for_service(self):
        if not self.ifstatus_up_and_configured:
            self.cancel_timer()
            self.transition_to_state("RequestedButNotReady")
            return
        if self.receive_offer_service():
            self.set_timer(self.TTL)
            self.transition_to_state("ServiceReady")
        if self.substate == "InitialWaitPhase":
            self.handle_initial_wait_phase()
        elif self.substate == "RepetitionPhase":
            self.handle_repetition_phase()

    def handle_service_ready(self):
        if self.receive_offer_service():
            self.reset_timer(self.TTL)
        elif self.timer_expired():
            self.transition_to_state("SearchingForService")
            self.handle_searching_for_service_initial_entry()
        elif not self.ifstatus_up_and_configured:
            self.cancel_timer()
            self.transition_to_state("RequestedButNotReady")
        elif self.receive_stop_offer_service():
            self.cancel_timer()
            self.transition_to_state("Stopped")

    def handle_stopped(self):
        if not self.service_requested:
            self.transition_to_state("NotRequested", "ServiceNotSeen")
        elif self.receive_offer_service():
            self.reset_timer(self.TTL)
            self.transition_to_state("ServiceReady")

    def run_state_machine(self):
        while not self.stop_event.is_set():
            if self.state == "Initial":
                self.handle_initial()
            elif self.state == "NotRequested":
                self.handle_not_requested()
            elif self.state == "RequestedButNotReady":
                self.handle_requested_but_not_ready()
            elif self.state == "SearchingForService":
                self.handle_searching_for_service()
            elif self.state == "ServiceReady":
                self.handle_service_ready()
            elif self.state == "Stopped":
                self.handle_stopped()
            time.sleep(0.1)

    def stop(self):
        self.stop_event.set()
