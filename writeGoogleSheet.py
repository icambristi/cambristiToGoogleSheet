import datetime
import hashlib
import json
import logging
import uuid

import gspread
import pandas as pd
import requests
from oauth2client.service_account import ServiceAccountCredentials

from get_secrets import get_secret


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
    _, sa = get_secret("cambristiGoogleServiceAccount")
    creds = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(sa), scope)
    gc = gspread.authorize(creds)

    _, spreadsheet_id = get_secret("cambristiMemberSheetID")
    sh = gc.open_by_key(spreadsheet_id)
    ws = sh.sheet1

    _, token = get_secret("cambristiApiToken")

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
    _, sa = get_secret("cambristiGoogleServiceAccount")
    creds = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(sa), scope)
    gc = gspread.authorize(creds)

    _, spreadsheet_id = get_secret("cambristiMembersPlanEventsSheetID")
    sh = gc.open_by_key(spreadsheet_id)
    ws = sh.sheet1

    _, token = get_secret("cambristiApiToken")

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


if __name__ == '__main__':
    upd_members_db_to_google_sheet()
    upd_members_plans_to_google_sheet()
