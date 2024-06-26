import logging
from os import getenv
from os.path import join

import yaml

_config_file = "~/.config/.vault/vault.yml"
_home = getenv("HOME")
_config = yaml.safe_load(open(join(_home, _config_file.replace("~/", ''))))
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s',
                    datefmt='%m/%d/%Y %I:%M:%S %p')


def get_secret(id: str):
    """
    :param id: The ID of the secret to retrieve
    :return: A tuple containing the key-value pairs of the secret or a json object for complex secrets
             or (None, None) if the secret retrieval fails

    This method retrieves a secret from a Vault server using the provided ID. I
    t sends a GET request to the Vault server with the necessary headers and authentication token.
    If the request is successful (status code 200), the method extracts the key-value pairs
    from the response JSON and returns them as a tuple.
    If the request fails, the method prints an HTTP error message and returns (None, None).
    """
    import requests
    base_url = _config['vault']['vault_addr']
    certs = join(_home, _config['vault']['certs'].replace("~/", ''))
    token = _config['vault']['token']

    headers = {"X-Vault-Token": token}
    uri = "/v1/secret/data/"
    url = f"{base_url}{uri}{id}"
    resp = requests.get(url, headers=headers, verify=certs)
    if resp.status_code == 200:
        secret = resp.json()["data"]["data"]
        if len(secret.values()) == 1:
            for k, v in secret.items():
                return k, v
        else:
            return secret

    else:
        print(f"http error {resp.status_code}")
        logging.error(f"Vault api error {resp}")
        return None, None
