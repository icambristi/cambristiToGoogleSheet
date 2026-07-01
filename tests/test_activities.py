from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import gspread
import pandas as pd

import writeGoogleSheet as wgs

CURRENT_YEAR = datetime.now().year


# ---------------------------------------------------------------------------
# is_coti_paid / is_member
# ---------------------------------------------------------------------------

def test_custom_hook_prints_failure(capsys):
    args = MagicMock()
    args.exc_value = "boom"
    wgs.custom_hook(args)
    captured = capsys.readouterr()
    assert "boom" in captured.out


def test_is_coti_paid_true_for_future_order():
    future = (datetime.now() + timedelta(days=10)).isoformat()
    df_orders = pd.DataFrame([{
        "emailMembre": "a@b.com", "planName": "Cotisation annuelle", "validUntil": future,
    }])
    item = {"email": "a@b.com"}
    assert wgs.is_coti_paid(item, df_orders) == "True"


def test_is_coti_paid_false_for_past_order():
    past = (datetime.now() - timedelta(days=10)).isoformat()
    df_orders = pd.DataFrame([{
        "emailMembre": "a@b.com", "planName": "Cotisation annuelle", "validUntil": past,
    }])
    item = {"email": "a@b.com"}
    assert wgs.is_coti_paid(item, df_orders) == "False"


def test_is_coti_paid_false_when_no_matching_orders():
    df_orders = pd.DataFrame([{
        "emailMembre": "other@b.com", "planName": "Cotisation annuelle",
        "validUntil": datetime.now().isoformat(),
    }])
    item = {"email": "a@b.com"}
    assert wgs.is_coti_paid(item, df_orders) == "False"


def test_is_member_true_for_member_title():
    df_members = pd.DataFrame([{"email": "a@b.com", "title": "member"}])
    assert wgs.is_member({"email": "a@b.com"}, df_members) == "True"


def test_is_member_false_for_other_title():
    df_members = pd.DataFrame([{"email": "a@b.com", "title": "guest"}])
    assert wgs.is_member({"email": "a@b.com"}, df_members) == "False"


def test_is_member_false_when_not_found():
    df_members = pd.DataFrame([{"email": "other@b.com", "title": "member"}])
    assert wgs.is_member({"email": "a@b.com"}, df_members) == "False"


# ---------------------------------------------------------------------------
# fmt_musicians
# ---------------------------------------------------------------------------

def _group(musicians_repr):
    gr = MagicMock()
    gr.musicians = musicians_repr
    return gr


def _activity(stage_id="s1"):
    act = MagicMock()
    act._id = stage_id
    return act


def test_fmt_musicians_matches_member_paid():
    df_participants = pd.DataFrame([{
        "memberId": "m1", "stageId": "s1", "isCotiPaid": "True", "member": "True",
        "participantName": "Jean Dupont", "participantEmail": "jean@x.com", "instrument": "Piano",
    }])
    gr = _group("['m1']")
    result = wgs.fmt_musicians(gr, _activity(), df_participants)
    assert "[ ok ]" in result.musicians
    assert "[Mbre]" in result.musicians
    assert "Jean Dupont" in result.musicians


def test_fmt_musicians_unpaid_external():
    df_participants = pd.DataFrame([{
        "memberId": "m1", "stageId": "s1", "isCotiPaid": "False", "member": "False",
        "participantName": "Jean Dupont", "participantEmail": "jean@x.com", "instrument": "Piano",
    }])
    gr = _group("['m1']")
    result = wgs.fmt_musicians(gr, _activity(), df_participants)
    assert "[25€]" in result.musicians
    assert "[Extrn]" in result.musicians


def test_fmt_musicians_no_match_produces_empty_string():
    df_participants = pd.DataFrame([{
        "memberId": "other", "stageId": "s1", "isCotiPaid": "True", "member": "True",
        "participantName": "X", "participantEmail": "x@x.com", "instrument": "Flute",
    }])
    gr = _group("['m1']")
    result = wgs.fmt_musicians(gr, _activity(), df_participants)
    assert result.musicians == ""


