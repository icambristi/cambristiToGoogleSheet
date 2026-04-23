#!/usr/bin/env python3
import argparse
import datetime
import hashlib
import json
import logging
import sys
import threading
from time import sleep

import folium
import gspread
import gspread_formatting as gf
import influxdb_client
import jsonpath_ng.ext as jp
import pandas as pd
import requests
import yaml
from geopy.geocoders import TomTom
from getSecrets import get_secret, get_user_pwd
from oauth2client.service_account import ServiceAccountCredentials
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)
test_mode = False


def load_config():
    """
    Load the configuration file
    :return: dict

    """
    try:
        with open('/app/config.yml') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        with open('config.yml') as f:
            return yaml.safe_load(f)


config = load_config()
max_tries = config['google']['max_tries']


def log(severity, msg):
    """
    Log a message to the console and to the logs API
    :param severity: str
    :param msg: str
    :return: None
    """
    valid_severities = {'info', 'debug', 'warning', 'error'}

    if severity in valid_severities:
        logging_function = getattr(logging, severity)
        logging_function(msg)
    else:
        logging.error(f"Invalid severity level: {severity}")
        logging.info(msg)

    if 'logs' in config:
        log_cfg = config['logs']
        url = log_cfg.get('url')
        username = log_cfg.get('username')
        tag = log_cfg.get('tag')
        if url and username:
            pb_hash = hashlib.sha256(username.encode()).hexdigest()
            headers = {'Content-Type': 'application/json'}
            data = {
                'severity': severity,
                'message': msg,
                'timestamp': datetime.datetime.now().isoformat()
            }
            send_log_request(url, pb_hash, tag, headers, data)


def send_log_request(url, pb_hash, tag, headers, data):
    """
    Send a log request to the logs API
    :param url: str
    :param pb_hash: str
    :param tag: str
    :param headers: dict
    :param data: dict
    :return: None

    """
    try:
        resp = requests.post(f'{url}?token={pb_hash}&tag={tag}', headers=headers, json=data)
        if resp.status_code != 201:
            logging.error(f"Error {resp.status_code}: {resp.text}")
    except Exception as e:
        logging.error(e)


def gc_login():
    """
    Get Service Account Credentials and open a connection to google services
    :return:
    """
    scope = ['https://www.googleapis.com/auth/spreadsheets',
             'https://spreadsheets.google.com/feeds',
             'https://www.googleapis.com/auth/drive']

    n = max_tries
    while n > 0:
        try:
            creds = ServiceAccountCredentials.from_json_keyfile_dict(get_secret("cambristiGoogleServiceAccount"), scope)
            return gspread.authorize(creds)
        except Exception:
            sleep(60)
            log('error', 'Retrying connecting to Google Sheets')
            n -= 1
            continue
    log('error', 'Error connecting to Google Sheets')
    return None


def open_sheet(client, ws_id, sheet=None):
    """
    Open a Google Sheet
    :param client: gspread.Client
    :param ws_id: str
    :param sheet: str
    :return: gspread.Worksheet

    """
    n_try = 3
    timeout = 6000
    _, spreadsheet_id = get_user_pwd(ws_id)
    wb = client.open_by_key(spreadsheet_id)
    try:
        return wb.worksheet(sheet) if sheet else wb.sheet1
    except gspread.exceptions.WorksheetNotFound:
        return None
    except gspread.exceptions.APIError as e:
        log('error', f'Error opening sheet: {e}')
        while n_try > 0:
            sleep(timeout)
            n_try -= 1
            wb = client.open_by_key(spreadsheet_id)
            try:
                return wb.worksheet(sheet) if sheet else wb.sheet1
            except gspread.exceptions.WorksheetNotFound:
                return None
            except gspread.exceptions.APIError as e:
                log('error', f'Retrying - Error opening sheet: {e}')
                continue
        return None


def open_workbook(client, ws_id):
    """
    Open a Google Sheet
    :param client: gspread.Client
    :param ws_id: str
    :return: gspread.Worksheet

    """
    _, spreadsheet_id = get_user_pwd(ws_id)
    return client.open_by_key(spreadsheet_id)


def open_worksheet(wb, sheet):
    try:
        return wb.worksheet(sheet) if sheet else wb.sheet1
    except gspread.exceptions.WorksheetNotFound:
        return None


