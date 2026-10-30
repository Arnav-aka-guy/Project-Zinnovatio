"""API tests for Officer Dashboard integration with Voice Bookings (Step V7).

Tests:
  - /api/dashboard/summary counts voice requests in `by_source`.
  - /api/dashboard/summary never exposes farmer phone numbers or names to any caller.
  - /api/dashboard/summary requires staff authentication (returns 401 without credentials).
"""

from fastapi.testclient import TestClient

from app import clock
from app.enums import RequestSource, ServiceType
from app.routes.requests import create_request_record
from app.schemas import RequestIn


def test_dashboard_summary_requires_auth(client: TestClient):
    res = client.get("/api/dashboard/summary")
    assert res.status_code == 401


def test_dashboard_summary_counts_voice_requests(client: TestClient, auth_headers: dict, temp_db):
    with temp_db() as s:
        # 2 voice requests
        create_request_record(
            s,
            RequestIn(
                name="Amrik Singh",
                phone="9876543210",
                village="Rampur",
                acres=2.5,
                service_type=ServiceType.SUPER_SEEDER,
                harvest_date=clock.today(),
                consent_service=True,
                consent_evidence=True,
                consent_share=False,
            ),
            source=RequestSource.VOICE,
        )
        create_request_record(
            s,
            RequestIn(
                name="Jaswant Kaur",
                phone="9876543211",
                village="Rampur",
                acres=2.5,
                service_type=ServiceType.HAPPY_SEEDER,
                harvest_date=clock.today(),
                consent_service=True,
                consent_evidence=True,
                consent_share=False,
            ),
            source=RequestSource.VOICE,
        )
        # 1 form request
        create_request_record(
            s,
            RequestIn(
                name="Kuldeep Singh",
                phone="9876543212",
                village="Kila Raipur",
                acres=1.5,
                service_type=ServiceType.SUPER_SEEDER,
                harvest_date=clock.today(),
                consent_service=True,
                consent_evidence=True,
                consent_share=False,
            ),
            source=RequestSource.FORM,
        )
        s.commit()

    res = client.get("/api/dashboard/summary", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()

    assert "by_source" in data
    assert data["by_source"]["voice"] == 2
    assert data["by_source"]["form"] == 1


def test_dashboard_summary_privacy_no_phones_or_names(client: TestClient, auth_headers: dict, temp_db):
    with temp_db() as s:
        create_request_record(
            s,
            RequestIn(
                name="Secret Farmer Name",
                phone="9988776655",
                village="Rampur",
                acres=2.0,
                service_type=ServiceType.SUPER_SEEDER,
                harvest_date=clock.today(),
                consent_service=True,
                consent_evidence=True,
                consent_share=False,
            ),
            source=RequestSource.VOICE,
        )
        s.commit()

    res = client.get("/api/dashboard/summary", headers=auth_headers)
    assert res.status_code == 200
    raw_text = res.text

    # Privacy guarantee: Farmer phone and personal name must NEVER appear in the response payload
    assert "9988776655" not in raw_text
    assert "Secret Farmer Name" not in raw_text