# ---------------------------------------------------------------------------
# upd_activities_to_google_sheet (integration)
# ---------------------------------------------------------------------------

def _all_activities_payload():
    return {"items": [{
        "_id": "act1",
        "title": "Concert Été",
        "typeActivite": "Concert",
        "dateDebut": f"{CURRENT_YEAR}-08-01T00:00:00",
        "nomLieu": "Salle X",
        "lieu": {"formatted": "1 rue Test, Bruxelles"},
        "adminEmail": "admin1@x.com",
        "adminEmail1": "admin2@x.com",
    }]}


def _members_payload():
    return {"items": [{"email": "jean@x.com", "title": "member"}]}


def _orders_payload():
    return {"items": [{"emailMembre": "jean@x.com", "planName": "Cotisation",
                        "validUntil": (datetime.now() + timedelta(days=10)).isoformat()}]}


def _groups_payload():
    return {"items": [{
        "_id": "g1", "stageId": "act1", "title": "Groupe A", "isConfirmed": "True",
        "responsibleEmail": "resp@x.com", "workToPlay": "Symphony", "remarks": "",
        "duration": "1h", "musicians": "['m1']",
    }]}


def _participants_payload():
    return {"items": [{
        "_id": "p1", "prenom": "Jean", "nom": "Dupont", "email": "jean@x.com",
        "memberId": "m1", "stageId": "act1", "stageName": "Concert Été",
        "groupId": "g1", "groupName": "Groupe A", "instrument": "Piano",
    }]}


@patch("writeGoogleSheet.gf.set_column_widths")
@patch("writeGoogleSheet.update_data")
@patch("writeGoogleSheet.fetch_data")
@patch("writeGoogleSheet.get_user_pwd", return_value=("u", "tok"))
@patch("writeGoogleSheet.open_worksheet")
@patch("writeGoogleSheet.open_workbook")
def test_upd_activities_happy_path(
    mock_open_workbook, mock_open_worksheet, _pwd, mock_fetch, mock_update_data, _set_widths, fake_config
):
    wb = MagicMock()
    mock_open_workbook.return_value = wb
    mock_open_worksheet.return_value = MagicMock()

    mock_fetch.side_effect = [
        _all_activities_payload(),
        _members_payload(),
        _orders_payload(),
        _groups_payload(),
        _participants_payload(),
    ]

    wb.worksheet.side_effect = gspread.exceptions.WorksheetNotFound
    wb.add_worksheet.return_value = MagicMock()

    wgs.upd_activities_to_google_sheet(MagicMock())

    wb.add_worksheet.assert_called_once_with("Concert Été", 100, 20)
    assert mock_update_data.call_count == 2  # summary sheet + per-activity sheet


@patch("writeGoogleSheet.gf.set_column_widths")
@patch("writeGoogleSheet.update_data")
@patch("writeGoogleSheet.fetch_data")
@patch("writeGoogleSheet.get_user_pwd", return_value=("u", "tok"))
@patch("writeGoogleSheet.open_worksheet")
@patch("writeGoogleSheet.open_workbook")
def test_upd_activities_reuses_existing_worksheet(
    mock_open_workbook, mock_open_worksheet, _pwd, mock_fetch, mock_update_data, _set_widths, fake_config
):
    wb = MagicMock()
    mock_open_workbook.return_value = wb
    mock_open_worksheet.return_value = MagicMock()

    mock_fetch.side_effect = [
        _all_activities_payload(),
        _members_payload(),
        _orders_payload(),
        _groups_payload(),
        _participants_payload(),
    ]

    existing_ws = MagicMock()
    wb.worksheet.return_value = existing_ws

    wgs.upd_activities_to_google_sheet(MagicMock())

    wb.add_worksheet.assert_not_called()