def update_data(ws, df, range):
    """
    Update a Google Sheet with data
    :param ws: gspread.Worksheet
    :param data: dict
    :param range: str
    :param columns: list
    :return: None

    """

    if range == "A1":
        ws.clear()
    else:
        ws.batch_clear([range])

    ws.update(range_name=range, values=[df.columns.values.tolist()] + df.values.tolist())

    if range != "A1":
        ws.update(range_name="A16", values=[["Writes your notes below this line..."]])
        ws.format("A16:F16", {
            "backgroundColor": {
                "red": 1.0,
                "green": 1.0,
                "blue": 0.0
            }
        })
        ws.format('A16', {"verticalAlignment": "TOP",
                          "wrapStrategy": "OVERFLOW_CELL"})


def fetch_data(url, token):
    """
    Fetch data from an API
    :param url: str
    :param token: str
    :return: dict
    """
    n = max_tries
    while n > 0:
        try:
            headers = {'Accept': 'application/json', 'auth': token}
            resp = requests.get(url, headers=headers)
            if resp.status_code == 200:
                return resp.json()
            else:
                log('error', f'Error fetching data: {resp.status_code}')
                return None

        except requests.exceptions.RequestException:
            sleep(60)
            n -= 1
            log('error', 'Retrying fetching data')
            continue

    log('error', 'Error fetching data')
    return None


def geomap_address(df):
    """
    Map the address of members on a map
    :param df: pd.DataFrame
    :return: None
    """
    key = get_secret("TomTomAPI")["key"]

    geolocator = TomTom(api_key=key, timeout=10)

    location = geolocator.geocode("Bruxelles, Belgique")
    m = folium.Map([location.latitude, location.longitude], zoom_start=8)

    for idx, r in df.iterrows():
        sleep(0.3)
        if idx > 1000:
            break
        if not r["cotisationExpiration"]:
            continue
        country = {
            "BE": "Belgique"
        }
        address = ""
        try:
            pays = country[r["adressePays"]].strip()
            if not pays:
                pays = "Belgique"
            address = str(r["adresseNumero"]) + " " + r["adresseRue"].strip() + ", " + str(int(r["adresseCp"])) + " " + \
                      r[
                          "adresseVille"].strip() + ", " + pays

            if not address:
                continue

            location = geolocator.geocode(address)
            # print(location)
            folium.Marker(
                location=[location.latitude, location.longitude],
                tooltip=r["prenom"] + " " + r["nom"],
                popup=address,
                icon=folium.Icon(color="red"),
            ).add_to(m)

        except Exception:
            print('ERROR', "geocode error for " + r["prenom"] + " " + r["nom"] + ":  " + address)
            continue
        # log('INFO', r["prenom"] + " " + r["nom"])

    m.save(config['geomap']['index'])
    log('info', 'Member map updated')


def upd_members_db_to_google_sheet(gc, geomap=False):
    """
    Update the members data to a Google Sheet
    :param gc: gspread.Client
    :return
    """
    columns = [
        "title", "_owner", "_createdDate", "_updatedDate", "email", "emailBounced", "nom", "prenom",
        "cotisationExpiration",
        "instrument1", "categorie1", "instrument2", "categorie2", "prefM", "prefR", "prefS", "prefT", "prefO",
        "adresseRue", "adresseNumero", "adresseBoite", "adresseCp", "adresseVille", "adressePays",
        "telMobC", "telMobP", "telMobN", "telHomeC", "telHomeP", "telHomeN", "telWorkC", "telWorkP",
        "telWorkN", "anneeNaissance", "memberPic", "instrument1Fr", "instrument1Nl", "instrument1En",
        "instrument2Fr", "instrument2Nl", "instrument2En", "adressePaysFr", "adressePaysNl", "adressePaysEn",
        "lastfeePaymentYear", "_id"
    ]

    ws = open_sheet(gc, "cambristiMemberSheetID")
    if not ws:
        log('error', 'Member sheet not found')
        return

    _, token = get_user_pwd("cambristiApiToken")
    data = fetch_data(config['cambristi']['members_endpoint'], token)
    if data:
        df = pd.DataFrame(data["items"]).fillna('').astype("string")
        df = df[columns]
        update_data(ws, df, "A1")
        if geomap:
            today = datetime.datetime.now(datetime.UTC)
            df['cotisationExpirationDate'] = pd.to_datetime(df['cotisationExpiration'])
            df['cotisationExpirationDays'] = (df['cotisationExpirationDate'] - today).dt.days
            df = df[df['cotisationExpirationDays'] > 0]
            geomap_address(df)

        log('info', 'Members updated to Google Sheet')


