from hamrelay_field_strength import database
from hamrelay_field_strength.database import StationRecord


def test_locked_coordinates_survive_later_import(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "stations.sqlite3")
    database.initialize()
    original = StationRecord(
        station_id="LOCKED-1",
        latitude_deg=46.123,
        longitude_deg=8.456,
        coordinates_locked=True,
        coordinate_source="surveyed",
        tx_frequency_mhz=439.5,
        erp_w=12,
    )
    database.upsert_station(original)

    imported = original.model_copy(
        update={
            "latitude_deg": 47.0,
            "longitude_deg": 9.0,
            "coordinates_locked": False,
            "coordinate_source": "bulk import",
            "erp_w": 25,
        }
    )
    result = database.upsert_station(imported)

    assert result["latitude_deg"] == 46.123
    assert result["longitude_deg"] == 8.456
    assert result["coordinate_source"] == "surveyed"
    assert result["coordinates_locked"] is True
    assert result["erp_w"] == 25
