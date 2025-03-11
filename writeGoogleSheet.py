#!/usr/bin/env python3
import argparse
import datetime
import hashlib
import json
import logging
import os.path
import sys
import uuid
from time import sleep

import folium
import gspread
import influxdb_client
import jsonpath_ng.ext as jp
import pandas as pd
import requests
import yaml
from geopy.geocoders import TomTom
from getSecrets import get_secret, get_user_pwd
from oauth2client.service_account import ServiceAccountCredentials


def load_config():
    """
    Load the configuration file
    :return: dict

    """
    try:
        return yaml.safe_load(open('/app/config.yml'))
    except FileNotFoundError:
        return yaml.safe_load(open('config.yml'))


config = load_config()


def log(severity, msg):
    """
    Log a message to the console and to the logs API
    :param severity: str
    :param msg: str
    :return: None

    """
    logging_function = getattr(logging, severity, logging.info)
    logging_function(msg)

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
    send_log_request(url, pbHash, tag, headers, data)


def send_log_request(url, pbHash, tag, headers, data):
    """
    Send a log request to the logs API
    :param url: str
    :param pbHash: str
    :param tag: str
    :param headers: dict
    :param data: dict
    :return: None

    """
    try:
        resp = requests.post(f'{url}?token={pbHash}&tag={tag}', headers=headers, json=data)
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

    creds = ServiceAccountCredentials.from_json_keyfile_dict(get_secret("cambristiGoogleServiceAccount"), scope)
    return gspread.authorize(creds)


def open_sheet(client, ws_id, sheet=None):
    """
    Open a Google Sheet
    :param client: gspread.Client
    :param ws_id: str
    :param sheet: str
    :return: gspread.Worksheet

    """
    _, spreadsheet_id = get_user_pwd(ws_id)
    wb = client.open_by_key(spreadsheet_id)
    try:
        return wb.worksheet(sheet) if sheet else wb.sheet1
    except gspread.exceptions.WorksheetNotFound:
        return None


def update_data(ws, df, range, columns):
    """
    Update a Google Sheet with data
    :param ws: gspread.Worksheet
    :param data: dict
    :param range: str
    :param columns: list
    :return: None

    """

    ws.clear()
    ws.update(range_name=range, values=[df.columns.values.tolist()] + df.values.tolist())


def fetch_data(url, token):
    """
    Fetch data from an API
    :param url: str
    :param token: str
    :return: dict
    """
    headers = {'Accept': 'application/json', 'auth': token}
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        return resp.json()
    else:
        log('error', f'Error fetching data: {resp.status_code}')
        return None


def geomap_address(df):
    """
    Map the address of members on a map
    :param df: pd.DataFrame
    :return: None
    """
    key = get_secret("TomTomAPI")["key"]

    # geolocator = Nominatim(user_agent="my_geocoder")
    geolocator = TomTom(api_key=key)

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

            location = geolocator.geocode(address)
            # print(location)
            folium.Marker(
                location=[location.latitude, location.longitude],
                tooltip=r["prenom"] + " " + r["nom"],
                popup=address,
                icon=folium.Icon(color="red"),
            ).add_to(m)
        except:
            print('ERROR', "geocode error for " + r["prenom"] + " " + r["nom"] + ":  " + address)
            continue
        # log('INFO', r["prenom"] + " " + r["nom"])

    if os.path.exists(config['geomap']['index']):
        m.save(config['geomap']['index'])
    else:
        m.save("geomap.html")


def upd_members_db_to_google_sheet(gc, geomap=False):
    """
    Update the members data to a Google Sheet
    :param gc: gspread.Client
    :return
    """
    columns = [
        "_owner", "_createdDate", "_updatedDate", "email", "nom", "prenom", "cotisationExpiration",
        "instrument1", "categorie1", "instrument2", "categorie2", "prefR", "prefS", "prefT", "prefO",
        "adresseRue", "adresseNumero", "adresseBoite", "adresseCp", "adresseVille", "adressePays",
        "telMobC", "telMobP", "telMobN", "telHomeC", "telHomeP", "telHomeN", "telWorkC", "telWorkP",
        "telWorkN", "anneeNaissance", "memberPic", "instrument1Fr", "instrument1Nl", "instrument1En",
        "instrument2Fr", "instrument2Nl", "instrument2En", "adressePaysFr", "adressePaysNl", "adressePaysEn",
        "lastfeePaymentYear", "_id"
    ]

    ws = open_sheet(gc, "cambristiMemberSheetID")
    _, token = get_user_pwd("cambristiApiToken")
    data = fetch_data(config['cambristi']['members_endpoint'], token)
    if data:
        df = pd.DataFrame(data["items"]).fillna('').astype("string")
        df = df[columns]
        update_data(ws, df, "A1", columns)
        if geomap:
            # df_filtered = df[df['cotisationExpiration'] != '']
            today = datetime.datetime.now(datetime.UTC)
            df['cotisationExpirationDate'] = pd.to_datetime(df['cotisationExpiration'])
            df['cotisationExpirationnDays'] = (df['cotisationExpirationDate'] - today).dt.days
            df = df[df['cotisationExpirationnDays'] > 0]
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
    _, token = get_user_pwd("cambristiApiToken")
    data = fetch_data(config['cambristi']['orders_endpoint'], token)
    if data:
        df = pd.DataFrame(data["items"]).fillna('').astype("string")
        df = df[columns]
        update_data(ws, df, "A1", columns)
        log('info', 'Plans updated to Google Sheet')


