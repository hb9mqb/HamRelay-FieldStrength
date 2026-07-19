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


def test_seed_file_never_replaces_existing_station(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "stations.sqlite3")
    database.initialize()
    seed_path = tmp_path / "stations.json"
    seed_path.write_text(
        '[{"station_id":"REAL-1","latitude_deg":47.0,'
        '"longitude_deg":8.0,"tx_frequency_mhz":439.5,"erp_w":12}]',
        encoding="utf-8",
    )
    assert database.seed_from_file(seed_path) == 1

    existing = StationRecord.model_validate({**database.get_station("REAL-1"), "erp_w": 25})
    database.upsert_station(existing)
    assert database.seed_from_file(seed_path) == 0
    assert database.get_station("REAL-1")["erp_w"] == 25


def test_registry_records_default_power_provenance(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "stations.sqlite3")
    database.initialize()
    record = StationRecord(
        station_id="ASSUMED-1",
        latitude_deg=47.0,
        longitude_deg=8.0,
        tx_frequency_mhz=439.5,
    )
    assert record.erp_w == 12
    assert record.power_assumed is True
    stored = database.upsert_station(record)
    assert stored["power_assumed"] is True
