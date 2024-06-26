import json
import logging

import influxdb_client
import jsonpath_ng.ext as jp
import yaml

from get_secrets import get_secret

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s',
                    datefmt='%m/%d/%Y %I:%M:%S %p')

CONFIG_FILE = "config.yml"
config = yaml.safe_load(open(CONFIG_FILE))

sheetID = 'cambristiLogSheetID'

bucket = config['db']['bucket']
_, db_token = get_secret(config['db']['token'])
org = config['db']['org']
db_url = config['db']['url']
write_api = None
try:
    client = influxdb_client.InfluxDBClient(url=db_url, token=db_token, org=org)
except Exception as e:
    logging.error(f'client {str(e)}')

query_api = client.query_api()

query = """from(bucket: "cambristi")
 |> range(start: -1d)
 |> filter(fn: (r) => r._measurement == "Cambristi Production")
 |> sort(columns: ["_time"], desc: true) """
tables = query_api.query(query, org="Home")

all_rows = []
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

            if isinstance(msg, list) and len(msg) == 1:
                hdr = msg[0]

            module = ""

            if 'module' in str(hdr):
                module = hdr['module']
            elif 'sourceLocation' in rec:
                module = rec['sourceLocation']['file']

            if 'severity' in str(hdr):
                severity = hdr['severity']
            else:
                severity = ""

            row = [rec['timestamp'], severity, module, json.dumps(msg, indent=4)]
            all_rows.append(row)
        # print(json.dumps(rec, indent=4))

        # print(record)
