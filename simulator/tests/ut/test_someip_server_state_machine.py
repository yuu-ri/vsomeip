import socket
import time
import unittest
from unittest.mock import Mock, patch
from src.SomeIPServerStateMachine import SomeIPServerStateMachine
import threading

class TestSomeIPServerStateMachine(unittest.TestCase):
    def setUp(self):
        self.state_machine = SomeIPServerStateMachine()
        self.state_machine.sock = Mock()

    def test_initial_entry_not_ready(self):
        """Test initial entry to Not Ready state"""
        self.state_machine.ifstatus = "down"
        self.state_machine.service_status = "down"
        self.state_machine.handle_initial_ready()
        self.assertEqual(self.state_machine.state, "Not Ready")

    def test_initial_entry_ready_initial_wait_phase(self):
        """Test initial entry to Ready state (Initial Wait Phase)"""
        self.state_machine.ifstatus = "up_and_configured"
        self.state_machine.service_status = "up"
        self.state_machine.handle_initial_ready()
        self.assertEqual(self.state_machine.state, "Ready")
        self.assertEqual(self.state_machine.substate, "Initial Wait Phase")

    def test_transition_not_ready_to_ready(self):
        """Test transition from Not Ready to Ready"""
        self.state_machine.state = "Not Ready"
        self.state_machine.ifstatus = "up_and_configured"
        self.state_machine.service_status = "up"
        self.state_machine.handle_not_ready()
        self.assertEqual(self.state_machine.state, "Ready")
        self.assertEqual(self.state_machine.substate, "Initial Wait Phase")

    def test_transition_ready_to_not_ready(self):
        """Test transition from Ready to Not Ready"""
        self.state_machine.state = "Ready"
        self.state_machine.ifstatus = "down"
        self.state_machine.handle_ready()
        self.assertEqual(self.state_machine.state, "Not Ready")

    def test_timer_set_initial_wait_phase(self):
        """Test timer set in Initial Wait Phase"""
        self.state_machine.state = "Ready"
        self.state_machine.substate = "Initial Wait Phase"
        self.state_machine.set_timer = Mock()
        self.state_machine.handle_ready()
        self.state_machine.set_timer.assert_called_with(self.state_machine.INITIAL_DELAY_MIN, self.state_machine.INITIAL_DELAY_MAX)

    def test_timer_expired_repetition_phase(self):
        """Test timer expired in Repetition Phase"""
        self.state_machine.state = "Ready"
        self.state_machine.substate = "Repetition Phase"
        self.state_machine.timer_expired = Mock(return_value=True)
        self.state_machine.run = 0
        self.state_machine.handle_ready()
        self.assertEqual(self.state_machine.substate, "Repetition Phase")
        self.state_machine.set_timer.assert_called_with((2 ** self.state_machine.run) * self.state_machine.REPETITIONS_BASE_DELAY)

    def test_transition_repetition_phase_to_main_phase(self):
        """Test transition from Repetition Phase to Main Phase"""
        self.state_machine.state = "Ready"
        self.state_machine.substate = "Repetition Phase"
        self.state_machine.timer_expired = Mock(return_value=True)
        self.state_machine.run = self.state_machine.REPETITIONS_MAX
        self.state_machine.handle_ready()
        self.assertEqual(self.state_machine.substate, "Main Phase")

    def test_timer_set_main_phase(self):
        """Test timer set in Main Phase"""
        self.state_machine.state = "Ready"
        self.state_machine.substate = "Main Phase"
        self.state_machine.set_timer = Mock()
        self.state_machine.handle_ready()
        self.state_machine.set_timer.assert_called_with(self.state_machine.CYCLIC_ANNOUNCE_DELAY)

    def test_receive_find_service_main_phase(self):
        """Test receiving FindService in Main Phase"""
        self.state_machine.state = "Ready"
        self.state_machine.substate = "Main Phase"
        self.state_machine.sock.recvfrom = Mock(return_value=(b"FindService", ("127.0.0.1", 30491)))
        self.state_machine.handle_ready()
        self.state_machine.wait_and_send.assert_called_with("OfferService")
        self.state_machine.reset_timer.assert_called()

    def test_run_state_machine_service_down(self):
        """Test running the state machine with service down"""
        self.state_machine.state = "Initial"
        self.state_machine.service_status = "Down"
        with patch.object(self.state_machine, 'handle_service_down') as mock_handle_service_down:
            with patch('time.sleep', return_value=None):
                thread = threading.Thread(target=self.state_machine.run_state_machine)
                thread.start()
                time.sleep(0.2)  # Allow some iterations
                self.state_machine.stop()
                thread.join()
                mock_handle_service_down.assert_called()

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