def upd_logs_google_sheet(gc, ndays):
    """
    Update the logs data to a Google Sheet
    :param gc: gspread.Client
    :return
    """
    if not ndays:
        ndays = config['logs']['ndays']
    cfg = get_secret('InfluxDbApiToken')
    bucket = cfg['bucket']
    db_token = cfg['token']
    org = cfg['org']
    db_url = cfg['url']

    try:
        client = influxdb_client.InfluxDBClient(url=db_url, token=db_token, org=org)
    except Exception as e:
        logging.error(f'client {str(e)}')
        sys.exit(1)

    query_api = client.query_api()
    query = f"""from(bucket: "{bucket}")
     |> range(start: -{ndays}d)
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
                    except Exception:
                        continue

                if 'Running the code for' in msg:
                    continue

                hdr = msg[0] if isinstance(msg, list) and len(msg) == 1 else ""
                module = hdr.get('module', "") if isinstance(hdr, dict) else ""
                severity = hdr.get('severity', "") if isinstance(hdr, dict) else ""

                if 'sourceLocation' in rec:
                    module = rec['sourceLocation']['file']
                    if 'line' in rec['sourceLocation']:
                        module += f":{rec['sourceLocation']['line']} in {module}"

                try:
                    _msg = msg[0].get('message', "") if len(msg) == 1 and isinstance(msg[0], dict) else msg
                except KeyError as e:
                    pass
                row = [rec['timestamp'], severity, module, str(_msg)[:512]]
                all_rows.append(row)

    ws = open_sheet(gc, "cambristiLogSheetID")
    ws.clear()
    ws.update(range_name="A1", values=all_rows)
    log('info', 'Logs updated to Google Sheet')


def upd_activities_to_google_sheet(gc):
    # columns = [
    #     "_id", "title", "description", "_createdDate", "_updatedDate", "_owner", "dateDebut", "time", "dateFin",
    #     "nomLieu", "lieu", "adminEmail", "adminEmail1", "adminId", "adminId1", "typeActivite",  "prixMembre",
    #     "prixNonMembre", "prixJeune", "contactEmail", "contactFullName", "message", "show",
    #
    # ]

    columns = ["activityName", "activityType", "date", "location", "address", "responsibles"]
    ws = open_sheet(gc, "CambristiActivitySheetId")
    _, token = get_user_pwd("cambristiApiToken")
    data = fetch_data(config['cambristi']['activities_endpoint'], token)
    if data:
        data2 = {"items": []}

        for item in data["items"]:
            item2 = {}
            item2["activityName"] = item["title"]
            item2["activityType"] = item["typeActivite"]
            item2["date"] = item["dateDebut"].split("T")[0]
            item2["location"] = item["nomLieu"]
            item2["address"] = item["lieu"]["formatted"]
            item2["responsibles"] = item["adminEmail"] + ", " + item["adminEmail1"]
            data2["items"].append(item2)

        df = pd.DataFrame(data2["items"]).fillna('').astype("string")
        df = df[columns]
        update_data(ws, df, "A1", columns)
        log('info', 'Activities Sheet updated to Google Sheet')


if __name__ == '__main__':
    """
    Update the members, members plans and logs data to Google Sheets
    """

    parser = argparse.ArgumentParser()
    parser.add_argument("-l", "--log", help="Get log files", action="store_true")
    parser.add_argument("-m", "--members", help="Get log files", action="store_true")
    parser.add_argument("-p", "--plans", help="Get log files", action="store_true")
    parser.add_argument("-a", "--activities", help="Get log files", action="store_true")
    parser.add_argument("-d", "--days", help="nr of days of log files", type=int)
    parser.add_argument("-g", "--geomap", help="Map members address on a map", action="store_true")
    args = parser.parse_args()

    if len(sys.argv) <= 1:
        args.log = True
        args.members = True
        args.plans = True
        args.activities = True
        args.geomap = True

    gc = gc_login()

    if args.members:
        upd_members_db_to_google_sheet(gc, args.geomap)
        sleep(1)
    if args.plans:
        upd_members_plans_to_google_sheet(gc)
        sleep(1)
    if args.log:
        upd_logs_google_sheet(gc, args.days)
        sleep(1)
    if args.activities:
        upd_activities_to_google_sheet(gc)
