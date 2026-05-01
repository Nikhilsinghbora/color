#!/usr/bin/env python3
"""
Detailed WebSocket connection test script.
Tests the WebSocket endpoint directly to verify backend connectivity.
"""

import asyncio
import json
import sys
from datetime import datetime

try:
    import websockets
except ImportError:
    print("❌ websockets library not installed")
    print("Install with: pip install websockets")
    sys.exit(1)

import requests


def log(message):
    """Print timestamped log message."""
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] {message}")


def test_backend_health():
    """Test if backend is responding."""
    log("Testing backend health...")
    try:
        response = requests.get("http://localhost:8000/api/v1/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            log(f"✅ Backend health: {data}")
            return True
        else:
            log(f"❌ Backend returned status {response.status_code}")
            return False
    except Exception as e:
        log(f"❌ Backend not reachable: {e}")
        return False


def get_test_token():
    """Get a test JWT token by logging in."""
    log("Getting authentication token...")
    try:
        response = requests.post(
            "http://localhost:8000/api/v1/auth/login",
            json={"email": "test@example.com", "password": "testpassword"},
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            token = data.get("access_token")
            log(f"✅ Got token: {token[:30]}...")
            return token
        else:
            log(f"❌ Login failed with status {response.status_code}")
            log(f"Response: {response.text}")
            return None
    except Exception as e:
        log(f"❌ Login request failed: {e}")
        return None


def get_active_round_id(token):
    """Get an active round ID from game modes."""
    log("Fetching active round ID...")
    try:
        response = requests.get(
            "http://localhost:8000/api/v1/game/modes",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5
        )
        if response.status_code == 200:
            modes = response.json()
            if modes and len(modes) > 0:
                round_id = modes[0].get("active_round_id")
                mode_name = modes[0].get("name")
                log(f"✅ Active round: {round_id} (mode: {mode_name})")
                return round_id
            else:
                log("❌ No game modes found")
                return None
        else:
            log(f"❌ Failed to get game modes: {response.status_code}")
            return None
    except Exception as e:
        log(f"❌ Request failed: {e}")
        return None


async def test_websocket_connection(round_id, token):
    """Test WebSocket connection."""
    ws_url = f"ws://localhost:8000/ws/game/{round_id}?token={token}"
    log(f"Connecting to WebSocket...")
    log(f"URL: {ws_url[:60]}...?token=***")

    try:
        async with websockets.connect(ws_url) as websocket:
            log("✅ WebSocket connection ESTABLISHED")

            # Wait for initial messages
            log("Waiting for messages (10 seconds)...")
            message_count = 0

            try:
                for _ in range(10):  # Wait up to 10 seconds
                    message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    message_count += 1

                    try:
                        data = json.loads(message)
                        msg_type = data.get("type", "unknown")
                        log(f"📩 Received message #{message_count}: type={msg_type}")

                        # Show some key fields
                        if msg_type == "round_state":
                            log(f"   Phase: {data.get('phase')}, Timer: {data.get('timer')}s, Players: {data.get('total_players')}")
                        elif msg_type == "timer_tick":
                            log(f"   Remaining: {data.get('remaining')}s")
                    except json.JSONDecodeError:
                        log(f"📩 Received non-JSON message: {message[:100]}")

            except asyncio.TimeoutError:
                pass  # Normal - no more messages

            log(f"✅ Received {message_count} messages total")

            if message_count == 0:
                log("⚠️  No messages received - check if Celery is running!")
                log("   Start Celery with: start_celery.bat")

    except websockets.exceptions.InvalidStatusCode as e:
        log(f"❌ WebSocket connection rejected: {e.status_code}")
        if e.status_code == 401:
            log("   This means: Authentication failed (invalid token)")
        elif e.status_code == 403:
            log("   This means: Forbidden (token valid but access denied)")
        elif e.status_code == 404:
            log("   This means: Round not found")
    except websockets.exceptions.WebSocketException as e:
        log(f"❌ WebSocket error: {e}")
    except Exception as e:
        log(f"❌ Unexpected error: {type(e).__name__}: {e}")


async def main():
    """Run all tests."""
    log("=" * 60)
    log("WebSocket Connection Test")
    log("=" * 60)

    # Step 1: Test backend health
    if not test_backend_health():
        log("\n❌ Backend is not running. Start with: uv run run_local.py")
        return

    log("")

    # Step 2: Get authentication token
    token = get_test_token()
    if not token:
        log("\n⚠️  Could not get auth token. Create test user with:")
        log("   python -m scripts.create_admin --email test@example.com --username test --password testpassword")
        return

    log("")

    # Step 3: Get active round ID
    round_id = get_active_round_id(token)
    if not round_id:
        log("\n❌ No active round found. Make sure game modes are seeded:")
        log("   python -m scripts.seed_data")
        return

    log("")

    # Step 4: Test WebSocket
    await test_websocket_connection(round_id, token)

    log("")
    log("=" * 60)
    log("Test complete!")
    log("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
