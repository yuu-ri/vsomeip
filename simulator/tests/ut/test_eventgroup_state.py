import socket
import time
import unittest
from unittest.mock import Mock, patch
from src.EventGroupState import EventgroupPubSubStateMachine
import threading

class TestEventgroupPubSubStateMachine(unittest.TestCase):
    def setUp(self):
        self.state_machine = EventgroupPubSubStateMachine()
        self.state_machine.sock = Mock()

    def test_initial_entry_service_down(self):
        """Test initial entry with service down"""
        self.state_machine.service_status = "Down"
        self.state_machine.handle_initial_entry()
        self.assertEqual(self.state_machine.state, "ServiceDown")

    def test_initial_entry_service_up(self):
        """Test initial entry with service up"""
        self.state_machine.service_status = "Up"
        self.state_machine.handle_initial_entry()
        self.assertEqual(self.state_machine.state, "ServiceUp")
        self.assertEqual(self.state_machine.substate, "NotSubscribed")

    def test_service_down_to_up_transition(self):
        """Test transition from ServiceDown to ServiceUp"""
        self.state_machine.state = "ServiceDown"
        self.state_machine.service_status = "Up"
        self.state_machine.handle_service_down()
        self.assertEqual(self.state_machine.state, "ServiceUp")
        self.assertEqual(self.state_machine.substate, "NotSubscribed")

    def test_service_up_to_down_transition(self):
        """Test transition from ServiceUp to ServiceDown"""
        self.state_machine.state = "ServiceUp"
        self.state_machine.service_status = "Down"
        self.state_machine.handle_service_up()
        self.assertEqual(self.state_machine.state, "ServiceDown")

    def test_not_subscribed_to_subscribed(self):
        """Test subscription transition"""
        self.state_machine.state = "ServiceUp"
        self.state_machine.substate = "NotSubscribed"
        self.state_machine.service_status = "Up"  # Ensure service status is up
        self.state_machine.receive_subscribe_eventgroup = Mock(return_value=True)

        self.state_machine.handle_service_up()

        self.assertEqual(self.state_machine.state, "ServiceUp")
        self.assertEqual(self.state_machine.substate, "Subscribed")
        self.assertEqual(self.state_machine.subscription_counter, 1)

    def test_subscribed_renew(self):
        """Test subscription renewal"""
        self.state_machine.state = "ServiceUp"
        self.state_machine.substate = "Subscribed"
        self.state_machine.service_status = "Up"  # Ensure service status is up
        self.state_machine.receive_subscribe_eventgroup = Mock(return_value=True)
        self.state_machine.timer = time.time() - 1  # Set timer to expired

        self.state_machine.handle_service_up()

        self.assertEqual(self.state_machine.substate, "Subscribed")
        self.assertIsNotNone(self.state_machine.timer)

    def test_subscribed_stop(self):
        """Test stop subscription"""
        self.state_machine.state = "ServiceUp"
        self.state_machine.substate = "Subscribed"
        self.state_machine.service_status = "Up"  # Ensure service status is up
        self.state_machine.subscription_counter = 1
        self.state_machine.receive_subscribe_eventgroup = Mock(return_value=False)
        self.state_machine.receive_stop_subscribe_eventgroup = Mock(return_value=True)

        self.state_machine.handle_service_up()

        self.assertEqual(self.state_machine.substate, "NotSubscribed")
        self.assertEqual(self.state_machine.subscription_counter, 0)

    def test_subscribed_ttl_expired(self):
        """Test TTL expiration"""
        self.state_machine.state = "ServiceUp"
        self.state_machine.substate = "Subscribed"
        self.state_machine.service_status = "Up"  # Ensure service status is up
        self.state_machine.subscription_counter = 1
        self.state_machine.timer = time.time() - 1  # Set timer to expired
        self.state_machine.receive_subscribe_eventgroup = Mock(return_value=False)
        self.state_machine.receive_stop_subscribe_eventgroup = Mock(return_value=False)

        self.state_machine.handle_service_up()

        self.assertEqual(self.state_machine.substate, "NotSubscribed")
        self.assertEqual(self.state_machine.subscription_counter, 0)

    def test_service_down_no_transition(self):
        """Test ServiceDown state with no transition"""
        self.state_machine.state = "ServiceDown"
        self.state_machine.service_status = "Down"
        self.state_machine.handle_service_down()
        self.assertEqual(self.state_machine.state, "ServiceDown")

    def test_service_up_no_transition(self):
        """Test ServiceUp state with no transition"""
        self.state_machine.state = "ServiceUp"
        self.state_machine.substate = "NotSubscribed"
        self.state_machine.service_status = "Up"
        self.state_machine.receive_subscribe_eventgroup = Mock(return_value=False)
        self.state_machine.handle_service_up()
        self.assertEqual(self.state_machine.state, "ServiceUp")
        self.assertEqual(self.state_machine.substate, "NotSubscribed")

    def test_receive_subscribe_eventgroup(self):
        """Test receiving SubscribeEventgroup message"""
        self.state_machine.sock.recvfrom = Mock(return_value=(b"SubscribeEventgroup", ("127.0.0.1", 30491)))
        result = self.state_machine.receive_subscribe_eventgroup()
        self.assertTrue(result)

    def test_receive_stop_subscribe_eventgroup(self):
        """Test receiving StopSubscribeEventgroup message"""
        self.state_machine.sock.recvfrom = Mock(return_value=(b"StopSubscribeEventgroup", ("127.0.0.1", 30491)))
        result = self.state_machine.receive_stop_subscribe_eventgroup()
        self.assertTrue(result)

    def test_receive_stop_subscribe_eventgroup_timeout(self):
        """Test receiving StopSubscribeEventgroup message with timeout"""
        self.state_machine.sock.recvfrom = Mock(side_effect=socket.timeout)
        result = self.state_machine.receive_stop_subscribe_eventgroup()
        self.assertFalse(result)

    def test_run_state_machine(self):
        """Test running the state machine"""
        self.state_machine.service_status = "Up"
        self.state_machine.sock.recvfrom = Mock(side_effect=[(b"SubscribeEventgroup", ("127.0.0.1", 30491)), socket.timeout])
        with patch('time.sleep', return_value=None):
            thread = threading.Thread(target=self.state_machine.run_state_machine)
            thread.start()
            time.sleep(0.2)  # Allow some iterations
            self.state_machine.stop()
            thread.join()
            self.assertEqual(self.state_machine.state, "ServiceUp")
            self.assertEqual(self.state_machine.substate, "Subscribed")

if __name__ == '__main__':
    unittest.main()
