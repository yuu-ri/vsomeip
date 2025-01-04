import unittest
from unittest.mock import Mock, patch
import time
import threading
import socket  # Import the socket module
from src.ClientServiceStateMachine import ClientServiceStateMachine

class TestClientServiceStateMachine(unittest.TestCase):
    def setUp(self):
        self.state_machine = ClientServiceStateMachine()
        self.state_machine.sock = Mock()
        self.state_machine.sock.recvfrom = Mock()

    def tearDown(self):
        self.state_machine.stop()
        self.state_machine.sock.close()

    def wait_for_state(self, expected_state, expected_substate=None, timeout=2.0):
        """Wait for the state machine to reach the expected state and substate."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.state_machine.state == expected_state and (expected_substate is None or self.state_machine.substate == expected_substate):
                return True
            time.sleep(0.01)
        print(f"state {expected_state} and substate {expected_substate} not reached within {timeout} seconds.")
        print(f"Expected state {self.state_machine.state} and substate {self.state_machine.substate}")
        return False

    def test_handle_not_requested(self):
        """Test handle_not_requested state transitions"""
        # Ensure the start state is "NotRequested"
        self.state_machine.state = "NotRequested"

        # UML: NotRequested --> RequestedButNotReady : [Requested and ifstatus!=up_and_configured]
        self.state_machine.service_requested = True
        self.state_machine.ifstatus_up_and_configured = False
        self.state_machine.handle_not_requested()
        self.assertEqual(self.state_machine.state, "RequestedButNotReady")

  
    def test_handle_requested_but_not_ready(self):
        """Test handle_requested_but_not_ready state transitions"""
        # UML: RequestedButNotReady --> SearchingForService : [ifstatus=up_and_configured]
        self.state_machine.state = "RequestedButNotReady"
        self.state_machine.ifstatus_up_and_configured = True
        self.state_machine.handle_requested_but_not_ready()
        self.assertEqual(self.state_machine.state, "SearchingForService")

    def test_handle_searching_for_service(self):
        """Test handle_searching_for_service state transitions"""
        self.state_machine.sock.recvfrom.side_effect = [socket.timeout()]  # Prevent receiving offers
        self.state_machine.state = "SearchingForService"

        # UML: SearchingForService --> ServiceReady : [receive(OfferService)]
        self.state_machine.ifstatus_up_and_configured = True
        self.state_machine.sock.recvfrom.side_effect = [(b"OfferService", ("127.0.0.1", 30491))]
        self.state_machine.handle_searching_for_service()
        self.assertEqual(self.state_machine.state, "ServiceReady")

        # UML: SearchingForService --> RequestedButNotReady : [ifstatus!=up_and_configured]
        self.state_machine.state = "SearchingForService"
        self.state_machine.ifstatus_up_and_configured = False
        self.state_machine.sock.recvfrom.side_effect = [socket.timeout()]
        self.state_machine.handle_searching_for_service()
        self.assertEqual(self.state_machine.state, "RequestedButNotReady")

        # UML: SearchingForService:InitialWaitPhase --> RepetitionPhase : [Timer expired\nsend(FindService)]
        self.state_machine.state = "SearchingForService"
        self.state_machine.substate = "InitialWaitPhase"
        self.state_machine.ifstatus_up_and_configured = True
        self.state_machine.set_timer(0.1)
        time.sleep(0.2)
        self.state_machine.handle_searching_for_service()
        self.assertEqual(self.state_machine.substate, "RepetitionPhase")

        # UML: RepetitionPhase --> TimerSet2 : [REPETITONS_MAX>0] /run=0 \n setTimer(2^run * REPETITIONS_BASE_DELAY)
        self.state_machine.state = "SearchingForService"
        self.state_machine.substate = "RepetitionPhase"
        self.state_machine.run = 0
        self.state_machine.ifstatus_up_and_configured = True
        self.state_machine.set_timer(2 ** self.state_machine.run * self.state_machine.REPETITIONS_BASE_DELAY)
        self.assertEqual(self.state_machine.substate, "RepetitionPhase")

        # UML: TimerSet2 --> TimerSet2 : [Timer expired[run < REPETITIONS_MAX] \n send(FindService) \n run++ \n setTimer(2^run * REPETITIONS_BASE_DELAY)]
        self.state_machine.state = "SearchingForService"
        self.state_machine.substate = "RepetitionPhase"
        self.state_machine.run = 0
        self.state_machine.ifstatus_up_and_configured = True
        self.state_machine.set_timer(0.1)
        time.sleep(0.2)
        self.state_machine.handle_searching_for_service()
        self.assertEqual(self.state_machine.substate, "RepetitionPhase")
        self.assertEqual(self.state_machine.run, 1)

        # UML: SearchingForService:RepetitionPhase --> Stopped : [receive(StopOfferService)]
        self.state_machine.state = "SearchingForService"
        self.state_machine.substate = "RepetitionPhase"
        self.state_machine.ifstatus_up_and_configured = True
        self.state_machine.sock.recvfrom.side_effect = [
            (b"StopOfferService", ("127.0.0.1", 30491)),
            (b"StopOfferService", ("127.0.0.1", 30491)),
            (b"StopOfferService", ("127.0.0.1", 30491))
        ]
        self.state_machine.handle_searching_for_service()
        self.assertEqual(self.state_machine.state, "Stopped")

        # UML: SearchingForService:RepetitionPhase --> Stopped : [run>=REPETITIONS_MAX]
        self.state_machine.state = "SearchingForService"
        self.state_machine.substate = "RepetitionPhase"
        self.state_machine.run = self.state_machine.REPETITIONS_MAX
        self.state_machine.ifstatus_up_and_configured = True
        self.state_machine.set_timer(0.1)
        self.state_machine.sock.recvfrom.side_effect = [socket.timeout()]  # Prevent receiving offers
        time.sleep(0.2)
        self.state_machine.handle_searching_for_service()
        self.assertEqual(self.state_machine.state, "Stopped")

    def test_handle_service_ready(self):
        """Test handle_service_ready state transitions"""
        self.state_machine.state = "ServiceReady"
        self.state_machine.set_timer(0.1)
        self.state_machine.ifstatus_up_and_configured = True

        # UML: ServiceReady --> SearchingForService : [Timer expired]
        time.sleep(0.2)
        self.state_machine.sock.recvfrom.side_effect = [socket.timeout()]
        self.state_machine.handle_service_ready()
        self.assertEqual(self.state_machine.state, "SearchingForService")

        # Ensure the start state is "ServiceReady"
        self.state_machine.state = "ServiceReady"
        self.state_machine.ifstatus_up_and_configured = True

        # UML: ServiceReady --> ServiceReady : [receive(OfferService) \n resetTimer(TTL)]
        self.state_machine.sock.recvfrom.side_effect = [(b"OfferService", ("127.0.0.1", 30491))]
        self.state_machine.handle_service_ready()
        self.assertEqual(self.state_machine.state, "ServiceReady")
        self.assertIsNotNone(self.state_machine.timer)

        # UML: ServiceReady --> RequestedButNotReady : [ifstatus!=up_and_configured]
        self.state_machine.state = "ServiceReady"
        self.state_machine.ifstatus_up_and_configured = False
        self.state_machine.sock.recvfrom.side_effect = [socket.timeout()]
        self.state_machine.handle_service_ready()
        self.assertEqual(self.state_machine.state, "RequestedButNotReady")

        # UML: ServiceReady --> Stopped : [receive(StopOfferService)]
        self.state_machine.state = "ServiceReady"
        self.state_machine.ifstatus_up_and_configured = True
        self.state_machine.sock.recvfrom.side_effect = [
            (b"StopOfferService", ("127.0.0.1", 30491)),
            (b"StopOfferService", ("127.0.0.1", 30491)),
            (b"StopOfferService", ("127.0.0.1", 30491))
        ]
        self.state_machine.handle_service_ready()
        self.assertEqual(self.state_machine.state, "Stopped")

    def test_handle_stopped(self):
        """Test handle_stopped state transitions"""
        self.state_machine.state = "Stopped"

        # UML: Stopped --> NotRequested : [Service Not Requested]
        self.state_machine.service_requested = False
        self.state_machine.handle_stopped()
        self.assertEqual(self.state_machine.state, "NotRequested")

        # UML: Stopped --> ServiceReady : [receive(OfferService)]
        self.state_machine.service_requested = True
        self.state_machine.sock.recvfrom.side_effect = [(b"OfferService", ("127.0.0.1", 30491))]
        self.state_machine.handle_stopped()
        self.assertEqual(self.state_machine.state, "ServiceReady")

    def test_run_state_machine(self):
        """Test running the state machine through specific states"""
        self.state_machine.ifstatus_up_and_configured = False
        self.state_machine.service_requested = True

        # Start in NotRequested state
        self.state_machine.state = "NotRequested"
        thread = threading.Thread(target=self.state_machine.run_state_machine)
        thread.daemon = True
        thread.start()

        # Wait for state transitions
        self.assertTrue(self.wait_for_state("RequestedButNotReady"))

        # Simulate state transition to SearchingForService
        self.state_machine.ifstatus_up_and_configured = True
        self.assertTrue(self.wait_for_state("SearchingForService"))

        # Simulate state transition to ServiceReady
        self.state_machine.sock.recvfrom.side_effect = [(b"OfferService", ("127.0.0.1", 30491))]
        self.assertTrue(self.wait_for_state("ServiceReady"))

        # Simulate state transition to Stopped
        self.state_machine.sock.recvfrom.side_effect = [
            (b"StopOfferService", ("127.0.0.1", 30491)),
            (b"StopOfferService", ("127.0.0.1", 30491)),
            (b"StopOfferService", ("127.0.0.1", 30491))
        ]
        self.assertTrue(self.wait_for_state("Stopped"))

        # Simulate state transition from Stopped to ServiceReady
        self.state_machine.sock.recvfrom.side_effect = [(b"OfferService", ("127.0.0.1", 30491))]
        self.assertTrue(self.wait_for_state("ServiceReady"))

        # Simulate state transition from ServiceReady to Stopped again
        self.state_machine.sock.recvfrom.side_effect = [
            (b"StopOfferService", ("127.0.0.1", 30491)),
            (b"StopOfferService", ("127.0.0.1", 30491)),
            (b"StopOfferService", ("127.0.0.1", 30491))
        ]
        self.assertTrue(self.wait_for_state("Stopped"))

        # Simulate state transition from Stopped to NotRequested (ServiceNotSeen)
        self.state_machine.service_requested = False
        self.assertTrue(self.wait_for_state("NotRequested"))

        # Stop the state machine
        self.state_machine.stop()
        thread.join(timeout=0.1)

    def test_handle_searching_for_service_complete(self):
        """Test all branches of searching for service"""
        self.state_machine.sock.recvfrom.side_effect = [socket.timeout()]  # Prevent receiving offers
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

        # Test transition to Stopped when repetition expires and run >= REPETITIONS_MAX
        self.state_machine.sock.recvfrom.side_effect = [socket.timeout()]  # Prevent receiving offers
        self.state_machine.state = "SearchingForService"
        self.state_machine.substate = "RepetitionPhase"
        self.state_machine.run = self.state_machine.REPETITIONS_MAX
        self.state_machine.ifstatus_up_and_configured = True
        self.state_machine.set_timer(0.1)
        time.sleep(0.2)
        self.state_machine.handle_searching_for_service()
        self.assertEqual(self.state_machine.state, "Stopped")

        # Test transition within RepetitionPhase when timer expires and run < REPETITIONS_MAX
        self.state_machine.sock.recvfrom.side_effect = [socket.timeout()]  # Prevent receiving offers
        self.state_machine.state = "SearchingForService"
        self.state_machine.substate = "RepetitionPhase"
        self.state_machine.run = 0
        self.state_machine.ifstatus_up_and_configured = True
        self.state_machine.set_timer(0.1)
        time.sleep(0.2)
        self.state_machine.handle_searching_for_service()
        self.assertEqual(self.state_machine.state, "SearchingForService")
        self.assertEqual(self.state_machine.substate, "RepetitionPhase")
        self.assertEqual(self.state_machine.run, 1)

    def test_initial_wait_phase_to_repetition_phase(self):
        """Test transition from InitialWaitPhase to RepetitionPhase"""
        self.state_machine.sock.recvfrom.side_effect = [socket.timeout()]  # Prevent receiving offers
        self.state_machine.state = "SearchingForService"
        self.state_machine.substate = "InitialWaitPhase"
        
        # Set timer and wait for expiration
        self.state_machine.set_timer(0.1)
        time.sleep(0.2)
        
        # Mock socket for initial phase
        self.state_machine.sock.recvfrom.side_effect = [socket.timeout()]
        self.state_machine.handle_initial_wait_phase()
        self.assertEqual(self.state_machine.substate, "RepetitionPhase")

    def test_initial_state_to_initial_wait_phase(self):
        """Test transition from initial state to InitialWaitPhase and then to RepetitionPhase"""
        self.state_machine.sock.recvfrom.side_effect = [socket.timeout()]  # Prevent receiving offers
        self.state_machine.state = "Initial"
        self.state_machine.service_requested = True
        self.state_machine.ifstatus_up_and_configured = True

        # Start the state machine
        thread = threading.Thread(target=self.state_machine.run_state_machine)
        thread.daemon = True
        thread.start()

        # Wait for state transitions
        self.assertTrue(self.wait_for_state("SearchingForService"))
        self.assertEqual(self.state_machine.substate, "InitialWaitPhase")

        # Set timer and wait for expiration
        self.state_machine.set_timer(0.1)
        time.sleep(0.2)
        
        # Mock socket for initial phase
        self.state_machine.sock.recvfrom.side_effect = [socket.timeout()]
        self.state_machine.handle_initial_wait_phase()
        self.assertEqual(self.state_machine.substate, "RepetitionPhase")

        # Stop the state machine
        self.state_machine.stop()
        thread.join(timeout=0.1)

    def test_initial_state_to_initial_wait_phase_to_repetition_phase(self):
        """Test transition from initial state to InitialWaitPhase and then to RepetitionPhase"""
        self.state_machine.sock.recvfrom.side_effect = [socket.timeout()]  # Prevent receiving offers
        self.state_machine.state = "Initial"
        self.state_machine.service_requested = True
        self.state_machine.ifstatus_up_and_configured = True

        # Start the state machine
        thread = threading.Thread(target=self.state_machine.run_state_machine)
        thread.daemon = True
        thread.start()

        # Wait for state transitions
        self.assertTrue(self.wait_for_state("SearchingForService", "InitialWaitPhase"))
        # Mock socket for initial phase
        # Set timer and wait for expiration
        self.state_machine.set_timer(0.1)
        self.state_machine.sock.recvfrom.side_effect = [socket.timeout()]
        #self.state_machine.handle_initial_wait_phase()
        self.assertTrue(self.wait_for_state("SearchingForService", "RepetitionPhase"))
       

        # Stop the state machine
        self.state_machine.stop()
        thread.join(timeout=0.1)

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

    def test_receive_stop_offer_service(self):
        """Test receiving StopOfferService message"""
        # Set up mock for successful reception
        self.state_machine.sock.recvfrom.side_effect = None  # Clear previous side effects
        self.state_machine.sock.recvfrom.return_value = (b"StopOfferService", ("127.0.0.1", 30491))
        self.assertTrue(self.state_machine.receive_stop_offer_service())

        # Set up mock for timeout
        self.state_machine.sock.recvfrom.side_effect = socket.timeout()
        self.assertFalse(self.state_machine.receive_stop_offer_service())

    def test_initial_state_transitions(self):
        """Test initial state transitions according to UML diagram"""
        # Ensure the start state is "Initial"
        self.state_machine.state = "Initial"

        # UML: [*] --> NotRequested : [Service Not Requested]
        self.state_machine.service_requested = False
        self.state_machine.ifstatus_up_and_configured = False
        self.state_machine.handle_initial()
        self.assertEqual(self.state_machine.state, "NotRequested")

        # Reset to "Initial" state
        self.state_machine.state = "Initial"

        # UML: [*] --> RequestedButNotReady : [Requested and ifstatus!=up_and_configured]
        self.state_machine.service_requested = True
        self.state_machine.ifstatus_up_and_configured = False
        self.state_machine.handle_initial()
        self.assertEqual(self.state_machine.state, "RequestedButNotReady")

        # Reset to "Initial" state
        self.state_machine.state = "Initial"

        # UML: [*] --> SearchingForService : ServiceRequested\nand if-status=up_and_configured
        self.state_machine.service_requested = True
        self.state_machine.ifstatus_up_and_configured = True
        self.state_machine.handle_initial()
        self.assertEqual(self.state_machine.state, "SearchingForService")

    def test_initial_state_to_initial_wait_phase(self):
        """Test transition from initial state to InitialWaitPhase and then to RepetitionPhase"""
        self.state_machine.sock.recvfrom.side_effect = [socket.timeout()]  # Prevent receiving offers
        self.state_machine.state = "Initial"
        self.state_machine.service_requested = True

        # Start the state machine
        thread = threading.Thread(target=self.state_machine.run_state_machine)
        thread.daemon = True
        thread.start()

        # Wait for state transitions
        self.assertTrue(self.wait_for_state("RequestedButNotReady"))
        self.state_machine.ifstatus_up_and_configured = True
        self.assertTrue(self.wait_for_state("SearchingForService", "InitialWaitPhase"))

        # Set timer and wait for expiration
        self.state_machine.set_timer(0.1)
        time.sleep(0.2)
        
        # Mock socket for initial phase
        self.state_machine.sock.recvfrom.side_effect = [socket.timeout()]
        self.state_machine.handle_initial_wait_phase()
        self.assertTrue(self.wait_for_state("SearchingForService", "RepetitionPhase"))

        # Stop the state machine
        self.state_machine.stop()
        thread.join(timeout=0.1)

    def test_handle_not_requested(self):
        """Test handle_not_requested state transitions"""
        # UML: NotRequested --> RequestedButNotReady : [Requested and ifstatus!=up_and_configured]
        self.state_machine.service_requested = True
        self.state_machine.ifstatus_up_and_configured = False
        self.state_machine.handle_not_requested()
        self.assertEqual(self.state_machine.state, "RequestedButNotReady")

    def test_handle_service_not_seen(self):
        """Test handle_service_not_seen state transitions"""
        self.state_machine.state = "NotRequested"
        self.state_machine.substate = "ServiceNotSeen"

        # UML: ServiceNotSeen --> ServiceSeen : [receive(OfferService) /setTimer(TTL)]
        self.state_machine.sock.recvfrom.side_effect = [(b"OfferService", ("127.0.0.1", 30491))]
        self.state_machine.handle_service_not_seen()
        self.assertEqual(self.state_machine.substate, "ServiceSeen")
        self.assertIsNotNone(self.state_machine.timer)

    def test_handle_service_seen(self):
        """Test handle_service_seen state transitions"""
        # Ensure the start state is "ServiceSeen"
        self.state_machine.state = "NotRequested"
        self.state_machine.substate = "ServiceSeen"

        # UML: ServiceSeen --> ServiceNotSeen : [ifstatus!=up_and_configured]
        self.state_machine.ifstatus_up_and_configured = False
        self.state_machine.handle_service_seen()
        self.assertEqual(self.state_machine.substate, "ServiceNotSeen")

        # Ensure the start state is "ServiceSeen"
        self.state_machine.state = "NotRequested"
        self.state_machine.substate = "ServiceSeen"

        # UML: ServiceSeen --> ServiceNotSeen : [Timer expired (TTL)]
        self.state_machine.ifstatus_up_and_configured = True
        self.state_machine.set_timer(0.1)
        time.sleep(0.2)
        self.state_machine.handle_service_seen()
        self.assertEqual(self.state_machine.substate, "ServiceNotSeen")

        # Ensure the start state is "ServiceSeen"
        self.state_machine.state = "NotRequested"
        self.state_machine.substate = "ServiceSeen"

        # UML: ServiceSeen --> ServiceNotSeen : [receive(Offer)]
        self.state_machine.set_timer(0.1)
        self.state_machine.sock.recvfrom.side_effect = [(b"Offer", ("127.0.0.1", 30491)), (b"StopOfferService", ("127.0.0.1", 30491))]
        self.state_machine.handle_service_seen()
        self.assertEqual(self.state_machine.substate, "ServiceNotSeen")

        # Ensure the start state is "ServiceSeen"
        self.state_machine.state = "NotRequested"
        self.state_machine.substate = "ServiceSeen"

        # UML: ServiceSeen --> ServiceSeen : [receive(OfferService) /setTimer(TTL)]
        self.state_machine.set_timer(0.1)
        self.state_machine.sock.recvfrom.side_effect = [(b"OfferService", ("127.0.0.1", 30491))]
        self.state_machine.handle_service_seen()
        self.assertEqual(self.state_machine.substate, "ServiceSeen")
        self.assertIsNotNone(self.state_machine.timer)

        # Ensure the start state is "ServiceSeen"
        self.state_machine.state = "NotRequested"
        self.state_machine.substate = "ServiceSeen"

        # UML: ServiceSeen --> ServiceReady : [InternalServiceRequest and ifstatus==up_and_configured]
        self.state_machine.service_requested = True
        self.state_machine.ifstatus_up_and_configured = True
        self.state_machine.handle_service_seen()
        self.assertEqual(self.state_machine.substate, "ServiceReady")

if __name__ == '__main__':
    unittest.main()
