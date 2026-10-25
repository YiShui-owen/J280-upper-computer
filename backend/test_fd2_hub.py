"""Full FD2 cursor drain and 120-second history in the real Hub, no sockets."""
import time
import unittest
from unittest.mock import Mock, patch

import main
from host_bridge import BridgeError
from fastapi import HTTPException
from test_fd2_telemetry import frame, snapshot


class FD2HubTests(unittest.IsolatedAsyncioTestCase):
    async def test_known_host_rejection_is_not_reported_as_unknown_or_retried(self):
        client = Mock(); client.status.return_value = snapshot()
        error = BridgeError('replay rejects hardware commands')
        error.request_rejected = True
        client.command.side_effect = error
        with patch.object(main, 'HostClient', return_value=client), patch.object(main, 'load_config', return_value=dict(bridge_port=8371, firmware_variant='auto')):
            with self.assertRaises(HTTPException) as context:
                await main.command(main.Command(action='balance', request_id='one'))
        self.assertEqual(context.exception.detail['state'], 'rejected')
        client.command.assert_called_once()

    async def test_35_seconds_of_200hz_history_is_drained_without_latest_only_sampling(self):
        now = time.time()
        count = 7000
        records = [dict(cursor=i+1, received_at=now-35+(i+1)*.005,
                        frame=frame(seq=i+1, board=i*5), gap_before=False) for i in range(count)]
        client = Mock()
        client.status.return_value = snapshot()
        def read(after=None, stream=None):
            rows = records[after or 0:(after or 0)+512]
            return dict(stream='offline-test', cursor=rows[-1]['cursor'] if rows else count,
                        head=1, tail=count, overrun=False, samples=rows)
        client.waveform.side_effect = read
        hub = main.Hub()
        with patch.object(main, 'HostClient', return_value=client), patch.object(main, 'load_config', return_value=dict(bridge_port=8371, firmware_variant='auto')):
            await hub.poll_once()
            self.assertIsNone(hub.last_error)
            self.assertEqual(len(hub.samples), count)
            self.assertEqual(hub.wave_cursor, count)
            await hub.poll_once()
            self.assertEqual(len(hub.samples), count)

    async def test_malformed_page_keeps_cursor_and_can_be_refetched_without_loss(self):
        hub = main.Hub()
        client = Mock(); client.status.return_value = snapshot()
        row = dict(cursor=1, received_at=time.time(), frame=frame(), gap_before=False)
        bad = dict(row, frame=dict(row['frame'], schema=0))
        page = dict(stream='offline-test', cursor=1, head=1, tail=1, overrun=False, samples=[bad])
        client.waveform.return_value = page
        with patch.object(main, 'HostClient', return_value=client), patch.object(main, 'load_config', return_value=dict(bridge_port=8371, firmware_variant='auto')):
            await hub.poll_once()
            self.assertIsNotNone(hub.last_error)
            self.assertIsNone(hub.wave_cursor)
            page['samples'] = [row]
            await hub.poll_once()
            self.assertIsNone(hub.last_error)
            self.assertEqual(len(hub.samples), 1)


if __name__ == '__main__': unittest.main()
