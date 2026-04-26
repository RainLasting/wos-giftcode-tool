import json
import time
import random
import hashlib
import requests

BASE_URL = "https://wos-giftcode-api.centurygame.com"
LOGIN_URL = BASE_URL + "/api/player"
CAPTCHA_URL = BASE_URL + "/api/captcha"
REDEEM_URL = BASE_URL + "/api/gift_code"
WOS_ENCRYPT_KEY = "tB87#kPtkxqOS2"

DELAY = 1
RETRY_DELAY = 2
MAX_RETRIES = 3


def encode_data(data):
    sorted_keys = sorted(data.keys())
    encoded_data = "&".join([
        f"{key}={json.dumps(data[key]) if isinstance(data[key], dict) else data[key]}"
        for key in sorted_keys
    ])
    return {"sign": hashlib.md5(f"{encoded_data}{WOS_ENCRYPT_KEY}".encode()).hexdigest(), **data}


def make_request(url, payload, headers=None):
    session = requests.Session()
    version = random.randint(130, 135)
    base_headers = {
        'User-Agent': f'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{version}.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Encoding': 'gzip, deflate, br, zstd',
        'Accept-Language': 'en-US,en;q=0.9',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Origin': 'https://wos-giftcode.centurygame.com',
        'Referer': 'https://wos-giftcode.centurygame.com/',
        'sec-ch-ua': f'"Not:A-Brand";v="99", "Google Chrome";v="{version}", "Chromium";v="{version}"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
    }
    if headers:
        base_headers.update(headers)

    for attempt in range(MAX_RETRIES):
        try:
            response = session.post(url, data=payload, headers=base_headers, timeout=15)
            if response.status_code in [502, 503, 504]:
                time.sleep(RETRY_DELAY * (attempt + 1) * 1.5)
                continue
            elif response.status_code == 429:
                time.sleep(RETRY_DELAY * (attempt + 1) * 2)
                continue
            return response
        except requests.exceptions.Timeout:
            time.sleep(RETRY_DELAY * (attempt + 1))
        except requests.exceptions.ConnectionError:
            time.sleep(RETRY_DELAY * (attempt + 1))
        except requests.exceptions.RequestException:
            time.sleep(RETRY_DELAY * (attempt + 1))

    return None
