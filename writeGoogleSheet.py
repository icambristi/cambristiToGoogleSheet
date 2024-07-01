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
from getSecrets import get_secret, get_user_pwd
from oauth2client.service_account import ServiceAccountCredentials


def log(severity, msg):
    if severity == 'info':
        logging.info(msg)
    elif severity == 'debug':
        logging.debug(msg)
    elif severity == 'warning':
        logging.warning(msg)
    elif severity == 'error':
        logging.error(msg)

    hash_object = hashlib.sha256(b'Cambristi Sushi RPI')
    pbHash = hash_object.hexdigest()
    headers = {"Content-Type": "application/json"}
    data = {
        "timestamp": datetime.datetime.now().isoformat(),
        "event_id": str(uuid.uuid4()),
        "severity": severity,
        "message": msg
    }
    resp = requests.post(f'https://home.mayeur.be:6123/log?token={pbHash}&tag=wixtogoogle',
                         headers=headers, json=data)
    if resp.status_code != 201:
        logging.error(resp.status_code, resp.text)


def upd_members_db_to_google_sheet():
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

    scope = ['https://www.googleapis.com/auth/spreadsheets',
             'https://spreadsheets.google.com/feeds',
             'https://www.googleapis.com/auth/drive']
    #
    _, sa = get_user_pwd("cambristiGoogleServiceAccount")
    creds = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(sa), scope)
    gc = gspread.authorize(creds)

    _, spreadsheet_id = get_user_pwd("cambristiMemberSheetID")
    sh = gc.open_by_key(spreadsheet_id)
    ws = sh.sheet1

    _, token = get_user_pwd("cambristiApiToken")

    headers = {'Accept': 'application/json',
               'auth': token
               }

    URL = "https://www.cambristi.com/_functions/members/"

    resp = requests.get(URL, headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        # convert all values to string
        df = pd.DataFrame(data["items"]).fillna('').astype("string")
        # re-order the column
        df = df[columns]
        ws.clear()
        ws.update(range_name="A1", values=[df.columns.values.tolist()] + df.values.tolist())
        log('info', 'Members updated to Google Sheet')
    else:
        log('error', 'Upload to Google sheet error ' + str(resp.status_code))


def upd_members_plans_to_google_sheet():
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
    scope = ['https://www.googleapis.com/auth/spreadsheets',
             'https://spreadsheets.google.com/feeds',
             'https://www.googleapis.com/auth/drive']
    #
    _, sa = get_user_pwd("cambristiGoogleServiceAccount")
    creds = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(sa), scope)
    gc = gspread.authorize(creds)

    _, spreadsheet_id = get_user_pwd("cambristiMembersPlanEventsSheetID")
    sh = gc.open_by_key(spreadsheet_id)
    ws = sh.sheet1

    _, token = get_user_pwd("cambristiApiToken")

    headers = {'Accept': 'application/json',
               'auth': token
               }

    URL = "https://www.cambristi.com/_functions/orders/"

    resp = requests.get(URL, headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        # convert all values to string
        df = pd.DataFrame(data["items"]).fillna('').astype("string")
        # re-order the column
        df = df[columns]
        ws.clear()
        ws.update(range_name="A1", values=[df.columns.values.tolist()] + df.values.tolist())
        log('info', 'Plans updated to Google Sheet')
    else:
        log('error', 'Upload to Google sheet error ' + str(resp.status_code))


def upd_logs_google_sheet():
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

    query = """from(bucket: "cambristi")
     |> range(start: -7d)
     |> filter(fn: (r) => r._measurement == "Cambristi Production")
     |> sort(columns: ["_time"], desc: true) """
    tables = query_api.query(query, org="Home")

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

    scope = ['https://www.googleapis.com/auth/spreadsheets',
             'https://spreadsheets.google.com/feeds',
             'https://www.googleapis.com/auth/drive']

    #
    _, sa = get_user_pwd("cambristiGoogleServiceAccount")
    creds = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(sa), scope)
    gc = gspread.authorize(creds)

    _, spreadsheet_id = get_user_pwd("cambristiLogSheetID")
    sh = gc.open_by_key(spreadsheet_id)
    ws = sh.sheet1

    ws.clear()
    ws.update(range_name="A1", values=all_rows)
    log('info', 'Logs updated to Google Sheet')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        upd_members_db_to_google_sheet()
        sleep(30)
        upd_members_plans_to_google_sheet()
        sleep(30)
    upd_logs_google_sheet()
