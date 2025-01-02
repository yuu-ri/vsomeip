import socket
import time
import threading

class EventgroupPubSubStateMachine:
    TTL = 5  # Time-to-Live for subscriptions

    def __init__(self, udp_ip="127.0.0.1", udp_port=30490):
        # States
        self.state = "Initial"  # Start from Initial state
        self.substate = None
        self.service_status = "Down"
        self.subscription_counter = 0
        self.timer = None
        
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

    def enable_events(self):
        print("Events enabled")
        self.subscription_counter += 1

    def disable_events(self):
        print("Events disabled")
        self.subscription_counter -= 1

    def receive_subscribe_eventgroup(self):
        """Receive SubscribeEventgroup message."""
        try:
            data, addr = self.sock.recvfrom(1024)
            if data.decode() == "SubscribeEventgroup":
                print("Received SubscribeEventgroup")
                self.send_subscribe_eventgroup_ack()
                return True
        except socket.timeout:
            pass
        return False

    def send_subscribe_eventgroup_ack(self):
        """Send SubscribeEventgroupAck message."""
        message = "SubscribeEventgroupAck"
        self.sock.sendto(message.encode(), ("127.0.0.1", 30491))
        print("Sent SubscribeEventgroupAck")

    def receive_stop_subscribe_eventgroup(self):
        """Receive StopSubscribeEventgroup message."""
        try:
            data, addr = self.sock.recvfrom(1024)
            if data.decode() == "StopSubscribeEventgroup":
                print("Received StopSubscribeEventgroup")
                return True
        except socket.timeout:
            pass
        return False

    def handle_initial_entry(self):
        """Handle initial entry point transitions"""
        if self.service_status == "Down":
            self.transition_to_state("ServiceDown")
        elif self.service_status == "Up":
            self.transition_to_state("ServiceUp", "NotSubscribed")

    def handle_service_down(self):
        """Handle ServiceDown state"""
        if self.service_status == "Up":
            self.transition_to_state("ServiceUp", "NotSubscribed")

    def handle_service_up(self):
        """Handle ServiceUp state"""
        if self.service_status == "Down":
            self.transition_to_state("ServiceDown")
        elif self.substate == "NotSubscribed":
            if self.receive_subscribe_eventgroup():
                self.enable_events()
                self.send_subscribe_eventgroup_ack()
                self.transition_to_state("ServiceUp", "Subscribed")
                self.set_timer(self.TTL)
        elif self.substate == "Subscribed":
            if self.receive_subscribe_eventgroup():
                self.send_subscribe_eventgroup_ack()
                self.set_timer(self.TTL)
            elif self.receive_stop_subscribe_eventgroup():
                self.disable_events()
                self.transition_to_state("ServiceUp", "NotSubscribed")
            elif self.timer_expired() and self.subscription_counter == 1:
                self.disable_events()
                self.transition_to_state("ServiceUp", "NotSubscribed")

    def transition_to_state(self, state, substate=None):
        self.state = state
        self.substate = substate
        print(f"Transitioning to {state} {substate if substate else ''}")

    def run_state_machine(self):
        while not self.stop_event.is_set():
            if self.state == "Initial":
                self.handle_initial_entry()
            elif self.state == "ServiceDown":
                self.handle_service_down()
            elif self.state == "ServiceUp":
                self.handle_service_up()
            time.sleep(0.1)

    def stop(self):
        self.stop_event.set()
