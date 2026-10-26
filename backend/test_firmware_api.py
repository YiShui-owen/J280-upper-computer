"""ASGI-only API validation; no native process, port or device is opened."""
import importlib.util
import json
import unittest
from unittest.mock import Mock, patch

from fastapi import FastAPI
from test_car_api import request as old_request

if importlib.util.find_spec('firmware_api'):
    import firmware_api
else:
    firmware_api = None


async def api_request(app, path, body=None, *, headers=None, method='POST'):
    raw = b'' if body is None else json.dumps(body).encode('utf-8')
    default = {'host': '127.0.0.1:8000', 'origin': 'http://localhost:5173',
               'x-j280-local': '1', 'content-type': 'application/json'}
    if headers:
        default.update(headers)
    scope = dict(type='http', asgi={'version': '3.0'}, http_version='1.1', method=method,
                 scheme='http', path=path, raw_path=path.encode(), root_path='', query_string=b'',
                 server=('127.0.0.1', 8000), client=('127.0.0.1', 1),
                 headers=[(k.encode(), v.encode()) for k, v in default.items()])
    messages = []
    async def receive():
        return dict(type='http.request', body=raw, more_body=False)
    async def send(message):
        messages.append(message)
    await app(scope, receive, send)
    return messages[0]['status'], json.loads(b''.join(m.get('body', b'') for m in messages[1:]))


class FirmwareApiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.assertIsNotNone(firmware_api, '缺少固件切换API')
        self.app = FastAPI()
        self.app.include_router(firmware_api.router)
        self.service = Mock()
        self.service.status.return_value = dict(busy=False, phase='idle', job=None, error=None)
        self.service.config.return_value = dict(configured=False, firmwares=['V1','V2','V3','V4','V5'])
        self.service.start.return_value = dict(request_id='one', target='V5', state='queued')
        self.patch = patch.object(firmware_api, 'service', self.service)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    async def test_status_and_config_never_launch_or_scan(self):
        self.assertEqual((await api_request(self.app, '/firmware/status', method='GET'))[0], 200)
        self.assertEqual((await api_request(self.app, '/firmware/config', method='GET'))[0], 200)
        self.service.start.assert_not_called()
        self.service.scan.assert_not_called()

    async def test_explicit_job_is_once_only_and_strict_sram_target_body(self):
        body = dict(request_id='one', target='V5', motor_isolated=False)
        code, result = await api_request(self.app, '/firmware/jobs', body)
        self.assertEqual(code, 202)
        self.assertEqual(result['request_id'], 'one')
        self.service.start.assert_called_once_with(**body)
        for changes in (dict(target='V6'), dict(target='auto'), dict(operation=5),
                        dict(fsFile='other.fs'), dict(motor_isolated='yes')):
            with self.subTest(changes=changes):
                self.assertEqual((await api_request(self.app, '/firmware/jobs', body | changes))[0], 422)
        self.assertEqual(self.service.start.call_count, 1)

    async def test_untrusted_origin_host_and_missing_local_header_are_rejected(self):
        for headers in ({'origin':'https://example.invalid'}, {'host':'example.invalid'}, {'x-j280-local':'0'}):
            with self.subTest(headers=headers):
                self.assertEqual((await api_request(self.app, '/firmware/jobs',
                                                   dict(request_id='one', target='V5'), headers=headers))[0], 403)
        self.service.start.assert_not_called()

    async def test_known_rejection_keeps_reason_and_is_not_retried(self):
        from firmware_service import FirmwareError
        self.service.start.side_effect = FirmwareError('回放禁止固件下载')
        code, result = await api_request(self.app, '/firmware/jobs', dict(request_id='one', target='V5'))
        self.assertEqual(code, 409)
        self.assertEqual(result['detail']['state'], 'rejected')
        self.assertIn('回放', result['detail']['message'])
        self.service.start.assert_called_once()


if __name__ == '__main__':
    unittest.main()
