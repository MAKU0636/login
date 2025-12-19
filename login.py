import os, time, requests
import selenium.webdriver as webdriver, datetime as DT
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import pyotp, json
from webdriver_manager.chrome import ChromeDriverManager
from firebase_credentials import FirestoreData
import json,pyotp
from urllib import parse
import sys,hashlib
import asyncio,pytz,logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

fire = FirestoreData()
utc_now = DT.datetime.now(pytz.utc)
ist = pytz.timezone('Asia/Kolkata')
ist_now = utc_now.astimezone(ist)
today = str(ist_now.date())

user_agent = 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36'
chrome_options = Options()
chrome_options.add_argument(f'user-agent={user_agent}')
chrome_options.add_argument("--user-data-dir=/tmp/chrome-user-data-" + str(time.time()))
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--disable-software-rasterizer")
chrome_options.binary_location = "/usr/bin/google-chrome"

async def login_upstox(apikey, secretkey, totpkey, mobile):
    redirect_uri = "https://127.0.0.1:5000/"
    browser = None
    try:
        url = f'https://api-v2.upstox.com/login/authorization/dialog?response_type=code&client_id={apikey}&redirect_uri={redirect_uri}'
        browser = webdriver.Chrome(options=chrome_options)
        browser.get(url)
        WebDriverWait(browser, 10).until(EC.presence_of_element_located((By.ID, "mobileNum"))).send_keys(mobile)
        WebDriverWait(browser, 10).until(EC.presence_of_element_located((By.ID, "getOtp"))).submit()
        otp = pyotp.TOTP(totpkey).now()
        WebDriverWait(browser, 10).until(EC.presence_of_element_located((By.ID, 'otpNum'))).send_keys(otp)
        WebDriverWait(browser, 10).until(EC.presence_of_element_located((By.ID, "continueBtn"))).submit()
        WebDriverWait(browser, 10).until(EC.presence_of_element_located((By.ID, 'pinCode'))).send_keys('280319')
        WebDriverWait(browser, 10).until(EC.presence_of_element_located((By.ID, "pinContinueBtn"))).submit()
        time.sleep(3)
        current_url = browser.current_url
        code = current_url.split('=')[1]
        token_url = 'https://api-v2.upstox.com/login/authorization/token'
        headers = {'accept': 'application/json','Api-Version': '2.0','Content-Type': 'application/x-www-form-urlencoded'}
        data = {'code': code,'client_id': apikey,'client_secret': secretkey,'redirect_uri': redirect_uri,'grant_type': 'authorization_code'}
        response = requests.post(token_url, headers=headers, data=data)
        response.raise_for_status()  # Raise exception for HTTP errors
        json_response = response.json()
        if 'access_token' not in json_response:
            raise Exception(f"Access token not found in response: {json_response}")
        return json_response['access_token']
    except Exception as e:
        logger.error(f"Error in get_code: {str(e)}")
        raise
    finally: 
        if browser: browser.quit()

##### fyre api credentials
APP_name = 'MAKU0636'
client_id ='Z7JMN5IH35-100'
secret_key='IFHGMFRCJX'
redirect_url = 'https://www.google.com'
TOTP_KEY ='JCMUFBW2ICNIAGXJQ3N723PSQFD32NGI'
FY_ID = "YM17039" # Your fyers ID
APP_ID_TYPE = "2"# Keep default as 2, It denotes web login
PIN = "2803"
APP_ID,APP_TYPE = client_id.split('-')#Example - EGNI8CE27Q-100, In this code EGNI8CE27Q will be APP_ID and 100 will be the APP_TYPE
REDIRECT_URI = "https://www.google.com"  # Redirect url from the app.
a_string = f'{client_id}:{secret_key}' # NEW
APP_ID_HASH = hashlib.sha256(a_string.encode('utf-8')).hexdigest()
BASE_URL = "https://api-t2.fyers.in/vagator/v2"
BASE_URL_2 = "https://api-t1.fyers.in/api/v3"
URL_SEND_LOGIN_OTP = BASE_URL + "/send_login_otp"
URL_VERIFY_TOTP = BASE_URL + "/verify_otp"
URL_VERIFY_PIN = BASE_URL + "/verify_pin"
URL_TOKEN = BASE_URL_2 + "/token"
URL_VALIDATE_AUTH_CODE = BASE_URL_2 + "/validate-authcode"

SUCCESS,ERROR = 1, -1
async def post_url(url, payload,key,header=None):
    try:
        resp = requests.post(url, json=payload, headers=header) if header else requests.post(url, json=payload)
        if (key == 'Url' and resp.status_code != 308) or (key != 'Url' and resp.status_code != 200):return [ERROR, response.text]
        return [SUCCESS, resp.json()[key]]
    except Exception as e: return [ERROR, e]
async def send_login_otp(fy_id, app_id):
    return await post_url(URL_SEND_LOGIN_OTP, {"fy_id": fy_id,"app_id": app_id}, "request_key")
async def verify_totp(request_key, totp):
    return await post_url(URL_VERIFY_TOTP, {"request_key": request_key,"otp": totp}, "request_key")
async def verify_PIN(request_key, pin):
    res = await post_url(URL_VERIFY_PIN, {"request_key": request_key,"identity_type": "pin","identifier": pin}, "data")
    return [SUCCESS, res[1]['access_token']] if res[0] == SUCCESS else res
async def token(access_token):
    payload = {"fyers_id": FY_ID,"app_id": APP_ID,"redirect_uri": REDIRECT_URI,"appType": APP_TYPE,"code_challenge": "",
            "state": "sample_state","scope": "","nonce": "","response_type": "code","create_cookie": True}
    headers={'Authorization': f'Bearer {access_token}'}
    response = await post_url(URL_TOKEN, payload, "Url", headers)
    if response[0] == SUCCESS: return [SUCCESS, parse.parse_qs(parse.urlparse(response[1]).query)['auth_code'][0]]
    return response      

