"""
shoonya_auth.py
---------------
Standalone script to automate Shoonya (Finvasia) OAuth 2.0 login.
Usage: python shoonya_auth.py [shoonya_huf | shoonya_regular]
"""

import asyncio
import logging
import re
import time
import sys
import pyotp
from playwright.async_api import async_playwright, Page

from firebase_credentials import get_shoonya_huf_creds

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Low-level Playwright helpers
# ---------------------------------------------------------------------------

async def _try_dom_login(page: Page, user_id: str, password: str, totp_secret: str) -> bool:
    """Attempt credential entry via DOM selectors."""
    try:
        await page.wait_for_selector("input", state="visible", timeout=8_000)
        
        user_field = await page.query_selector('input[placeholder*="User ID"], input[placeholder*="Client"], #uid, #userid')
        if not user_field:
            inputs = await page.query_selector_all("input")
            if inputs: user_field = inputs[0]
            
        if user_field:
            await user_field.fill(user_id)
            await asyncio.sleep(0.3)

        pass_field = await page.query_selector('input[type="password"], #pwd, #password')
        if not pass_field:
            inputs = await page.query_selector_all("input")
            if len(inputs) >= 2: pass_field = inputs[1]

        if pass_field:
            await pass_field.fill(password)
            await asyncio.sleep(0.3)

        # 3. Find and fill TOTP field
        totp_field = await page.query_selector('input[placeholder*="TOTP"], input[placeholder*="OTP"], #totp')
        if not totp_field:
            inputs = await page.query_selector_all("input")
            if len(inputs) >= 3: totp_field = inputs[2]
            
        if totp_field:
            otp = pyotp.TOTP(totp_secret).now()
            await totp_field.fill(otp)
            await asyncio.sleep(0.3)
            logger.info("Filled TOTP field")

        for selector in ['button[type="submit"]', 'button:has-text("LOGIN")', 'button:has-text("Login")']:
            btn = await page.query_selector(selector)
            if btn:
                await btn.click()
                return True

        if inputs and len(inputs) >= 3:
            await inputs[2].press("Enter")
            return True
        return False
    except Exception:
        return False


async def _try_coordinate_login(page: Page, user_id: str, password: str, totp_secret: str) -> None:
    """Coordinate-based login for the Flutter canvas UI."""
    logger.info("Starting coordinate login on Flutter canvas...")
    await page.wait_for_timeout(10_000)

    # User ID
    await page.mouse.click(960, 350)
    await page.keyboard.type(user_id, delay=100)
    await asyncio.sleep(1.0)

    # Password
    await page.keyboard.press("Tab")
    await page.keyboard.type(password, delay=100)
    await asyncio.sleep(1.0)

    # TOTP
    await page.keyboard.press("Tab")
    otp = pyotp.TOTP(totp_secret).now()
    logger.info(f"Typing TOTP: {otp}")
    await page.keyboard.type(otp, delay=100)
    await asyncio.sleep(1.0)

    # Login button
    await page.mouse.click(960, 580)


async def get_shoonya_auth_code(
    user_id: str,
    password: str,
    totp_secret: str,
    headless: bool = True,
    timeout: int = 90
) -> str | None:
    """Automate the Shoonya OAuth login and return the auth code."""
    url_api_key = f"{user_id}_U"
    oauth_url = f"https://trade.shoonya.com/OAuthlogin/investor-entry-level/login?api_key={url_api_key}&route_to={user_id}"
    
    auth_code: str | None = None

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=headless,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = await context.new_page()

        def _extract_auth_code(url: str) -> str | None:
            if not url: return None
            match = re.search(r'[?&#]code=([^&]+)', url)
            return match.group(1) if match else None

        def _on_request(request):
            nonlocal auth_code
            if not auth_code:
                code = _extract_auth_code(request.url)
                if code: auth_code = code

        def _on_response(response):
            nonlocal auth_code
            if not auth_code:
                location = response.headers.get("location", "")
                code = _extract_auth_code(location)
                if code: auth_code = code

        page.on("request", _on_request)
        page.on("response", _on_response)

        try:
            logger.info("Navigating to Shoonya OAuth URL...")
            await page.goto(oauth_url, wait_until="domcontentloaded", timeout=30_000)

            used_dom = await _try_dom_login(page, user_id, password, totp_secret)
            if not used_dom:
                logger.info("Using coordinate method...")
                await _try_coordinate_login(page, user_id, password, totp_secret)

            current_otp = pyotp.TOTP(totp_secret).now()
            deadline = time.monotonic() + timeout
            
            while auth_code is None and time.monotonic() < deadline:
                code = _extract_auth_code(page.url)
                if code:
                    auth_code = code
                    break
                await asyncio.sleep(0.5)
                
                # Check for TOTP rollover
                new_otp = pyotp.TOTP(totp_secret).now()
                if new_otp != current_otp and auth_code is None:
                    logger.info("TOTP rolled over, retrying login...")
                    current_otp = new_otp
                    await _try_dom_login(page, user_id, password, totp_secret)
                    deadline = time.monotonic() + 30 

            if auth_code:
                logger.info("SUCCESS! Auth code obtained.")
                print(f"AUTHENTICATION CODE: {auth_code}")
            else:
                logger.error("FAILED! Timed out waiting for auth code.")

        finally:
            await browser.close()

    return auth_code

async def main():
    account_type = "shoonya_huf"
    logger.info(f"--- Starting Shoonya {account_type.upper()} Auth Code Generation ---")
    
    # 2. Fetch Credentials from Firebase
    try:
        creds = await get_shoonya_huf_creds()
            
        if not creds:
            logger.error(f"Credentials not found for {account_type}")
            return
            
        userid = creds.get('userid')
        password = creds.get('password')
        totp_secret = creds.get('totp_secret')
        
        if not all([userid, password, totp_secret]):
            logger.error("Incomplete credentials in Firebase.")
            return
            
        logger.info(f"Fetched credentials for user: {userid}")
        
    except Exception as e:
        logger.error(f"Error fetching credentials: {e}")
        return

    # 3. Run Automation
    auth_code = await get_shoonya_auth_code(userid, password, totp_secret, headless=True)
    
    # 4. Send to Oracle VM
    if auth_code:
        vm_url = "http://140.245.249.191/oracle_trade/generate_token"
        logger.info(f"Sending auth code to Oracle VM at {vm_url}...")
        try:
            import requests
            r = requests.post(vm_url, json={
                "auth_code": auth_code
            })
            print("\n" + "="*50)
            print(f"VM RESPONSE: {r.text}")
            print("="*50 + "\n")
        except Exception as e:
            logger.error(f"Failed to send code to Oracle VM: {e}")

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    asyncio.run(main())
