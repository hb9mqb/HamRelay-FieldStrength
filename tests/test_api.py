from fastapi.testclient import TestClient

from hamrelay_field_strength import service


def test_health() -> None:
    assert TestClient(service.app).get("/v1/health").json() == {"status": "ok"}


def test_root_redirects_to_demo() -> None:
    response = TestClient(service.app).get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/demo/"


def test_capabilities_describe_web_integration() -> None:
    data = TestClient(service.app).get("/v1/capabilities").json()
    assert data["field_units"] == "dBµV/m"
    assert data["radius_km"]["maximum"] == 100
    assert "web-mercator-tiles" in data["features"]
    assert "server-composites" in data["features"]


def test_calculation_is_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("FIELD_STRENGTH_ENABLE_CALCULATIONS", raising=False)
    response = TestClient(service.app).post(
        "/v1/calculations",
        json={
            "station": {
                "id": "TEST-UHF-001",
                "latitude_deg": 46.8,
                "longitude_deg": 8.2,
                "frequency_mhz": 439.5,
            },
            "terrain_mode": "dataset",
            "dem_dataset_id": "world",
            "radius_km": 75,
        },
    )
    assert response.status_code == 403


def test_tile_coordinates_are_bounded() -> None:
    client = TestClient(service.app)
    assert client.get("/v1/coverage/missing/tiles/19/0/0.png").status_code == 422
    assert client.get("/v1/coverage/missing/tiles/0/2/0.png").status_code == 404


def test_current_geotiff_can_be_delivered(tmp_path, monkeypatch) -> None:
    station_directory = tmp_path / "TEST-UHF-001"
    station_directory.mkdir()
    (station_directory / "manifest.json").write_text(
        '{"published_outputs":["geotiff"]}', encoding="utf-8"
    )
    (station_directory / "field-strength.tif").write_bytes(b"test-geotiff")
    monkeypatch.setattr(service, "ARTIFACT_ROOT", tmp_path)
    service._manifest.cache_clear()
    response = TestClient(service.app).get("/v1/coverage/TEST-UHF-001/field-strength.tif")
    assert response.status_code == 200
    assert response.content == b"test-geotiff"
    service._manifest.cache_clear()