def upd_members_plans_to_google_sheet(gc):
    """
    Update the members plans data to a Google Sheet
    :param gc: gspread.Client
    :return
    """
    columns = [
        "_id", "nomMembre", "prenomMembre", "emailMembre", "planName", "planDescription", "price",
        "paymentStatus", "_createdDate", "validUntil", "_updatedDate", "validFrom", "recurring", "id",
        "dateCreated", "status", "roleId", "wixPayOrderId", "memberId", "orderType", "cancellationReason",
        "planId", "cancellationInitiator", "validFor"
    ]

    ws = open_sheet(gc, "cambristiMembersPlanEventsSheetID")
    if not ws:
        log('error', 'Plan sheet not found')
        return

    _, token = get_user_pwd("cambristiApiToken")
    data = fetch_data(config['cambristi']['orders_endpoint'], token)
    if data:
        df = pd.DataFrame(data["items"]).fillna('').astype("string")
        df = df[columns]
        update_data(ws, df, "A1")
        log('info', 'Plans updated to Google Sheet')


def db_connect(url, token, org):
    try:
        client = influxdb_client.InfluxDBClient(url=url, token=token, org=org,
                                                default_configuration={"batch_size": 10000},
                                                verify_ssl=False)
        return client
    except influxdb_client.client.exceptions.InfluxDBError as e:
        logging.error('InfluxDB client error: %s', e)
        sys.exit(1)


def _parse_message_content(msg):
    """Parse log message content if it is a JSON string."""
    if isinstance(msg, str) and (msg.startswith('[') or msg.startswith('{')):
        try:
            return json.loads(msg)
        except (json.JSONDecodeError, TypeError):
            return msg
    return msg


def _extract_log_details(msg, rec):
    """Extract severity, module, and message text from log record."""
    hdr = msg[0] if isinstance(msg, list) and len(msg) == 1 else ""
    module = hdr.get('module', "") if isinstance(hdr, dict) else ""
    severity = hdr.get('severity', "") if isinstance(hdr, dict) else ""
    line = ""

    if 'sourceLocation' in rec:
        module = rec['sourceLocation'].get('file', module)
        line = f":{rec['sourceLocation']['line']}" if 'line' in rec['sourceLocation'] else ""

    try:
        _msg = msg[0].get('message', "") if len(msg) == 1 and isinstance(msg[0], dict) else msg
        if severity == "" and isinstance(_msg, dict):
            severity = _msg.get('severity', "")
            module = f"{module} - {_msg.get('module', '')} line:{line}"
            _msg = _msg.get('message', "") + _msg.get('event', "")
        if isinstance(_msg, str) and 'Error' in _msg:
            severity = 'ERROR'
    except (KeyError, TypeError, IndexError):
        _msg = msg

    return severity, module, _msg


def _process_log_record(record):
    """
    Process a single InfluxDB record and return list of rows to append.
    """
    try:
        rec = json.loads(record.get_value())
        mode = jp.parse('labels.viewMode').find(rec)[0].value
    except (json.JSONDecodeError, TypeError, IndexError):
        return []

    if mode != 'Site':
        return []

    rows = []
    q = jp.parse('jsonPayload.message')
    for match in q.find(rec):
        msg = _parse_message_content(match.value)

        if isinstance(msg, str) and 'Running the code for' in msg:
            continue

        severity, module, _msg_text = _extract_log_details(msg, rec)
        row = [rec.get('timestamp', ''), severity, module, str(_msg_text)[:512]]
        rows.append(row)
    return rows


