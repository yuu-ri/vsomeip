import unittest
from unittest.mock import Mock, patch
import socket
import threading
import time
from simulator.src.SomeIPServerStateMachine import SomeIPServerStateMachine

class TestSomeIPServerStateMachine(unittest.TestCase):
    def setUp(self):
        """Initialize test environment before each test"""
        self.state_machine = SomeIPServerStateMachine()
        self.state_machine.sock = Mock()
        
    def tearDown(self):
        """Clean up after each test"""
        self.state_machine.sock.close()

    def test_initial_state(self):
        """Test initial state configuration"""
        self.assertEqual(self.state_machine.state, "Initial")
        self.assertIsNone(self.state_machine.substate)
        self.assertFalse(self.state_machine.ifstatus_up_and_configured)
        self.assertFalse(self.state_machine.service_status_up)

    def test_transition_to_not_ready(self):
        """Test transition to Not Ready state"""
        self.state_machine.ifstatus_up_and_configured = False
        self.state_machine.service_status_up = True
        self.state_machine.handle_initial_entry()
        self.assertEqual(self.state_machine.state, "NotReady")

    def test_transition_to_ready(self):
        """Test transition to Ready state"""
        self.state_machine.ifstatus_up_and_configured = True
        self.state_machine.service_status_up = True
        self.state_machine.handle_initial_entry()
        self.assertEqual(self.state_machine.state, "Ready")
        self.assertEqual(self.state_machine.substate, "InitialWaitPhase")

    def test_initial_wait_phase_timer(self):
        """Test timer setting in Initial Wait Phase"""
        self.state_machine.state = "Ready"
        self.state_machine.substate = "InitialWaitPhase"
        self.state_machine.handle_initial_entry_initial_wait_phase()
        self.assertIsNotNone(self.state_machine.timer)
        
    def test_repetition_phase_transitions(self):
        """Test Repetition Phase transitions and timer behavior"""
        self.state_machine.state = "Ready"
        self.state_machine.substate = "RepetitionPhase"
        self.state_machine.run = 0
        self.state_machine.timer = time.time() - 1  # Expired timer
        
        with patch.object(self.state_machine, 'send_offer_service'):
            self.state_machine.handle_repetition_phase()
            self.assertEqual(self.state_machine.run, 1)
            
    def test_main_phase_cyclic_announcement(self):
        """Test Main Phase cyclic announcements"""
        self.state_machine.state = "Ready"
        self.state_machine.substate = "MainPhase"
        self.state_machine.timer = time.time() - 1  # Expired timer
        
        with patch.object(self.state_machine, 'send_offer_service'):
            self.state_machine.handle_main_phase()
            self.assertGreater(self.state_machine.timer, time.time())

    def test_find_service_handling(self):
        """Test FindService message handling"""
        self.state_machine.sock.recvfrom = Mock(return_value=(b"FindService", ("127.0.0.1", 30491)))
        self.assertTrue(self.state_machine.receive_find_service())

    def test_service_status_change(self):
        """Test service status change handling"""
        self.state_machine.state = "Ready"
        self.state_machine.service_status_up = False
        with patch.object(self.state_machine, 'send_stop_offer_service'):
            self.state_machine.handle_ready()
            self.assertEqual(self.state_machine.state, "NotReady")

    def test_clear_timers(self):
        """Test timer clearing functionality"""
        self.state_machine.timer = time.time()
        self.state_machine.clear_all_timers()
        self.assertIsNone(self.state_machine.timer)

    def test_state_machine_thread_safety(self):
        """Test state machine thread safety"""
        self.state_machine.ifstatus_up_and_configured = True
        self.state_machine.service_status_up = True
        
        thread = threading.Thread(target=self.state_machine.run_state_machine)
        thread.daemon = True
        thread.start()
        time.sleep(0.2)  # Allow state machine to run
        
        self.assertIn(self.state_machine.state, ["Ready", "NotReady"])
        
        # Cleanup
        thread.join(timeout=0.1)

    def test_transition_timing(self):
        """Test transition timing requirements"""
        with patch('time.time', side_effect=[0, 1, 2, 3]):
            self.state_machine.set_timer_in_range(
                self.state_machine.INITIAL_DELAY_MIN,
                self.state_machine.INITIAL_DELAY_MAX
            )
            self.assertTrue(
                self.state_machine.INITIAL_DELAY_MIN <= self.state_machine.timer <= 
                self.state_machine.INITIAL_DELAY_MAX
            )

    def test_repetition_max_transition(self):
        """Test transition after max repetitions"""
        self.state_machine.state = "Ready"
        self.state_machine.substate = "RepetitionPhase"
        self.state_machine.run = self.state_machine.REPETITIONS_MAX
        self.state_machine.timer = time.time() - 1  # Expired timer
        
        self.state_machine.handle_repetition_phase()
        self.assertEqual(self.state_machine.substate, "MainPhase")

if __name__ == '__main__':
    unittest.main()