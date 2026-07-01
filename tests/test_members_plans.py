from unittest.mock import MagicMock, patch

import writeGoogleSheet as wgs

MEMBER_COLUMNS = [
    "title", "_owner", "_createdDate", "_updatedDate", "email", "emailBounced", "nom", "prenom",
    "cotisationExpiration",
    "instrument1", "categorie1", "instrument2", "categorie2", "prefM", "prefR", "prefS", "prefT", "prefO",
    "adresseRue", "adresseNumero", "adresseBoite", "adresseCp", "adresseVille", "adressePays",
    "telMobC", "telMobP", "telMobN", "telHomeC", "telHomeP", "telHomeN", "telWorkC", "telWorkP",
    "telWorkN", "anneeNaissance", "memberPic", "instrument1Fr", "instrument1Nl", "instrument1En",
    "instrument2Fr", "instrument2Nl", "instrument2En", "adressePaysFr", "adressePaysNl", "adressePaysEn",
    "lastfeePaymentYear", "_id", "membreEffectif",
]


def _member_row(**overrides):
    row = {c: "" for c in MEMBER_COLUMNS}
    row.update(overrides)
    return row


# ---------------------------------------------------------------------------
# upd_members_db_to_google_sheet
# ---------------------------------------------------------------------------

@patch("writeGoogleSheet.open_sheet", return_value=None)
def test_upd_members_no_sheet_returns_early(_open_sheet):
    wgs.upd_members_db_to_google_sheet(MagicMock())
    # nothing else to assert: function must not raise and should return early


@patch("writeGoogleSheet.fetch_data", return_value=None)
@patch("writeGoogleSheet.get_user_pwd", return_value=("u", "tok"))
@patch("writeGoogleSheet.open_sheet")
def test_upd_members_no_data_skips_update(mock_open_sheet, _pwd, _fetch, fake_config):
    ws = MagicMock()
    mock_open_sheet.return_value = ws
    wgs.upd_members_db_to_google_sheet(MagicMock())
    ws.update.assert_not_called()


@patch("writeGoogleSheet.update_data")
@patch("writeGoogleSheet.fetch_data")
@patch("writeGoogleSheet.get_user_pwd", return_value=("u", "tok"))
@patch("writeGoogleSheet.open_sheet")
def test_upd_members_happy_path_no_geomap(mock_open_sheet, _pwd, mock_fetch, mock_update, fake_config):
    ws = MagicMock()
    mock_open_sheet.return_value = ws
    mock_fetch.return_value = {"items": [_member_row(email="a@b.com")]}

    with patch("writeGoogleSheet.geomap_address") as mock_geomap:
        wgs.upd_members_db_to_google_sheet(MagicMock(), geomap=False)
        mock_geomap.assert_not_called()

    mock_update.assert_called_once()


@patch("writeGoogleSheet.geomap_address")
@patch("writeGoogleSheet.update_data")
@patch("writeGoogleSheet.fetch_data")
@patch("writeGoogleSheet.get_user_pwd", return_value=("u", "tok"))
@patch("writeGoogleSheet.open_sheet")
def test_upd_members_geomap_filters_expired(mock_open_sheet, _pwd, mock_fetch, _update, mock_geomap, fake_config):
    ws = MagicMock()
    mock_open_sheet.return_value = ws
    from datetime import datetime, timedelta, UTC
    future = (datetime.now(UTC) + timedelta(days=30)).isoformat()
    past = (datetime.now(UTC) - timedelta(days=30)).isoformat()
    mock_fetch.return_value = {"items": [
        _member_row(email="future@b.com", cotisationExpiration=future),
        _member_row(email="past@b.com", cotisationExpiration=past),
    ]}

    wgs.upd_members_db_to_google_sheet(MagicMock(), geomap=True)

    mock_geomap.assert_called_once()
    passed_df = mock_geomap.call_args[0][0]
    assert list(passed_df["email"]) == ["future@b.com"]


@patch("writeGoogleSheet.geomap_address")
@patch("writeGoogleSheet.update_data")
@patch("writeGoogleSheet.fetch_data")
@patch("writeGoogleSheet.get_user_pwd", return_value=("u", "tok"))
@patch("writeGoogleSheet.open_sheet")
def test_upd_members_geomap_handles_tz_naive_expiration(mock_open_sheet, _pwd, mock_fetch, _update, mock_geomap, fake_config):
    # Regression test: cotisationExpiration values with no UTC offset used to
    # blow up with "Cannot subtract tz-naive and tz-aware datetime-like
    # objects" against the tz-aware `datetime.now(UTC)` comparison.
    ws = MagicMock()
    mock_open_sheet.return_value = ws
    from datetime import datetime, timedelta
    future = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    past = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    mock_fetch.return_value = {"items": [
        _member_row(email="future@b.com", cotisationExpiration=future),
        _member_row(email="past@b.com", cotisationExpiration=past),
    ]}

    wgs.upd_members_db_to_google_sheet(MagicMock(), geomap=True)

    mock_geomap.assert_called_once()
    passed_df = mock_geomap.call_args[0][0]
    assert list(passed_df["email"]) == ["future@b.com"]


# ---------------------------------------------------------------------------
# upd_members_plans_to_google_sheet
# ---------------------------------------------------------------------------

PLAN_COLUMNS = [
    "_id", "nomMembre", "prenomMembre", "emailMembre", "planName", "planDescription", "price",
    "paymentStatus", "_createdDate", "validUntil", "_updatedDate", "validFrom", "recurring", "id",
    "dateCreated", "status", "roleId", "wixPayOrderId", "memberId", "orderType", "cancellationReason",
    "planId", "cancellationInitiator", "validFor",
]


def _plan_row(**overrides):
    row = {c: "" for c in PLAN_COLUMNS}
    row.update(overrides)
    return row


@patch("writeGoogleSheet.open_sheet", return_value=None)
def test_upd_plans_no_sheet_returns_early(_open_sheet):
    wgs.upd_members_plans_to_google_sheet(MagicMock())


@patch("writeGoogleSheet.fetch_data", return_value=None)
@patch("writeGoogleSheet.get_user_pwd", return_value=("u", "tok"))
@patch("writeGoogleSheet.open_sheet")
def test_upd_plans_no_data_skips_update(mock_open_sheet, _pwd, _fetch, fake_config):
    ws = MagicMock()
    mock_open_sheet.return_value = ws
    wgs.upd_members_plans_to_google_sheet(MagicMock())
    ws.update.assert_not_called()


@patch("writeGoogleSheet.update_data")
@patch("writeGoogleSheet.fetch_data")
@patch("writeGoogleSheet.get_user_pwd", return_value=("u", "tok"))
@patch("writeGoogleSheet.open_sheet")
def test_upd_plans_happy_path(mock_open_sheet, _pwd, mock_fetch, mock_update, fake_config):
    ws = MagicMock()
    mock_open_sheet.return_value = ws
    mock_fetch.return_value = {"items": [_plan_row(_id="1")]}

    wgs.upd_members_plans_to_google_sheet(MagicMock())

    mock_update.assert_called_once()