def upd_logs_google_sheet(gc, ndays):
    """
    Update the logs data to a Google Sheet
    :param gc: gspread.Client
    :param ndays: number of days to look back
    :return
    """
    cfg = get_secret('InfluxDbApiToken')
    bucket = cfg['bucket']
    db_token = cfg['token']
    org = cfg['org']
    db_url = cfg['url']

    client = db_connect(db_url, db_token, org)

    query_api = client.query_api()
    query = f"""from(bucket: "{bucket}")
     |> range(start: -{ndays}d)
     |> filter(fn: (r) => r._measurement == "Cambristi Production")
     |> sort(columns: ["_time"], desc: true) """
    import csv
    csv.field_size_limit(10 ** 7)  # Fixe la taille maximale par champ à 10 Mo
    tables = query_api.query(query, org=org)

    all_rows = [['timestamp', 'severity', 'module', 'msg']]
    for table in tables:
        for record in table.records:
            all_rows.extend(_process_log_record(record))

    ws = open_sheet(gc, "cambristiLogSheetID")
    if not ws:
        log('error', 'Log sheet not found')
        return
    ws.clear()
    ws.update(range_name="A1", values=all_rows)
    log('info', 'Logs updated to Google Sheet')


def fmt_musicians(gr, act, df_participants):
    mlist = ""
    for m in eval(gr.musicians):
        p = df_participants[(df_participants['memberId'] == m) & (df_participants['stageId'] == act._id)]
        if len(p) > 0:
            paid = ' [25€] ' if (p.isCotiPaid.values[0] == "False") else ' [ ok ] '
            mbr = ' [Mbre] ' if (p.member.values[0] == "True") else ' [Extrn] '
            mlist += mbr + paid + p.participantName.values[0] + ' (' + p.participantEmail.values[
                0] + ') ' + ', ' + \
                     p.instrument.values[0] + '\n'
    gr.musicians = mlist
    return gr


def upd_activities_to_google_sheet(gc):
    df_activities = pd.DataFrame()
    # create activities summary sheet
    wb = open_workbook(gc, "CambristiActivitySheetId")
    ws = open_worksheet(wb, "Activities")
    _, token = get_user_pwd("cambristiApiToken")
    all_activities = fetch_data(config['cambristi']['activities_endpoint'], token)
    df_all_activities = pd.DataFrame(all_activities["items"]).fillna('').astype("string")

    members = fetch_data(config['cambristi']['members_endpoint'], token)
    df_members = pd.DataFrame(members["items"]).fillna('').astype("string")

    orders = fetch_data(config['cambristi']['orders_endpoint'], token)
    df_orders = pd.DataFrame(orders["items"]).fillna('').astype("string")

    activities = {"items": []}

    # just the most important fields
    for item in all_activities["items"]:
        item2 = {"activityName": item["title"],
                 "activityType": item["typeActivite"],
                 "date": item["dateDebut"].split("T")[0],
                 "location": item["nomLieu"],
                 "address": item["lieu"]["formatted"],
                 "responsibles": item["adminEmail"] + ", " + item["adminEmail1"]}
        activities["items"].append(item2)

    # create a dataframe from the list of dictionaries
    df_activities = pd.DataFrame(activities["items"]).fillna('').astype("string")
    columns = activities["items"][0].keys()
    df_activities = df_activities[columns]
    # and update the sheet
    update_data(ws, df_activities, "A1")

    # Get now the groups and participants
    groups = fetch_data(config['cambristi']['groups_endpoint'], token)
    df_groups = pd.DataFrame(groups["items"]).fillna('').astype("string")
    columns = groups["items"][0].keys()
    df_groups = df_groups[columns]

    all_participants = fetch_data(config['cambristi']['participants_endpoint'], token)
    participants = {"items": []}

    # ensure to have all fields populated
    for item in all_participants["items"]:
        item2 = {
            "id": item["_id"],
            "member": is_member(item, df_members),
            "participantName": item["prenom"] + " " + item["nom"],
            "participantEmail": item["email"],
            "memberId": item["memberId"],
            "planEventId": item["paymtEventId"] if "paymtEventId" in item else "",
            "stageId": item["stageId"],
            "stageName": item["stageName"],
            'groupId': item["groupId"],
            "groupName": item["groupName"],
            'instrument': item["instrument"],
            'level': item["level"] if "level" in item else "",
            "isYoung": item["isYoung"] if "isYoung" in item else False,
            "isCotiPaid": is_coti_paid(item, df_orders),
            # 'paidAmount': item["paidAmount"] if "paidAmount" in item else "",
            'note': item["note"] if "note" in item else "",
        }
        participants["items"].append(item2)

    df_participants = pd.DataFrame(participants["items"]).fillna('').astype("string")
    columns = participants["items"][0].keys()
    df_participants = df_participants[columns]

    # Start filling or creating one sheet per activity
    for _, activity in df_all_activities.iterrows():
        #
        if datetime.datetime.combine(
                datetime.datetime.strptime(activity.dateDebut, "%Y-%m-%d").date(),
                datetime.time.min,
                tzinfo=datetime.timezone.utc,
        ) < datetime.datetime.now(datetime.timezone.utc):
            continue

        try:
            ws = wb.worksheet(activity.title)
        except gspread.exceptions.WorksheetNotFound:
            ws = wb.add_worksheet(activity.title, 100, 20)

        # filter the groups on the current activity
        df_sub_groups = df_groups[df_groups['stageId'] == activity._id]
        columns = ['Group', 'IsConfirmed', 'Responsible', 'Work to play', 'Duration', 'Musicians']

        df_sub_groups = df_sub_groups.apply(fmt_musicians, args=(activity, df_participants), axis=1)
        data = df_sub_groups[['title', 'isConfirmed', 'responsibleEmail', 'workToPlay', 'duration', 'musicians']]
        update_data(ws, data, "A1:F15")
        ws.format("A1:F15", {
            "verticalAlignment": "TOP",
            "wrapStrategy": "WRAP",
        })
        gf.set_column_widths(ws, [('C', 250), ('D', 500), ('F', 750)])

        sleep(3)

    log('info', 'Activities Sheet updated to Google Sheet')


