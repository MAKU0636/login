import os
import time
import requests
import datetime as DT
import pyotp
import json
from firebase_credentials import FirestoreData, get_icici_creds
from urllib import parse
import sys
import hashlib
import asyncio
import pytz
import logging
from playwright.async_api import async_playwright
from shoonya_auth import get_shoonya_auth_code

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

fire = FirestoreData()
utc_now = DT.datetime.now(pytz.utc)
ist = pytz.timezone('Asia/Kolkata')
ist_now = utc_now.astimezone(ist)
today = str(ist_now.date())

user_agent = 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36'

async def login_upstox(apikey, secretkey, totpkey, mobile):
    redirect_uri = "https://127.0.0.1:5000/"
    try:
        url = f'https://api-v2.upstox.com/login/authorization/dialog?response_type=code&client_id={apikey}&redirect_uri={redirect_uri}'
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True, 
                args=["--disable-dev-shm-usage", "--no-sandbox", "--disable-gpu", "--disable-software-rasterizer"]
            )
            context = await browser.new_context(user_agent=user_agent)
            page = await context.new_page()
            
            await page.goto(url)
            await page.wait_for_selector("#mobileNum")
            await page.fill("#mobileNum", mobile)
            await page.click("#getOtp")
            
            otp = pyotp.TOTP(totpkey).now()
            await page.wait_for_selector("#otpNum")
            await page.fill("#otpNum", otp)
            await page.click("#continueBtn")
            
            await page.wait_for_selector("#pinCode")
            await page.fill("#pinCode", '280319')
            
            try:
                async with page.expect_request(lambda request: "127.0.0.1:5000" in request.url and "code=" in request.url, timeout=10000) as first:
                    await page.click("#pinContinueBtn")
                request = await first.value
                current_url = request.url
            except Exception as e:
                current_url = page.url
                logger.error(f"Timeout waiting for redirect request. Last URL: {current_url}")
                raise e
            
            await browser.close()
            
        code = ''
        if 'code=' in current_url:
            code = current_url.split('code=')[1].split('&')[0]
        else:
            logger.error(f"URL did not contain 'code='. Current URL is: {current_url}")
            raise Exception("Cannot extract code from URL")
        
        token_url = 'https://api-v2.upstox.com/login/authorization/token'
        headers = {'accept': 'application/json','Api-Version': '2.0','Content-Type': 'application/x-www-form-urlencoded'}
        data = {'code': code,'client_id': apikey,'client_secret': secretkey,'redirect_uri': redirect_uri,'grant_type': 'authorization_code'}
        response = await asyncio.to_thread(requests.post, token_url, headers=headers, data=data)
        response.raise_for_status()  # Raise exception for HTTP errors
        json_response = response.json()
        if 'access_token' not in json_response:
            raise Exception(f"Access token not found in response: {json_response}")
        return json_response['access_token']
    except Exception as e:
        logger.error(f"Error in get_code: {str(e)}")
        raise

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
        resp = await asyncio.to_thread(requests.post, url, json=payload, headers=header) if header else await asyncio.to_thread(requests.post, url, json=payload)
        if (key == 'Url' and resp.status_code != 308) or (key != 'Url' and resp.status_code != 200):
            return [ERROR, resp.text]
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
        raise Exception(f"{process_name} failure - {response}")
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

##### ICICI credentials
ICICI_API_KEY = "227R333763KzD(717qQ7n3v828~485PA"
ICICI_USER_ID = '8004912720'
ICICI_TOTP_KEY = 'GNSWOZDWLBRDQ4BQKBBWMTJTN4'

async def login_icici():
    icici_pin = await get_icici_creds()
    if not icici_pin:
        logger.error("ICICI PIN not found in Firestore")
        raise Exception("ICICI PIN not found")
    
    login_url = f"https://api.icicidirect.com/apiuser/login?api_key={ICICI_API_KEY}"
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--disable-dev-shm-usage", "--no-sandbox", "--disable-gpu", "--disable-software-rasterizer"]
            )
            context = await browser.new_context(user_agent=user_agent)
            page = await context.new_page()
            
            await page.goto(login_url)
            await page.wait_for_selector("#txtuid")
            await page.fill("#txtuid", ICICI_USER_ID)
            await page.fill("#txtPass", icici_pin)
            
            # Use query selector to make sure it only clicks if not checked
            is_checked = await page.is_checked("#chkssTnc")
            if not is_checked:
                await page.check("#chkssTnc")
                
            await page.click("#btnSubmit")
            await asyncio.sleep(2)
            
            otp = pyotp.TOTP(ICICI_TOTP_KEY).now()
            
            # There might be multiple OTP inputs
            otp_fields = await page.locator('input[tg-nm="otp"]').all()
            for i, digit in enumerate(otp):
                if i < len(otp_fields):
                    await otp_fields[i].fill(digit)
                    
            # Start monitoring network requests BEFORE the click
            logger.info("Monitoring network requests for token...")
            captured_url = [None]
            def handle_request(request):
                if "apisession=" in request.url:
                    captured_url[0] = request.url
            page.on("request", handle_request)

            await page.click("#Button1")
            
            # Wait for redirect to process
            await asyncio.sleep(7)
            
            # Check both captured requests and final page URL
            current_url = captured_url[0] if captured_url[0] else page.url
            await browser.close()
            
        if "apisession=" in current_url:
            return current_url.split("apisession=")[1]
        raise Exception("Session token not found in URL")
    except Exception as e:
        logger.error(f"Error in login_icici: {str(e)}")
        raise

async def login_shoonya_huf():
    """Fetch Shoonya HUF access token via shoonya_auth automation and Oracle VM."""
    try:
        from firebase_credentials import get_shoonya_huf_creds
        creds = await get_shoonya_huf_creds()
        if not creds:
            raise Exception("Shoonya HUF credentials not found")
            
        auth_code = await get_shoonya_auth_code(
            creds['userid'], 
            creds['password'], 
            creds['totp_secret'], 
            headless=True
        )
        if not auth_code:
            raise Exception("Failed to obtain Shoonya auth code")
            
        vm_url = "http://140.245.249.191/oracle_trade/generate_token"
        response = await asyncio.to_thread(requests.post, vm_url, json={
            "auth_code": auth_code
        })
        response.raise_for_status()
        result = response.json()
        
        if result.get('status') == 'success' and 'access_token' in result:
            return result['access_token']
        else:
            raise Exception(f"VM failed to generate token: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        logger.error(f"Error in login_shoonya_huf: {str(e)}")
        raise

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
            
        if 'shoonya_huf' not in brokers_today:
            try:
                shoonya_token = await login_shoonya_huf()
                new_tokens.append({'date': today, 'broker': 'shoonya_huf', 'token': shoonya_token})
                
                success.append('shoonya_huf')
            except Exception as e:
                logger.error(f'shoonya_huf login failed: {str(e)}')
                failed.append('shoonya_huf')
        else:
            already_logged_in.append('shoonya_huf')
        
        if new_tokens:
            await fire.update_collection('api_tokens', new_tokens, 'broker')
        
        return {'status': 'success', 'login_successful': success, 'login_failed': failed, 'already_logged_in': already_logged_in}
    except Exception as e:
        logger.error(f"Error in perform_login: {str(e)}")
        return {'status': 'error', 'message': str(e)}

if __name__ == "__main__":
    result = asyncio.run(perform_login())
    print(json.dumps(result, indent=2))
