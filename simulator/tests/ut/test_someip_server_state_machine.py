import unittest
from unittest.mock import Mock, patch
import socket
import threading
import time
from src.SomeIPServerStateMachine import SomeIPServerStateMachine

class TestSomeIPServerStateMachine(unittest.TestCase):
    def setUp(self):
        self.state_machine = SomeIPServerStateMachine()
        self.state_machine.sock = Mock()

    def tearDown(self):
        self.state_machine.stop()
        self.state_machine.sock.close()

    def test_initial_state(self):
        """Test initial state configuration according to AUTOSAR spec"""
        self.assertEqual(self.state_machine.state, "Initial")
        self.assertIsNone(self.state_machine.substate)
        self.assertFalse(self.state_machine.ifstatus_up_and_configured)
        self.assertFalse(self.state_machine.service_status_up)

    def test_state_transitions(self):
        """Test all state transitions defined in AUTOSAR spec"""
        # Initial → NotReady transition
        self.state_machine.ifstatus_up_and_configured = False
        self.state_machine.handle_initial_entry()
        self.assertEqual(self.state_machine.state, "NotReady")

        # NotReady → Ready transition
        self.state_machine.ifstatus_up_and_configured = True
        self.state_machine.service_status_up = True
        self.state_machine.handle_not_ready()
        self.assertEqual(self.state_machine.state, "Ready")

    def test_ready_substates(self):
        """Test Ready state substate transitions"""
        self.state_machine.state = "Ready"
        
        # Test InitialWaitPhase
        self.state_machine.handle_initial_entry_ready()
        self.assertEqual(self.state_machine.substate, "InitialWaitPhase")
        
        # Test RepetitionPhase
        self.state_machine.timer = time.time() - 1  # Expire timer
        self.state_machine.handle_initial_wait_phase()
        self.assertEqual(self.state_machine.substate, "RepetitionPhase")

    def test_timer_management(self):
        """Test timer settings and management"""
        # Mock socket operations
        self.state_machine.sock.recvfrom.return_value = (b"FindService", ("127.0.0.1", 30491))

        # 1. Setup and verify initial state
        self.state_machine.state = "Ready"
        self.state_machine.ifstatus_up_and_configured = True
        self.state_machine.service_status_up = True
        
        # 2. Test InitialWaitPhase
        self.state_machine.handle_initial_entry_ready()
        self.assertEqual(self.state_machine.substate, "InitialWaitPhase")
        self.assertIsNotNone(self.state_machine.timer)
        
        # 3. Verify InitialWaitPhase timer
        current_timer = self.state_machine.timer - time.time()
        self.assertTrue(0 <= current_timer <= self.state_machine.INITIAL_DELAY_MAX)
        
        # 4. Transition to RepetitionPhase
        self.state_machine.substate = "RepetitionPhase"
        self.state_machine.run = 0

        with patch.object(self.state_machine, 'receive_find_service', return_value=False):
            self.state_machine.handle_ready()
            self.assertIsNotNone(self.state_machine.timer)

        self.state_machine.run = 0
        self.state_machine.handle_ready()
        self.assertIsNotNone(self.state_machine.timer, "Timer should be set in RepetitionPhase")
        
        # 5. Verify RepetitionPhase timer
        repetition_timer = self.state_machine.timer - time.time()
        expected_delay = (2 ** self.state_machine.run) * self.state_machine.REPETITIONS_BASE_DELAY
        self.assertTrue(0 <= repetition_timer <= expected_delay + 0.1)

    def test_network_communication(self):
        """Test network message handling"""
        # Test FindService reception
        self.state_machine.sock.recvfrom.return_value = (b"FindService", ("127.0.0.1", 30491))
        self.assertTrue(self.state_machine.receive_find_service())

        # Test OfferService sending
        with patch.object(self.state_machine, 'send_offer_service') as mock_send:
            self.state_machine.handle_main_phase()
            mock_send.assert_called_once()

    def test_status_changes(self):
        """Test interface and service status changes"""
        # Test interface status change
        self.state_machine.state = "Ready"
        self.state_machine.ifstatus_up_and_configured = False
        self.state_machine.handle_ready()
        self.assertEqual(self.state_machine.state, "NotReady")

        # Test service status change
        self.state_machine.service_status_up = False
        with patch.object(self.state_machine, 'send_stop_offer_service'):
            self.state_machine.handle_ready()
            self.assertEqual(self.state_machine.state, "NotReady")

    def test_thread_safety(self):
        """Test thread-safe operation of state machine"""
        self.state_machine.ifstatus_up_and_configured = True
        self.state_machine.service_status_up = True
        
        thread = threading.Thread(target=self.state_machine.run_state_machine)
        thread.daemon = True
        thread.start()
        
        time.sleep(0.2)
        self.assertIn(self.state_machine.state, ["Ready", "NotReady"])
        self.state_machine.stop()
        thread.join(timeout=0.1)

    def test_send_stop_offer_service(self):
        """Test stop offer service functionality"""
        with patch.object(self.state_machine.sock, 'sendto') as mock_sendto:
            self.state_machine.send_stop_offer_service()
            mock_sendto.assert_called_once()

    def test_handle_main_phase(self):
        """Test main phase handling"""
        # Setup mock for socket operations
        mock_data = (b"FindService", ("127.0.0.1", 30491))
        self.state_machine.sock.recvfrom.return_value = mock_data
        
        # Setup state machine
        self.state_machine.state = "Ready"
        self.state_machine.substate = "MainPhase"
        self.state_machine.timer = time.time() - 1  # Expired timer
        
        # Test with mocked socket and send_offer_service
        with patch.object(self.state_machine, 'send_offer_service') as mock_send:
            with patch.object(self.state_machine, 'receive_find_service', return_value=False):
                self.state_machine.handle_main_phase()
                mock_send.assert_called_once() 
    
    def test_receive_find_service(self):
        """Test find service message reception"""
        mock_data = (b"FindService", ("127.0.0.1", 30491))
        self.state_machine.sock.recvfrom.return_value = mock_data
        self.assertTrue(self.state_machine.receive_find_service())

    def test_handle_initial_entry_main_phase(self):
        """Test main phase entry handling"""
        self.state_machine.state = "Ready"
        with patch.object(self.state_machine, 'send_offer_service') as mock_send:
            self.state_machine.handle_initial_entry_main_phase()
            mock_send.assert_called_once()
            self.assertIsNotNone(self.state_machine.timer)

    def test_handle_repetition_phase(self):
        """Test repetition phase handling"""
        self.state_machine.state = "Ready"
        self.state_machine.substate = "RepetitionPhase"
        self.state_machine.run = 0
        mock_data = (b"FindService", ("127.0.0.1", 30491))
        self.state_machine.sock.recvfrom.return_value = mock_data
    
        with patch.object(self.state_machine, 'send_offer_service') as mock_send:
            with patch.object(self.state_machine, 'receive_find_service', return_value=True):
                self.state_machine.handle_repetition_phase()
                mock_send.assert_called_once()

    def test_handle_ready_complete(self):
        """Test ready state handling with complete transitions"""
        # Initial setup
        self.state_machine.state = "Ready"
        self.state_machine.substate = "MainPhase"
        self.state_machine.ifstatus_up_and_configured = True
        self.state_machine.service_status_up = False

        # Mock socket operations
        mock_data = (b"FindService", ("127.0.0.1", 30491))
        self.state_machine.sock.recvfrom.return_value = mock_data

        # Test with mocked service
        with patch.object(self.state_machine, 'send_stop_offer_service') as mock_stop:
            with patch.object(self.state_machine, 'receive_find_service', return_value=False):
                self.state_machine.handle_ready()
                mock_stop.assert_called_once()
                self.assertEqual(self.state_machine.state, "NotReady")

if __name__ == '__main__':
    unittest.main()