# custom exception hook
def custom_hook(args):
    # report the failure
    print(f'Thread failed: {args.exc_value}')


def is_coti_paid(item, df_orders):
    orders = df_orders[(df_orders.emailMembre == item["email"]) & (df_orders.planName.str.contains("Cotisation"))]
    now = datetime.datetime.now().date()
    for _, order in orders.iterrows():
        valid_until = datetime.datetime.fromisoformat(order.validUntil).date()
        diff = (valid_until - now).days
        if diff > 0:
            return "True"
    return "False"


def is_member(item, df_members):
    row = df_members[df_members.email == item["email"]]
    if len(row) == 0:
        return "False"
    title = df_members[df_members.email == item["email"]]["title"].values[0]
    return "True" if title == "member" else "False"

if __name__ == '__main__':
    """
    Update the members, members plans and logs data to Google Sheets
    """

    parser = argparse.ArgumentParser()
    parser.add_argument("-l", "--log", help="Get log files", action="store_true")
    parser.add_argument("-m", "--members", help="upload members data", action="store_true")
    parser.add_argument("-p", "--plans", help="upload plans", action="store_true")
    parser.add_argument("-a", "--activities", help="upload activities", action="store_true")
    parser.add_argument("-d", "--days", help="nr of days of log files", type=int)
    parser.add_argument("-g", "--geomap", help="Map members address on a map", action="store_true")
    parser.add_argument("-t", "--test", help="Test mode", action="store_true")
    args = parser.parse_args()

    if len(sys.argv) <= 1:
        args.log = True
        args.members = True
        args.plans = True
        args.activities = True

    if args.geomap:
        args.members = True

    if args.test:
        test_mode = True

    gc = gc_login()
    threads = []
    # set the exception hook
    # threading.excepthook = custom_hook

    if args.members:
        # upd_members_db_to_google_sheet(gc, args.geomap)
        t = threading.Thread(target=upd_members_db_to_google_sheet, args=(gc, args.geomap))
        threads.append(t)

    if args.plans:
        # upd_members_plans_to_google_sheet(gc)
        t = threading.Thread(target=upd_members_plans_to_google_sheet, args=(gc,))
        threads.append(t)

    if args.log:
        if args.days:
            days = args.days
        elif 'logs' in config and 'days' in config['logs']:
            days = config['logs']['days']
        else:
            days = 7
        t = threading.Thread(target=upd_logs_google_sheet, args=(gc, days))
        threads.append(t)

    if args.activities:
        # upd_activities_to_google_sheet(gc)
        t = threading.Thread(target=upd_activities_to_google_sheet, args=(gc,))
        threads.append(t)

    for t in threads:
        t.start()

    for t in threads:
        t.join()
