"""Integration of the programming gate with existing display/car/control routes."""
import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException
import main
import car_api
from test_host_bridge import fixture


class ProgrammingGuardTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.assertIsNotNone(getattr(main, 'firmware_service', None), '后台未接入下载排他门')
        self.patch = patch.object(main.firmware_service, '_scanning', True)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    async def test_programming_blocks_motion_without_contacting_host_but_stop_remains_once(self):
        client = Mock()
        client.status.return_value = fixture()
        client.command.return_value = dict(request_id='stop', state='accepted')
        with patch.object(main, 'HostClient', return_value=client):
            with self.assertRaises(HTTPException):
                await main.command(main.Command(action='run', request_id='motion'))
            client.status.assert_not_called()
            result = await main.command(main.Command(action='stop', request_id='stop'))
        self.assertEqual(result['state'], 'accepted')
        client.command.assert_called_once()

    async def test_snapshot_cannot_show_cached_online_during_programming(self):
        old = dict(main.hub.latest, connected=True, synced=True, host_online=True,
                   status_fresh=True, display_fresh=True, angle_deg=12)
        with patch.object(main.hub, 'latest', old):
            state = main.snapshot()['latest']
        self.assertTrue(state['programming']['busy'])
        self.assertFalse(state['status_fresh'])
        self.assertIsNone(state['angle_deg'])

    async def test_car_motion_is_blocked_but_stop_and_disconnect_available(self):
        service = Mock()
        with patch.object(car_api, 'service', service):
            with self.assertRaises(HTTPException):
                car_api.connect(car_api.ConnectBody(device_id='fixture'))
            service.connect.assert_not_called()
            car_api.stop(car_api.SessionBody(session='fixture'))
            car_api.disconnect(car_api.SessionBody(session='fixture'))
        service.stop.assert_called_once()
        service.disconnect.assert_called_once()

    async def test_config_change_is_blocked_without_replacing_config(self):
        with patch.object(main, 'CONFIG_PATH') as path:
            with self.assertRaises(HTTPException):
                await main.update_config(main.ConfigUpdate(bridge_port=8371, firmware_variant='V5'))
        path.with_suffix.assert_not_called()

    async def test_task_admitted_during_conversion_cannot_publish_old_online_state(self):
        from host_bridge import empty_state
        main.firmware_service._scanning = False
        hub = main.Hub()
        client = Mock()
        client.status.return_value = fixture()
        def convert(*args, **kwargs):
            main.firmware_service._scanning = True
            return dict(empty_state(), status_fresh=True, host_online=True), [], False
        hub.adapter.observe = convert
        with patch.object(main, 'HostClient', return_value=client):
            await hub.poll_once()
        self.assertFalse(hub.latest['status_fresh'])


if __name__ == '__main__':
    unittest.main()
