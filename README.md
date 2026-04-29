# Broker Login Service (Playwright)

Automated login pipeline for multiple brokers using **Playwright** for high-reliability browser automation.

## Supported Brokers
- **Upstox** & **Upstox PRO**
- **Fyers**
- **ICICI Breeze**
- **Shoonya (Finvasia) HUF** - Includes auth code capture and automatic token generation via Oracle VM integration.

## How it Works
1.  **Firebase Sync**: Fetches credentials (API keys, secrets, TOTP keys) from Firestore.
2.  **Automation**: Uses Playwright (Headless) to perform logins, solve TOTPs, and capture session tokens.
3.  **Storage**: 
    - Saves all broker tokens to the `api_tokens` collection.
    - Specifically saves the Shoonya HUF token to `access_token/api_token_005` for the trading dispatcher.

## Deployment
- **Local**: Run `python login.py`.
- **Server**: Deploy the Flask `main.py` (Port 8080) for remote triggering.

## Endpoints
- `POST /login` - Triggers the full multi-broker login pipeline.
- `GET /health` - Health check.