async def validate_authcode(auth_code):
    payload = {"grant_type": "authorization_code","appIdHash": APP_ID_HASH,"code": auth_code,}
    return await post_url(URL_VALIDATE_AUTH_CODE, payload,"access_token")
    
async def process(fn,args,process_name):
    result, response = await fn(**args)
    if result != SUCCESS:
        logger.error(f"{process_name} failure - {response}")
        sys.exit()
    logger.info(f"{process_name} success")
    return response

async def login_fyers():
    request_key=  await process(send_login_otp, {"fy_id": FY_ID, "app_id": APP_ID_TYPE}, "send_login_otp")
    totp = pyotp.TOTP(TOTP_KEY).now()
    request_key_2 = await process(verify_totp, {"request_key":request_key, "totp":totp}, "verify_totp_result")
    verify_pin_result = await process(verify_PIN, {"request_key": request_key_2, "pin": PIN}, "verify_pin_result")
    auth_code = await process(token, {"access_token": verify_pin_result}, "get_auth_code")
    final_result = await process(validate_authcode, {"auth_code": auth_code}, "validate_authcode")
    return client_id + ":" + final_result
    logger.info(f"access_token - {access_token}")

##### ICICI credentials
ICICI_API_KEY = "227R333763KzD(717qQ7n3v828~485PA"
ICICI_USER_ID = '8004912720'
ICICI_PIN = '280319'
ICICI_TOTP_KEY = 'GNSWOZDWLBRDQ4BQKBBWMTJTN4'

async def login_icici():
    login_url = f"https://api.icicidirect.com/apiuser/login?api_key={ICICI_API_KEY}"
    browser = None
    try:
        browser = webdriver.Chrome(options=chrome_options)
        browser.get(login_url)
        WebDriverWait(browser, 10).until(EC.presence_of_element_located((By.ID, "txtuid"))).send_keys(ICICI_USER_ID)
        browser.find_element(By.ID, "txtPass").send_keys(ICICI_PIN)
        checkbox = browser.find_element(By.ID, "chkssTnc")
        if not checkbox.is_selected():
            checkbox.click()
        browser.find_element(By.ID, "btnSubmit").click()
        time.sleep(2)
        otp = pyotp.TOTP(ICICI_TOTP_KEY).now()
        otp_fields = browser.find_elements(By.CSS_SELECTOR, 'input[tg-nm="otp"]')
        for i, digit in enumerate(otp):
            if i < len(otp_fields):
                otp_fields[i].send_keys(digit)
        browser.find_element(By.ID, "Button1").click()
        time.sleep(3)
        current_url = browser.current_url
        if "apisession=" in current_url:
            return current_url.split("apisession=")[1]
        raise Exception("Session token not found in URL")
    except Exception as e:
        logger.error(f"Error in login_icici: {str(e)}")
        raise
    finally:
        if browser:browser.quit()

async def perform_login():
    try:
        token = await fire.read_collection('api_tokens')
        brokers_today = {item['broker'] for item in token if item['date'] == today}
        new_tokens = []
        success, failed, already_logged_in = [], [], []
        
        if 'upstox' not in brokers_today:
            try:
                upstox_token = await login_upstox('e85552ca-05b1-40bf-872f-d07670b76064', '04jibqarqv', 'TJZ5XEVN2EN3OEJMFBYT3U2DR6FT25PG', '9415912720')
                new_tokens.append({'date': today, 'broker': 'upstox', 'token': upstox_token})
                success.append('upstox')
            except Exception as e:
                logger.error(f'upstox login failed: {str(e)}')
                failed.append('upstox')
        else:
            already_logged_in.append('upstox')
        
        if 'fyres' not in brokers_today:
            try:
                fyres_token = await login_fyers()
                new_tokens.append({'date': today, 'broker': 'fyres', 'token': fyres_token})
                success.append('fyres')
            except Exception as e:
                logger.error(f'fyres login failed: {str(e)}')
                failed.append('fyres')
        else:
            already_logged_in.append('fyres')
        
        if 'upstox_PRO' not in brokers_today:
            try:
                upstox_pro_token = await login_upstox('273c283a-e220-4926-b455-d03d9a6dda81', 'vnbe3wkfjx', '26PABOPTGSVWESTEXCX5N7MC7LFGQLOG', '8004912720')
                new_tokens.append({'date': today, 'broker': 'upstox_PRO', 'token': upstox_pro_token})
                success.append('upstox_PRO')
            except Exception as e:
                logger.error(f'upstox_PRO login failed: {str(e)}')
                failed.append('upstox_PRO')
        else:
            already_logged_in.append('upstox_PRO')
        
        if 'icici' not in brokers_today:
            try:
                icici_token = await login_icici()
                new_tokens.append({'date': today, 'broker': 'icici', 'token': icici_token})
                success.append('icici')
            except Exception as e:
                logger.error(f'icici login failed: {str(e)}')
                failed.append('icici')
        else:
            already_logged_in.append('icici')
        
        if new_tokens:
            await fire.update_collection('api_tokens', new_tokens, 'broker')
        
        return {'status': 'success', 'login_successful': success, 'login_failed': failed, 'already_logged_in': already_logged_in}
    except Exception as e:
        logger.error(f"Error in perform_login: {str(e)}")
        return {'status': 'error', 'message': str(e)}

if __name__ == "__main__":
    result = asyncio.run(perform_login())
    print(json.dumps(result, indent=2))