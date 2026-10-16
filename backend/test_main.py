import asyncio
import unittest
from unittest.mock import Mock, patch
from fastapi import HTTPException

import main
from host_bridge import BridgeError
from test_host_bridge import fixture


class ApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_explicit_command_is_forwarded_once_and_keeps_host_state(self):
        client=Mock(); client.status.return_value=fixture(); client.command.return_value=dict(state='accepted',request_id='one')
        with patch.object(main,'HostClient',return_value=client):
            result=await main.command(main.Command(action='run',request_id='one'))
        self.assertEqual(result['state'],'accepted')
        client.command.assert_called_once_with(dict(action='run',request_id='one'))

    async def test_identity_failure_never_forwards_a_mutation(self):
        client=Mock(); client.status.return_value=dict(fixture(),schema='wrong')
        with patch.object(main,'HostClient',return_value=client):
            with self.assertRaises(HTTPException): await main.command(main.Command(action='run',request_id='one'))
        client.command.assert_not_called()

    async def test_command_timeout_reports_unknown_with_request_id_without_retry(self):
        client=Mock(); client.status.return_value=fixture(); client.command.side_effect=BridgeError('timeout')
        with patch.object(main,'HostClient',return_value=client):
            with self.assertRaises(HTTPException) as context:
                await main.command(main.Command(action='stop',request_id='keep-this-id'))
        self.assertEqual(context.exception.detail['request_id'],'keep-this-id')
        self.assertEqual(context.exception.detail['state'],'indeterminate')
        client.command.assert_called_once()

    async def test_polling_publishes_only_new_samples_and_clears_after_transport_loss(self):
        hub=main.Hub()
        client=Mock(); client.status.return_value=fixture()
        with patch.object(main,'HostClient',return_value=client):
            await hub.poll_once(); await hub.poll_once()
            self.assertEqual(len(hub.samples),2)
            client.status.side_effect=BridgeError('offline')
            await hub.poll_once()
            self.assertFalse(hub.latest['host_online'])
            self.assertIsNone(hub.latest['angle_deg'])
            self.assertEqual(len(hub.samples),0)
            client.status.side_effect=None
            await hub.poll_once()
            self.assertEqual(len(hub.samples),0)
            self.assertIsNone(hub.latest['angle_deg'])


if __name__=='__main__': unittest.main()
