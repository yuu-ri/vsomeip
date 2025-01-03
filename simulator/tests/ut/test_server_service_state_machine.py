import unittest
from unittest.mock import Mock, patch
import time
import threading
import socket
from src.ServerServiceStateMachine import ServerServiceStateMachine

class TestServerServiceStateMachine(unittest.TestCase):
    def setUp(self):
        self.state_machine = ServerServiceStateMachine()
        self.state_machine.sock = Mock()

    def tearDown(self):
        self.state_machine.stop()
        self.state_machine.sock.close()

    def test_initial_state(self):
        """Test initial state configuration"""
        self.assertEqual(self.state_machine.state, "NotReady")
        self.assertIsNone(self.state_machine.substate)
        self.assertFalse(self.state_machine.ifstatus_up_and_configured)
        self.assertFalse(self.state_machine.service_status_up)

    def test_transition_to_ready(self):
        """Test transition from NotReady to Ready"""
        self.state_machine.ifstatus_up_and_configured = True
        self.state_machine.service_status_up = True
        self.state_machine.handle_not_ready()
        self.assertEqual(self.state_machine.state, "Ready")
        self.assertEqual(self.state_machine.substate, "InitialWaitPhase")

    def test_initial_wait_phase(self):
        """Test InitialWaitPhase timer and transition"""
        self.state_machine.state = "Ready"
        self.state_machine.substate = "InitialWaitPhase"
        self.state_machine.set_timer(0.1)
        time.sleep(0.2)
        self.state_machine.handle_initial_wait_phase()
        self.assertEqual(self.state_machine.substate, "RepetitionPhase")

    def test_repetition_phase(self):
        """Test RepetitionPhase timer and transitions"""
        self.state_machine.state = "Ready"
        self.state_machine.substate = "RepetitionPhase"
        self.state_machine.run = 0
        self.state_machine.set_timer(0.1)
        
        with patch.object(self.state_machine, 'send_offer_service') as mock_send:
            with patch.object(self.state_machine, 'receive_find_service', return_value=False):
                time.sleep(0.2)
                self.state_machine.handle_repetition_phase()
                mock_send.assert_called_once()
                self.assertEqual(self.state_machine.run, 1)
                self.assertTrue(self.state_machine.timer > time.time())

    def test_main_phase(self):
        """Test MainPhase timer and transitions"""
        self.state_machine.state = "Ready"
        self.state_machine.substate = "MainPhase"
        self.state_machine.set_timer(0.1)
        
        with patch.object(self.state_machine, 'send_offer_service') as mock_send:
            with patch.object(self.state_machine, 'receive_find_service', return_value=False):
                time.sleep(0.2)
                self.state_machine.handle_main_phase()
                mock_send.assert_called_once()
                self.assertTrue(self.state_machine.timer > time.time())

    def test_receive_find_service(self):
        """Test receiving FindService message"""
        self.state_machine.sock.recvfrom.return_value = (b"FindService", ("127.0.0.1", 30491))
        self.assertTrue(self.state_machine.receive_find_service())

    def test_run_state_machine(self):
        """Test running the state machine"""
        self.state_machine.ifstatus_up_and_configured = True
        self.state_machine.service_status_up = True
        self.state_machine.state = "Ready"
        self.state_machine.substate = "InitialWaitPhase"
        
        def change_ifstatus():
            time.sleep(0.1)
            self.state_machine.ifstatus_up_and_configured = False  # Simulate condition to transition to NotReady

        thread = threading.Thread(target=self.state_machine.run_state_machine)
        thread.daemon = True
        thread.start()

        change_thread = threading.Thread(target=change_ifstatus)
        change_thread.start()
        change_thread.join()

        time.sleep(0.2)
        self.state_machine.stop()
        thread.join(timeout=0.1)

        self.assertEqual(self.state_machine.state, "NotReady")

    def test_run_state_machine_stop(self):
        """Test stopping the state machine"""
        self.state_machine.ifstatus_up_and_configured = True
        self.state_machine.service_status_up = True
        self.state_machine.state = "Ready"
        self.state_machine.substate = "InitialWaitPhase"
        
        thread = threading.Thread(target=self.state_machine.run_state_machine)
        thread.daemon = True
        thread.start()

        time.sleep(0.1)
        self.state_machine.stop()
        thread.join(timeout=0.1)

    def test_handle_ready_ifstatus_down(self):
        """Test transition from Ready to NotReady when ifstatus_up_and_configured is False"""
        self.state_machine.state = "Ready"
        self.state_machine.ifstatus_up_and_configured = False
        self.state_machine.handle_ready()
        self.assertEqual(self.state_machine.state, "NotReady")

    def test_handle_ready_service_status_down(self):
        """Test transition from Ready to NotReady when service_status_up is False"""
        self.state_machine.state = "Ready"
        self.state_machine.service_status_up = False
        self.state_machine.ifstatus_up_and_configured = True
        
        with patch.object(self.state_machine, 'send_stop_offer_service') as mock_stop:
            self.state_machine.handle_ready()
            mock_stop.assert_called_once()
            self.assertEqual(self.state_machine.state, "NotReady")

    def test_clear_all_timers(self):
        """Test clear_all_timers method"""
        self.state_machine.timer = time.time() + 1
        self.state_machine.run = 5
        self.state_machine.clear_all_timers()
        self.assertIsNone(self.state_machine.timer)
        self.assertEqual(self.state_machine.run, 0)

    def test_handle_initial_entry_ready(self):
        """Test handle_initial_entry_ready method"""
        self.state_machine.handle_initial_entry_ready()
        self.assertEqual(self.state_machine.substate, "InitialWaitPhase")
        self.assertTrue(self.state_machine.timer > time.time())

    def test_handle_initial_wait_phase(self):
        """Test handle_initial_wait_phase method"""
        self.state_machine.state = "Ready"
        self.state_machine.substate = "InitialWaitPhase"
        self.state_machine.set_timer(0.1)
        time.sleep(0.2)
        self.state_machine.handle_initial_wait_phase()
        self.assertEqual(self.state_machine.substate, "RepetitionPhase")
        self.assertTrue(self.state_machine.timer > time.time())

    def test_handle_repetition_phase_find_service(self):
        """Test handle_repetition_phase method with FindService reception"""
        self.state_machine.state = "Ready"
        self.state_machine.substate = "RepetitionPhase"
        self.state_machine.run = 0
        
        with patch.object(self.state_machine, 'receive_find_service', return_value=True):
            with patch.object(self.state_machine, 'wait_and_send_offer_service') as mock_wait_send:
                self.state_machine.handle_repetition_phase()
                mock_wait_send.assert_called_once()

    def test_handle_repetition_phase_timer_expired(self):
        """Test handle_repetition_phase method with timer expiration"""
        self.state_machine.state = "Ready"
        self.state_machine.substate = "RepetitionPhase"
        self.state_machine.run = 0
        self.state_machine.set_timer(0.1)
        
        with patch.object(self.state_machine, 'send_offer_service') as mock_send:
            with patch.object(self.state_machine, 'receive_find_service', return_value=False):
                time.sleep(0.2)
                self.state_machine.handle_repetition_phase()
                mock_send.assert_called_once()
                self.assertEqual(self.state_machine.run, 1)
                self.assertTrue(self.state_machine.timer > time.time())

    def test_handle_repetition_phase_to_main_phase(self):
        """Test handle_repetition_phase method transition to MainPhase"""
        self.state_machine.state = "Ready"
        self.state_machine.substate = "RepetitionPhase"
        self.state_machine.run = self.state_machine.REPETITIONS_MAX
        self.state_machine.set_timer(0.1)
        
        with patch.object(self.state_machine, 'send_offer_service') as mock_send:
            with patch.object(self.state_machine, 'receive_find_service', return_value=False):
                time.sleep(0.2)
                self.state_machine.handle_repetition_phase()
                mock_send.assert_called_once()
                self.assertEqual(self.state_machine.substate, "MainPhase")
                self.assertTrue(self.state_machine.timer > time.time())

    def test_handle_main_phase_timer_expired(self):
        """Test handle_main_phase method with timer expiration"""
        self.state_machine.state = "Ready"
        self.state_machine.substate = "MainPhase"
        self.state_machine.set_timer(0.1)
        
        with patch.object(self.state_machine, 'send_offer_service') as mock_send:
            with patch.object(self.state_machine, 'receive_find_service', return_value=False):
                time.sleep(0.2)
                self.state_machine.handle_main_phase()
                mock_send.assert_called_once()
                self.assertTrue(self.state_machine.timer > time.time())

    def test_handle_main_phase_find_service(self):
        """Test handle_main_phase method with FindService reception"""
        self.state_machine.state = "Ready"
        self.state_machine.substate = "MainPhase"
        
        with patch.object(self.state_machine, 'receive_find_service', return_value=True):
            with patch.object(self.state_machine, 'wait_and_send_offer_service') as mock_wait_send:
                self.state_machine.handle_main_phase()
                mock_wait_send.assert_called_once()

    def test_handle_not_ready(self):
        """Test handle_not_ready method"""
        self.state_machine.ifstatus_up_and_configured = True
        self.state_machine.service_status_up = True
        self.state_machine.handle_not_ready()
        self.assertEqual(self.state_machine.state, "Ready")
        self.assertEqual(self.state_machine.substate, "InitialWaitPhase")

    def test_set_timer(self):
        """Test set_timer method"""
        self.state_machine.set_timer(0.1)
        self.assertTrue(self.state_machine.timer > time.time())

    def test_timer_expired(self):
        """Test timer_expired method"""
        self.state_machine.set_timer(0.1)
        time.sleep(0.2)
        self.assertTrue(self.state_machine.timer_expired())

    def test_send_stop_offer_service(self):
        """Test send_stop_offer_service method"""
        self.state_machine.send_stop_offer_service()
        self.state_machine.sock.sendto.assert_called_once_with(b"StopOfferService", (self.state_machine.udp_ip, self.state_machine.udp_port))

    def test_wait_and_send_offer_service(self):
        """Test wait_and_send_offer_service method"""
        with patch('time.sleep', return_value=None):
            self.state_machine.wait_and_send_offer_service()
            self.state_machine.sock.sendto.assert_called_once_with(b"OfferService", (self.state_machine.udp_ip, self.state_machine.udp_port))

    def test_receive_find_service_timeout(self):
        """Test receive_find_service method with timeout"""
        self.state_machine.sock.recvfrom.side_effect = socket.timeout
        self.assertFalse(self.state_machine.receive_find_service())

    def test_handle_ready(self):
        """Test handle_ready method with all conditions"""
        self.state_machine.state = "Ready"
        self.state_machine.ifstatus_up_and_configured = False
        self.state_machine.handle_ready()
        self.assertEqual(self.state_machine.state, "NotReady")

        self.state_machine.state = "Ready"
        self.state_machine.ifstatus_up_and_configured = True
        self.state_machine.service_status_up = False
        with patch.object(self.state_machine, 'send_stop_offer_service') as mock_stop:
            self.state_machine.handle_ready()
            mock_stop.assert_called_once()
            self.assertEqual(self.state_machine.state, "NotReady")

        self.state_machine.state = "Ready"
        self.state_machine.ifstatus_up_and_configured = True
        self.state_machine.service_status_up = True
        self.state_machine.substate = "InitialWaitPhase"
        with patch.object(self.state_machine, 'handle_initial_wait_phase') as mock_initial:
            self.state_machine.handle_ready()
            mock_initial.assert_called_once()

        self.state_machine.state = "Ready"
        self.state_machine.ifstatus_up_and_configured = True
        self.state_machine.service_status_up = True
        self.state_machine.substate = "RepetitionPhase"
        with patch.object(self.state_machine, 'handle_repetition_phase') as mock_repetition:
            self.state_machine.handle_ready()
            mock_repetition.assert_called_once()

        self.state_machine.state = "Ready"
        self.state_machine.ifstatus_up_and_configured = True
        self.state_machine.service_status_up = True
        self.state_machine.substate = "MainPhase"
        with patch.object(self.state_machine, 'handle_main_phase') as mock_main:
            self.state_machine.handle_ready()
            mock_main.assert_called_once()

if __name__ == '__main__':
    unittest.main()