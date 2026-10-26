"""Local-only endpoints for the fixed SRAM workflow; no generic process runner."""
from typing import Any, Literal
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from firmware_service import FirmwareError, FirmwareService

service = FirmwareService()  # File metadata only; no native tool or device starts.


def local_request(request: Request):
    host = request.headers.get('host', '').lower()
    origin = request.headers.get('origin')
    if (request.headers.get('x-j280-local') != '1' or
            not re.fullmatch(r'(?:127\.0\.0\.1|localhost)(?::[0-9]{1,5})?', host) or
            origin not in (None, 'http://localhost:5173', 'http://127.0.0.1:5173') or
            not request.client or request.client.host not in ('127.0.0.1', '::1')):
        raise HTTPException(403, dict(state='rejected', message='固件接口仅接受本机展示页面的显式请求'))
    try:
        length = int(request.headers.get('content-length', '0'))
    except ValueError:
        length = -1
    if not 0 <= length <= 8192:
        raise HTTPException(400, dict(state='rejected', message='固件请求内容长度无效'))


router = APIRouter(prefix='/firmware', tags=['firmware'], dependencies=[Depends(local_request)])


class LocalConfig(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    programmer_path: str = Field(max_length=1024)
    cable: dict[str, Any] | None
    usb_port: str = Field(max_length=20)


class ScanBody(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    programmer_path: str = Field(min_length=1, max_length=1024)


class JobBody(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    request_id: str = Field(min_length=1, max_length=128, pattern=r'^[A-Za-z0-9_.:-]+$')
    target: Literal['V1', 'V2', 'V3', 'V4', 'V5']
    motor_isolated: bool = False


def _call(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except FirmwareError as exc:
        raise HTTPException(exc.status_code, dict(state='rejected', message=str(exc))) from exc
    except (ValueError, RuntimeError, OSError) as exc:
        raise HTTPException(400, dict(state='rejected', message=str(exc))) from exc


@router.get('/config')
def config():
    return _call(service.config)


@router.post('/config')
def update_config(body: LocalConfig):
    return _call(service.save_config, body.model_dump())


@router.post('/scan')
def scan(body: ScanBody):
    return _call(service.scan, body.programmer_path)


@router.get('/status')
def status():
    return service.status()


@router.post('/jobs', status_code=202)
def start(body: JobBody):
    return _call(service.start, **body.model_dump())


@router.get('/jobs/{request_id}')
def result(request_id: str):
    if not re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}', request_id):
        raise HTTPException(400, dict(state='rejected', message='任务ID无效'))
    return _call(service.result, request_id)
