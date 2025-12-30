from graph_api.quality_router import _soda_config_yaml_from_database_url


def test_soda_config_yaml_does_not_set_schema_to_avoid_double_qualification():
    yaml_str = _soda_config_yaml_from_database_url(
        "postgresql://user:pass@localhost:5432/dbname",
        data_source_name="postgres",
        _schema="public",
    )

    # We intentionally do NOT set schema in the connection config. Schema should be
    # specified in the SodaCL checks header (e.g. `checks for public.table:`).
    assert "schema:" not in yaml_str
    assert "data_source postgres:" in yaml_str
    assert "type: postgres" in yaml_str
