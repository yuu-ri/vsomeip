import unittest
from unittest.mock import Mock, patch
import time
import threading
import socket
from src.ClientServiceStateMachine import ClientServiceStateMachine

class TestClientServiceStateMachine(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures"""
        self.state_machine = ClientServiceStateMachine()
        self.state_machine.sock = Mock()
        self.state_machine.sock.recvfrom = Mock()

    def tearDown(self):
        """Tear down test fixtures"""
        self.state_machine.stop()
        self.state_machine.sock.close()

    def test_initial_state(self):
        """Test initial state configuration"""
        self.assertEqual(self.state_machine.state, "NotRequested")
        self.assertIsNone(self.state_machine.substate)
        self.assertFalse(self.state_machine.ifstatus_up_and_configured)
        self.assertFalse(self.state_machine.service_requested)

    def test_transition_to_requested_but_not_ready(self):
        """Test transition from NotRequested to RequestedButNotReady"""
        self.state_machine.ifstatus_up_and_configured = False
        self.state_machine.service_requested = True
        self.state_machine.handle_not_requested()
        self.assertEqual(self.state_machine.state, "RequestedButNotReady")

    def test_transition_to_searching_for_service(self):
        """Test transition from RequestedButNotReady to SearchingForService"""
        self.state_machine.ifstatus_up_and_configured = True
        self.state_machine.handle_requested_but_not_ready()
        self.assertEqual(self.state_machine.state, "SearchingForService")
        self.assertEqual(self.state_machine.substate, "InitialWaitPhase")

    def test_initial_wait_phase(self):
        """Test InitialWaitPhase timer and transition"""
        self.state_machine.state = "SearchingForService"
        self.state_machine.substate = "InitialWaitPhase"
        self.state_machine.set_timer(0.1)
        time.sleep(0.2)
        self.state_machine.handle_initial_wait_phase()
        self.assertEqual(self.state_machine.substate, "RepetitionPhase")

    def test_repetition_phase(self):
        """Test RepetitionPhase timer and transitions"""
        self.state_machine.state = "SearchingForService"
        self.state_machine.substate = "RepetitionPhase"
        self.state_machine.run = 0
        self.state_machine.set_timer(0.1)
        
        with patch.object(self.state_machine, 'send_find_service') as mock_send:
            with patch.object(self.state_machine, 'receive_stop_offer_service', return_value=False):
                time.sleep(0.2)
                self.state_machine.handle_repetition_phase()
                mock_send.assert_called_once()
                self.assertEqual(self.state_machine.run, 1)
                self.assertTrue(self.state_machine.timer > time.time())

    def test_repetition_phase_to_stopped(self):
        """Test RepetitionPhase transition to Stopped"""
        self.state_machine.state = "SearchingForService"
        self.state_machine.substate = "RepetitionPhase"
        self.state_machine.run = self.state_machine.REPETITIONS_MAX
        self.state_machine.set_timer(0.1)
        
        with patch.object(self.state_machine, 'send_find_service') as mock_send:
            with patch.object(self.state_machine, 'receive_stop_offer_service', return_value=False):
                time.sleep(0.2)
                self.state_machine.handle_repetition_phase()
                self.assertEqual(self.state_machine.state, "Stopped")

    def test_receive_offer_service(self):
        """Test receiving OfferService message"""
        self.state_machine.sock.recvfrom.return_value = (b"OfferService", ("127.0.0.1", 30491))
        self.assertTrue(self.state_machine.receive_offer_service())

    def test_run_state_machine(self):
        """Test running the state machine through specific states"""
        self.state_machine.ifstatus_up_and_configured = True
        self.state_machine.service_requested = True

        # Start in NotRequested state
        self.state_machine.state = "NotRequested"
        thread = threading.Thread(target=self.state_machine.run_state_machine)
        thread.daemon = True
        thread.start()
        self.state_machine.ifstatus_up_and_configured = False
        # Allow some time for state transitions
        time.sleep(0.1)

        # Check if state transitioned to RequestedButNotReady
        self.assertEqual(self.state_machine.state, "RequestedButNotReady")

        # Simulate state transition to SearchingForService
        self.state_machine.ifstatus_up_and_configured = True
        time.sleep(0.2)
        self.state_machine.set_timer(0.2)
        self.assertEqual(self.state_machine.state, "SearchingForService")
        self.state_machine.set_timer(0.2)
        # Simulate state transition to ServiceReady
        self.state_machine.sock.recvfrom.side_effect = [(b"OfferService", ("127.0.0.1", 30491)),(b"OfferService", ("127.0.0.1", 30491))]
        time.sleep(0.5)
        self.assertEqual(self.state_machine.state, "ServiceReady")

        # Simulate state transition to Stopped
        self.state_machine.sock.recvfrom.side_effect = [(b"StopOfferService", ("127.0.0.1", 30491)), (b"StopOfferService", ("127.0.0.1", 30491)), (b"StopOfferService", ("127.0.0.1", 30491))]
        time.sleep(0.4)  # Allow more time for state transition
        self.assertEqual(self.state_machine.state, "Stopped")

        # Stop the state machine
        self.state_machine.stop()
        thread.join(timeout=0.1)

    def test_handle_service_ready(self):
        """Test handling ServiceReady state"""
        self.state_machine.state = "ServiceReady"
        self.state_machine.set_timer(0.1)
        
        with patch.object(self.state_machine, 'receive_offer_service', return_value=True):
            self.state_machine.handle_service_ready()
            self.assertTrue(self.state_machine.timer > time.time())

        with patch.object(self.state_machine, 'receive_offer_service', return_value=False):
            time.sleep(0.2)
            self.state_machine.handle_service_ready()
            self.assertEqual(self.state_machine.state, "RequestedButNotReady")

    def test_handle_stopped(self):
        """Test handling Stopped state"""
        self.state_machine.state = "Stopped"
        self.state_machine.service_requested = False
        self.state_machine.handle_stopped()
        self.assertEqual(self.state_machine.state, "NotRequested")
        self.assertEqual(self.state_machine.substate, "ServiceNotSeen")

        self.state_machine.service_requested = True
        with patch.object(self.state_machine, 'receive_offer_service', return_value=True):
            self.state_machine.handle_stopped()
            self.assertTrue(self.state_machine.timer > time.time())

    def test_receive_stop_offer_service(self):
        """Test receiving StopOfferService message"""
        # Set up mock for successful reception
        self.state_machine.sock.recvfrom.side_effect = None  # Clear previous side effects
        self.state_machine.sock.recvfrom.return_value = (b"StopOfferService", ("127.0.0.1", 30491))
        self.assertTrue(self.state_machine.receive_stop_offer_service())

        # Set up mock for timeout
        self.state_machine.sock.recvfrom.side_effect = socket.timeout()
        self.assertFalse(self.state_machine.receive_stop_offer_service())

    def test_handle_repetition_phase_complete(self):
        """Test all branches of repetition phase"""
        self.state_machine.state = "SearchingForService"
        self.state_machine.substate = "RepetitionPhase"
        
        # Test normal repetition
        self.state_machine.run = 0
        self.state_machine.set_timer(0.1)
        time.sleep(0.2)
        self.state_machine.sock.recvfrom.side_effect = [socket.timeout()]
        self.state_machine.handle_repetition_phase()
        self.assertEqual(self.state_machine.run, 1)

        # Test max repetitions reached
        self.state_machine.run = self.state_machine.REPETITIONS_MAX
        self.state_machine.set_timer(0.1)
        time.sleep(0.2)
        self.state_machine.sock.recvfrom.side_effect = [socket.timeout()]
        self.state_machine.handle_repetition_phase()
        self.assertEqual(self.state_machine.state, "Stopped")

        # Test stop offer received
        self.state_machine.state = "SearchingForService"
        self.state_machine.sock.recvfrom.side_effect = [(b"StopOfferService", ("127.0.0.1", 30491)), (b"StopOfferService", ("127.0.0.1", 30491))]
        self.state_machine.set_timer(0.1)
        self.state_machine.handle_repetition_phase()
        self.assertEqual(self.state_machine.state, "Stopped")
        self.state_machine.set_timer(0)
        
    def test_handle_searching_for_service_complete(self):
        """Test all branches of searching for service"""
        self.state_machine.state = "SearchingForService"
        self.state_machine.substate = "InitialWaitPhase"
        
        # Set timer and wait for expiration
        self.state_machine.set_timer(0.1)
        time.sleep(0.2)
        
        # Mock socket for initial phase
        self.state_machine.sock.recvfrom.side_effect = [socket.timeout()]
        self.state_machine.handle_initial_wait_phase()
        self.assertEqual(self.state_machine.substate, "RepetitionPhase")

        # Test ifstatus changed
        self.state_machine.state = "SearchingForService"
        self.state_machine.ifstatus_up_and_configured = False
        self.state_machine.sock.recvfrom.side_effect = [socket.timeout()]  # Prevent OfferService reception
        self.state_machine.handle_searching_for_service()
        self.assertEqual(self.state_machine.state, "RequestedButNotReady")

        # Test offer service received
        self.state_machine.state = "SearchingForService"
        self.state_machine.ifstatus_up_and_configured = True
        self.state_machine.sock.recvfrom.side_effect = None
        self.state_machine.sock.recvfrom.return_value = (b"OfferService", ("127.0.0.1", 30491))
        self.state_machine.handle_searching_for_service()
        self.assertEqual(self.state_machine.state, "ServiceReady")

    def test_handle_service_ready_complete(self):
        """Test all branches of service ready state"""
        self.state_machine.state = "ServiceReady"
        self.state_machine.set_timer(0.1)
        self.state_machine.ifstatus_up_and_configured = True

        # Test offer service received
        self.state_machine.sock.recvfrom.side_effect = [(b"OfferService", ("127.0.0.1", 30491))]
        self.state_machine.handle_service_ready()
        self.assertTrue(self.state_machine.timer > time.time())

        # Test timer expired
        self.state_machine.set_timer(0.1)
        time.sleep(0.2)
        self.state_machine.sock.recvfrom.side_effect = [socket.timeout()]
        self.state_machine.handle_service_ready()
        self.assertEqual(self.state_machine.state, "SearchingForService")

        # Test ifstatus changed
        self.state_machine.state = "ServiceReady"
        self.state_machine.ifstatus_up_and_configured = False
        self.state_machine.sock.recvfrom.side_effect = [socket.timeout()]
        self.state_machine.handle_service_ready()
        self.assertEqual(self.state_machine.state, "RequestedButNotReady")

        # Test stop offer received
        self.state_machine.state = "ServiceReady"
        self.state_machine.ifstatus_up_and_configured = True
        self.state_machine.sock.recvfrom.side_effect = [
            (b"StopOfferService", ("127.0.0.1", 30491)),
            (b"StopOfferService", ("127.0.0.1", 30491)),  # Provide multiple stop offers
            socket.timeout()  # Ensure there's enough side effects to handle all calls
        ]
        self.state_machine.handle_service_ready()
        self.assertEqual(self.state_machine.state, "Stopped")

    def test_run_state_machine_complete(self):
        """Test all states in run_state_machine"""
        states_to_test = ["NotRequested", "RequestedButNotReady", "SearchingForService", 
                          "ServiceReady", "Stopped"]
        
        for state in states_to_test:
            self.state_machine.state = state
            thread = threading.Thread(target=self.state_machine.run_state_machine)
            thread.daemon = True
            thread.start()
            time.sleep(0.2)
            self.state_machine.stop()
            thread.join(timeout=0.1)
            self.assertTrue(self.state_machine.state in states_to_test)

    def test_handle_not_requested(self):
        """Test handle_not_requested state transitions"""
        # Test transition to RequestedButNotReady when ifstatus is not up and configured
        self.state_machine.service_requested = True
        self.state_machine.ifstatus_up_and_configured = False
        self.state_machine.handle_not_requested()
        self.assertEqual(self.state_machine.state, "RequestedButNotReady")

        # Test transition to NotRequested when ifstatus is up and configured
        self.state_machine.ifstatus_up_and_configured = True
        self.state_machine.handle_not_requested()
        self.assertEqual(self.state_machine.state, "NotRequested")

        # Test transition to NotRequested when service is not requested
        self.state_machine.service_requested = False
        self.state_machine.handle_not_requested()
        self.assertEqual(self.state_machine.state, "NotRequested")

if __name__ == '__main__':
    unittest.main()