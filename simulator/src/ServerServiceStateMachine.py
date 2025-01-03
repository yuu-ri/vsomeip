import socket
import time
import threading

class ServerServiceStateMachine:
    # Constants
    INITIAL_DELAY_MIN = 0.1
    INITIAL_DELAY_MAX = 0.5
    REPETITIONS_BASE_DELAY = 0.1
    CYCLIC_ANNOUNCE_DELAY = 1.0
    REPETITIONS_MAX = 3

    def __init__(self, udp_ip="127.0.0.1", udp_port=30490):
        # States
        self.state = "NotReady"
        self.substate = None
        self.ifstatus_up_and_configured = False
        self.service_status_up = False
        
        # Timer and counters
        self.timer = None
        self.run = 0
        
        # Communication
        self.udp_ip = udp_ip
        self.udp_port = udp_port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.udp_ip, self.udp_port))
        self.sock.settimeout(0.1)
        
        # Thread control
        self.stop_event = threading.Event()

    def set_timer(self, delay):
        self.timer = time.time() + delay

    def timer_expired(self):
        return self.timer and time.time() >= self.timer

    def clear_all_timers(self):
        self.timer = None
        self.run = 0

    def send_offer_service(self):
        self.sock.sendto(b"OfferService", (self.udp_ip, self.udp_port))

    def send_stop_offer_service(self):
        self.sock.sendto(b"StopOfferService", (self.udp_ip, self.udp_port))

    def receive_find_service(self):
        try:
            data, addr = self.sock.recvfrom(1024)
            return data == b"FindService"
        except socket.timeout:
            return False

    def wait_and_send_offer_service(self):
        time.sleep(0.01)  # Small delay
        self.send_offer_service()

    def handle_not_ready(self):
        if self.ifstatus_up_and_configured and self.service_status_up:
            self.state = "Ready"
            self.handle_initial_entry_ready()

    def handle_initial_entry_ready(self):
        self.substate = "InitialWaitPhase"
        self.set_timer(self.INITIAL_DELAY_MIN + (self.INITIAL_DELAY_MAX - self.INITIAL_DELAY_MIN) * time.time() % 1)

    def handle_initial_wait_phase(self):
        if self.timer_expired():
            self.substate = "RepetitionPhase"
            self.run = 0
            self.send_offer_service()
            self.set_timer(self.REPETITIONS_BASE_DELAY)

    def handle_repetition_phase(self):
        if self.receive_find_service():
            self.wait_and_send_offer_service()
            return

        if self.timer_expired():
            if self.run < self.REPETITIONS_MAX:
                self.send_offer_service()
                self.run += 1
                self.set_timer((2 ** self.run) * self.REPETITIONS_BASE_DELAY)
            else:
                self.substate = "MainPhase"
                self.set_timer(self.CYCLIC_ANNOUNCE_DELAY)
                self.send_offer_service()

    def handle_main_phase(self):
        if self.receive_find_service():
            self.wait_and_send_offer_service()
            return

        if self.timer_expired():
            self.set_timer(self.CYCLIC_ANNOUNCE_DELAY)
            self.send_offer_service()

    def handle_ready(self):
        if not self.ifstatus_up_and_configured:
            self.clear_all_timers()
            self.state = "NotReady"
            return
        
        if not self.service_status_up:
            self.clear_all_timers()
            self.send_stop_offer_service()
            self.state = "NotReady"
            return

        if self.substate == "InitialWaitPhase":
            self.handle_initial_wait_phase()
        elif self.substate == "RepetitionPhase":
            self.handle_repetition_phase()
        elif self.substate == "MainPhase":
            self.handle_main_phase()

    def run_state_machine(self):
        while not self.stop_event.is_set():
            if self.state == "NotReady":
                self.handle_not_ready()
            elif self.state == "Ready":
                self.handle_ready()
            time.sleep(0.01)

    def stop(self):
        self.stop_event.set()