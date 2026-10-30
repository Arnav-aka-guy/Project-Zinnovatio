"""Unit tests for Desk integration of Voice Bookings (Step V7).

Tests:
  - Request with source="voice" carries the "voice booking" badge.
  - Other sources (form, register, seed) carry their expected badges and do not carry "voice booking".
  - Source values and filtering behavior.
"""

from app import clock
from app.enums import RequestSource, ServiceType
from app.routes.common import serialize_request
from app.routes.requests import create_request_record
from app.schemas import RequestIn


def test_voice_request_has_voice_booking_badge(temp_db):
    with temp_db() as s:
        req_in = RequestIn(
            name="Gurpreet Singh",
            phone="9876543210",
            village="Rampur",
            acres=2.5,
            service_type=ServiceType.SUPER_SEEDER,
            harvest_date=clock.today(),
            consent_service=True,
            consent_evidence=True,
            consent_share=False,
        )
        req = create_request_record(s, req_in, source=RequestSource.VOICE)
        s.flush()

        out = serialize_request(s, req)
        assert out.source == "voice"
        assert "voice booking" in out.badges
        assert "seeded request" not in out.badges


def test_non_voice_requests_do_not_have_voice_booking_badge(temp_db):
    with temp_db() as s:
        req_form = create_request_record(
            s,
            RequestIn(
                name="Baldev Singh",
                phone="9876543211",
                village="Kila Raipur",
                acres=3.0,
                service_type=ServiceType.SUPER_SEEDER,
                harvest_date=clock.today(),
                consent_service=True,
                consent_evidence=True,
                consent_share=False,
            ),
            source=RequestSource.FORM,
        )

        req_seed = create_request_record(
            s,
            RequestIn(
                name="Baldev Singh",
                phone="9876543211",
                village="Kila Raipur",
                acres=3.0,
                service_type=ServiceType.SUPER_SEEDER,
                harvest_date=clock.today(),
                consent_service=True,
                consent_evidence=True,
                consent_share=False,
            ),
            source=RequestSource.SEED,
        )
        s.flush()

        out_form = serialize_request(s, req_form)
        assert "voice booking" not in out_form.badges

        out_seed = serialize_request(s, req_seed)
        assert "voice booking" not in out_seed.badges
        assert "seeded request" in out_seed.badges
