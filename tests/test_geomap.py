from unittest.mock import MagicMock, patch

import pandas as pd

import writeGoogleSheet as wgs


def _loc(lat=50.8, lng=4.35):
    loc = MagicMock()
    loc.latitude = lat
    loc.longitude = lng
    return loc


@patch("writeGoogleSheet.folium.Marker")
@patch("writeGoogleSheet.folium.Map")
@patch("writeGoogleSheet.TomTom")
@patch("writeGoogleSheet.get_secret", return_value={"key": "tt-key"})
def test_geomap_address_happy_path_plots_marker(_secret, mock_tomtom, mock_map, mock_marker, fake_config):
    geolocator = MagicMock()
    geolocator.geocode.return_value = _loc()
    mock_tomtom.return_value = geolocator
    mock_map.return_value = MagicMock()

    df = pd.DataFrame([{
        "cotisationExpiration": "2030-01-01",
        "adressePays": "BE",
        "adresseNumero": "12",
        "adresseRue": "Rue Test",
        "adresseCp": "1000",
        "adresseVille": "Bruxelles",
        "prenom": "Jean",
        "nom": "Dupont",
    }])

    wgs.geomap_address(df)

    mock_marker.assert_called_once()
    mock_map.return_value.save.assert_called_once_with(fake_config["geomap"]["index"])


@patch("writeGoogleSheet.folium.Marker")
@patch("writeGoogleSheet.folium.Map")
@patch("writeGoogleSheet.TomTom")
@patch("writeGoogleSheet.get_secret", return_value={"key": "tt-key"})
def test_geomap_address_skips_row_without_expiration(_secret, mock_tomtom, mock_map, mock_marker, fake_config):
    geolocator = MagicMock()
    geolocator.geocode.return_value = _loc()
    mock_tomtom.return_value = geolocator

    df = pd.DataFrame([{
        "cotisationExpiration": "",
        "adressePays": "BE",
        "adresseNumero": "12",
        "adresseRue": "Rue Test",
        "adresseCp": "1000",
        "adresseVille": "Bruxelles",
        "prenom": "Jean",
        "nom": "Dupont",
    }])

    wgs.geomap_address(df)

    mock_marker.assert_not_called()


@patch("writeGoogleSheet.folium.Marker")
@patch("writeGoogleSheet.folium.Map")
@patch("writeGoogleSheet.TomTom")
@patch("writeGoogleSheet.get_secret", return_value={"key": "tt-key"})
def test_geomap_address_unknown_country_is_caught(_secret, mock_tomtom, mock_map, mock_marker, fake_config):
    geolocator = MagicMock()
    geolocator.geocode.return_value = _loc()
    mock_tomtom.return_value = geolocator

    df = pd.DataFrame([{
        "cotisationExpiration": "2030-01-01",
        "adressePays": "FR",  # not in the country dict -> KeyError caught
        "adresseNumero": "12",
        "adresseRue": "Rue Test",
        "adresseCp": "1000",
        "adresseVille": "Paris",
        "prenom": "Jean",
        "nom": "Dupont",
    }])

    wgs.geomap_address(df)

    mock_marker.assert_not_called()


@patch("writeGoogleSheet.folium.Marker")
@patch("writeGoogleSheet.folium.Map")
@patch("writeGoogleSheet.TomTom")
@patch("writeGoogleSheet.get_secret", return_value={"key": "tt-key"})
def test_geomap_address_geocode_exception_is_caught(_secret, mock_tomtom, mock_map, mock_marker, fake_config):
    geolocator = MagicMock()
    geolocator.geocode.side_effect = [_loc(), Exception("geocode failed")]
    mock_tomtom.return_value = geolocator

    df = pd.DataFrame([{
        "cotisationExpiration": "2030-01-01",
        "adressePays": "BE",
        "adresseNumero": "12",
        "adresseRue": "Rue Test",
        "adresseCp": "1000",
        "adresseVille": "Bruxelles",
        "prenom": "Jean",
        "nom": "Dupont",
    }])

    wgs.geomap_address(df)

    mock_marker.assert_not_called()


@patch("writeGoogleSheet.folium.Marker")
@patch("writeGoogleSheet.folium.Map")
@patch("writeGoogleSheet.TomTom")
@patch("writeGoogleSheet.get_secret", return_value={"key": "tt-key"})
def test_geomap_address_stops_after_1000_rows(_secret, mock_tomtom, mock_map, mock_marker, fake_config):
    geolocator = MagicMock()
    geolocator.geocode.return_value = _loc()
    mock_tomtom.return_value = geolocator

    row = {
        "cotisationExpiration": "2030-01-01",
        "adressePays": "BE",
        "adresseNumero": "12",
        "adresseRue": "Rue Test",
        "adresseCp": "1000",
        "adresseVille": "Bruxelles",
        "prenom": "Jean",
        "nom": "Dupont",
    }
    df = pd.DataFrame([row] * 1005)

    wgs.geomap_address(df)

    # first geocode call is the Bruxelles bootstrap lookup, then one per row
    # for idx 0..1000 inclusive (break fires once idx > 1000)
    assert geolocator.geocode.call_count == 1 + 1001
