"""Tests for resource-domain test helpers: create_test_venue, create_test_equipment."""
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.venue import Venue
from app.models.equipment import Equipment
from tests.helpers import create_test_venue, create_test_equipment


@pytest.mark.asyncio(loop_scope="session")
async def test_create_test_venue_basic(db_session: AsyncSession):
    venue = await create_test_venue(db_session, name="Helper Venue", capacity=20)
    assert venue.id is not None
    assert venue.name == "Helper Venue"
    assert venue.capacity == 20
    assert venue.status == "active"


@pytest.mark.asyncio(loop_scope="session")
async def test_create_test_venue_persisted(db_session: AsyncSession):
    venue = await create_test_venue(db_session, name="Persisted Venue")
    result = await db_session.execute(select(Venue).where(Venue.id == venue.id))
    assert result.scalar_one() is not None


@pytest.mark.asyncio(loop_scope="session")
async def test_create_test_venue_defaults(db_session: AsyncSession):
    venue = await create_test_venue(db_session)
    assert venue.name == "Test Venue"
    assert venue.status == "active"


@pytest.mark.asyncio(loop_scope="session")
async def test_create_test_equipment_with_venue(db_session: AsyncSession):
    venue = await create_test_venue(db_session, name="Equip Helper Venue")
    equip = await create_test_equipment(db_session, name="Helper Device", venue_id=venue.id)
    assert equip.id is not None
    assert equip.name == "Helper Device"
    assert equip.venue_id == venue.id
    assert equip.status == "active"


@pytest.mark.asyncio(loop_scope="session")
async def test_create_test_equipment_no_venue(db_session: AsyncSession):
    equip = await create_test_equipment(db_session, name="Unbound Device")
    assert equip.venue_id is None
    assert equip.status == "active"


@pytest.mark.asyncio(loop_scope="session")
async def test_create_test_equipment_persisted(db_session: AsyncSession):
    equip = await create_test_equipment(db_session, name="Persisted Equip")
    result = await db_session.execute(select(Equipment).where(Equipment.id == equip.id))
    assert result.scalar_one() is not None


@pytest.mark.asyncio(loop_scope="session")
async def test_create_test_equipment_with_serial(db_session: AsyncSession):
    equip = await create_test_equipment(db_session, name="SN Device", serial_number="SN-TEST-001")
    assert equip.serial_number == "SN-TEST-001"
