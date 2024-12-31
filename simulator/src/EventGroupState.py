import time
import socket


class EventgroupPubSubStateMachine:
    TTL = 5  # Time-To-Live for subscriptions in seconds

    def __init__(self, udp_ip="127.0.0.1", udp_port=30500):
        self.state = "ServiceDown"
        self.substate = None
        self.subscription_counter = 0
        self.timer = None
        self.udp_ip = udp_ip
        self.udp_port = udp_port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.udp_ip, self.udp_port))
        self.sock.settimeout(0.1)  # Non-blocking with a 100ms timeout
        self.service_status_up = False  # Simulates the service status

    def set_timer(self, delay):
        """Set a timer for subscription TTL."""
        self.timer = time.time() + delay

    def reset_timer(self, delay):
        """Reset the timer with a new delay."""
        self.set_timer(delay)

    def timer_expired(self):
        """Check if the timer has expired."""
        return self.timer and time.time() >= self.timer

    def transition_to_state(self, state, substate=None):
        """Generic method for transitioning to a new state."""
        self.state = state
        self.substate = substate
        print(f"PubSub State Machine: Transitioning to {state} {substate if substate else ''}")

    def send_ack(self, message):
        """Send acknowledgment messages."""
        self.sock.sendto(message.encode(), ("127.0.0.1", 30501))  # Assuming client listens on this port
        print(f"PubSub State Machine: Sent {message}")

    def receive_message(self):
        """Receive messages (non-blocking)."""
        try:
            data, addr = self.sock.recvfrom(1024)
            return data.decode()
        except socket.timeout:
            return None

    def enable_events(self):
        """Enable events for the subscribed client."""
        print("PubSub State Machine: Events enabled for client.")

    def disable_events(self):
        """Disable events for the client."""
        print("PubSub State Machine: Events disabled for client.")

    def handle_service_down(self):
        """Handle the Service Down state."""
        if self.service_status_up:
            self.transition_to_state("ServiceUp", "NotSubscribed")

    def handle_service_up(self):
        """Handle the Service Up state and its substates."""
        if self.substate == "NotSubscribed":
            message = self.receive_message()
            if message == "SubscribeEventgroup":
                self.transition_to_state("ServiceUp", "Subscribed")
                self.enable_events()
                self.send_ack("SubscribeEventgroupAck")
                self.subscription_counter = 1
                self.set_timer(self.TTL)

        elif self.substate == "Subscribed":
            message = self.receive_message()
            if message == "SubscribeEventgroup":
                self.send_ack("SubscribeEventgroupAck")
            elif message == "StopSubscribeEventgroup":
                self.transition_to_state("ServiceUp", "NotSubscribed")
                self.disable_events()
            elif self.timer_expired() and self.subscription_counter == 1:
                self.transition_to_state("ServiceUp", "NotSubscribed")
                self.disable_events()

    def run_state_machine(self):
        """Run the state machine."""
        while True:
            if self.state == "ServiceDown":
                self.handle_service_down()

            elif self.state == "ServiceUp":
                self.handle_service_up()

            time.sleep(0.1)  # Small delay to prevent 100% CPU utilization


# Example usage:
pubsub_state_machine = EventgroupPubSubStateMachine()
pubsub_state_machine.service_status_up = True  # Simulate service up
pubsub_state_machine.run_state_machine()

