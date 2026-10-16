"""Explicit local HTTP actions for the separately owned real BLE car."""
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from car_service import CarError, CarService

service = CarService()  # Construction does not start a worker or access Bluetooth.
router = APIRouter(prefix='/car', tags=['car'])


class ConnectBody(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    device_id: str = Field(min_length=1, max_length=512)


class SessionBody(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    session: str = Field(min_length=1, max_length=128)


class IntentBody(SessionBody):
    sequence: int = Field(ge=0, le=9007199254740991)
    direction: Literal['FWD', 'REV'] | None
    steering: Literal['LEFT', 'CENTER', 'RIGHT']


def _call(function, *args):
    try:
        return function(*args)
    except CarError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc


@router.get('/status')
def status():
    return service.status()


@router.post('/scan')
def scan():
    return _call(service.scan)


@router.post('/connect')
def connect(body: ConnectBody):
    return _call(service.connect, body.device_id)


@router.post('/intent')
def intent(body: IntentBody):
    return _call(service.intent, body.session, body.sequence, body.direction, body.steering)


@router.post('/stop')
def stop(body: SessionBody):
    return _call(service.stop, body.session)


@router.post('/disconnect')
def disconnect(body: SessionBody):
    return _call(service.disconnect, body.session)
