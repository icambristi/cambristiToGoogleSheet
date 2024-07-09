import datetime
import hashlib
import json
import logging
import sys
import uuid
from time import sleep

import gspread
import influxdb_client
import jsonpath_ng.ext as jp
import pandas as pd
import requests
import yaml
from getSecrets import get_secret, get_user_pwd
from oauth2client.service_account import ServiceAccountCredentials

try:
    config = yaml.safe_load(open('/app/config.yml'))
except FileNotFoundError:
    config = yaml.safe_load(open('config.yml'))


def log(severity, msg):
    if severity == 'info':
        logging.info(msg)
    elif severity == 'debug':
        logging.debug(msg)
    elif severity == 'warning':
        logging.warning(msg)
    elif severity == 'error':
        logging.error(msg)

    hash_object = hashlib.sha256(config['logs']['username'].encode())
    pbHash = hash_object.hexdigest()
    url = config['logs']['url']
    tag = config['logs']['tag']
    headers = {"Content-Type": "application/json"}
    data = {
        "timestamp": datetime.datetime.now().isoformat(),
        "event_id": str(uuid.uuid4()),
        "severity": severity,
        "message": msg
    }
    try:
        resp = requests.post(f'{url}?token={pbHash}&tag={tag}', headers=headers, json=data)
        if resp.status_code != 201:
            logging.error(resp.status_code, resp.text)
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

    creds = ServiceAccountCredentials.from_json_keyfile_dict(get_secret("cambristiGoogleServiceAccount"), scope)
    return gspread.authorize(creds)


def open_sheet(client, ws_id, sheet=None):
    _, spreadsheet_id = get_user_pwd(ws_id)
    wb = client.open_by_key(spreadsheet_id)
    if sheet is None:
        return wb.sheet1
    else:
        try:
            return wb.worksheet(sheet)
        except gspread.exceptions.WorksheetNotFound:
            return None


def update_data(ws, data, range, columns):
    # convert all values to string
    df = pd.DataFrame(data["items"]).fillna('').astype("string")
    # re-order the column
    df = df[columns]
    ws.clear()
    ws.update(range_name=range, values=[df.columns.values.tolist()] + df.values.tolist())


def upd_members_db_to_google_sheet(gc):
    columns = [
        "_owner",
        "_createdDate",
        "_updatedDate",
        "email",
        "nom",
        "prenom",
        "cotisationExpiration",
        "instrument1",
        "categorie1",
        "instrument2",
        "categorie2",
        "prefR",
        "prefS",
        "prefT",
        "prefO",
        "adresseRue",
        "adresseNumero",
        "adresseBoite",
        "adresseCp",
        "adresseVille",
        "adressePays",
        "telMobC",
        "telMobP",
        "telMobN",
        "telHomeC",
        "telHomeP",
        "telHomeN",
        "telWorkC",
        "telWorkP",
        "telWorkN",
        "anneeNaissance",
        "memberPic",
        "instrument1Fr",
        "instrument1Nl",
        "instrument1En",
        "instrument2Fr",
        "instrument2Nl",
        "instrument2En",
        "adressePaysFr",
        "adressePaysNl",
        "adressePaysEn",
        "lastfeePaymentYear",
        "_id"
    ]

    ws = open_sheet(gc, "cambristiMemberSheetID")
    _, token = get_user_pwd("cambristiApiToken")
    headers = {'Accept': 'application/json',
               'auth': token
               }
    url = config['cambristi']['members_endpoint']
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        update_data(ws, data, "A1", columns)
        log('info', 'Members updated to Google Sheet')
    else:
        log('error', 'Upload to Google sheet error ' + str(resp.status_code))


def upd_members_plans_to_google_sheet(gc):
    columns = [
        "_id",
        "nomMembre",
        "prenomMembre",
        "emailMembre",
        "planName",
        "planDescription",
        "price",
        "paymentStatus",
        "_createdDate",
        "validUntil",
        "_updatedDate",
        "validFrom",
        "recurring",
        "id",
        "dateCreated",
        "status",
        "roleId",
        "wixPayOrderId",
        "memberId",
        "orderType",
        "cancellationReason",
        "planId",
        "cancellationInitiator",
        "validFor"
    ]

    ws = open_sheet(gc, "cambristiMembersPlanEventsSheetID")

    _, token = get_user_pwd("cambristiApiToken")
    headers = {'Accept': 'application/json',
               'auth': token
               }
    url = config['cambristi']['orders_endpoint']
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        update_data(ws, data, "A1", columns)
        log('info', 'Plans updated to Google Sheet')
    else:
        log('error', 'Upload to Google sheet error ' + str(resp.status_code))


def upd_logs_google_sheet(gc):
    cfg = get_secret('InfluxDbApiToken')
    bucket = cfg['bucket']
    db_token = cfg['token']
    org = cfg['org']
    db_url = cfg['url']
    client = None

    try:
        client = influxdb_client.InfluxDBClient(url=db_url, token=db_token, org=org)
    except Exception as e:
        logging.error(f'client {str(e)}')
        sys.exit(1)

    query_api = client.query_api()

    query = f"""from(bucket: "{bucket}")
     |> range(start: -7d)
     |> filter(fn: (r) => r._measurement == "Cambristi Production")
     |> sort(columns: ["_time"], desc: true) """
    tables = query_api.query(query, org=org)

    all_rows = [['timestamp', 'severity', 'module', 'msg']]
    for table in tables:
        for record in table.records:
            rec = json.loads(record.get_value())

            q = jp.parse('jsonPayload.message')
            for match in q.find(rec):
                msg = match.value
                if msg[0] == '[' or msg[0] == "{":
                    try:
                        msg = json.loads(msg)
                    except Exception as e:
                        continue

                if 'Running the code for' in msg:
                    continue

                hdr = ""
                if isinstance(msg, list) and len(msg) == 1:
                    hdr = msg[0]

                module = ""
                severity = ""

                if isinstance(hdr, dict) and 'module' in hdr:
                    module = hdr['module']
                if 'sourceLocation' in rec:
                    module = rec['sourceLocation']['file'] + ":" + str(rec['sourceLocation']['line']) + " in " + module

                if isinstance(hdr, dict) and 'severity' in hdr:
                    severity = hdr['severity']

                _msg = msg
                if len(msg) == 1 and isinstance(msg[0], dict):
                    if 'message' in msg[0]:
                        _msg = msg[0]['message']

                    if 'event' in msg[0]:
                        _msg += " event:" + str(msg[0]['event'])

                row = [rec['timestamp'], severity, module, str(_msg)[:512]]
                all_rows.append(row)

    ws = open_sheet(gc, "cambristiLogSheetID")
    ws.clear()
    ws.update(range_name="A1", values=all_rows)
    log('info', 'Logs updated to Google Sheet')


if __name__ == '__main__':
    gc = gc_login()
    if len(sys.argv) < 2:
        upd_members_db_to_google_sheet(gc)
        sleep(1)
        upd_members_plans_to_google_sheet(gc)
        sleep(1)
    upd_logs_google_sheet(gc)
