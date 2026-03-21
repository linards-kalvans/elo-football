"""Playwright test for accuracy detail panel on Premier League vs team pages."""

import json
import time
from playwright.sync_api import sync_playwright, Page


def setup_console_listener(page: Page) -> list:
    """Attach console listener and return list that collects messages."""
    messages = []

    def on_console(msg):
        messages.append({
            "type": msg.type,
            "text": msg.text,
            "location": str(msg.location),
        })

    page.on("console", on_console)
    return messages


def setup_request_listener(page: Page) -> list:
    """Capture all network requests/responses."""
    requests = []

    def on_response(response):
        if "/api/" in response.url:
            try:
                body = response.json()
            except Exception:
                body = response.text()[:500]
            requests.append({
                "url": response.url,
                "status": response.status,
                "body": body,
            })

    page.on("response", on_response)
    return requests


def dump_table_state(page: Page, label: str):
    """Print detailed info about the prediction history table."""
    print(f"\n--- TABLE STATE: {label} ---")

    # Check if accuracy detail panel is visible
    panel_visible = page.locator("#accuracy-detail-panel").is_visible()
    print(f"  Accuracy detail panel visible: {panel_visible}")

    # Check x-if template presence (x-if renders as a comment when false)
    table_html = page.locator("#prediction-history-table").inner_html() if page.locator("#prediction-history-table").count() > 0 else "NOT FOUND"
    print(f"  #prediction-history-table inner HTML (truncated): {str(table_html)[:300]}")

    # Count rows in tbody
    tbody_rows = page.locator("#prediction-history-table tbody tr").count()
    print(f"  tbody row count: {tbody_rows}")

    # Try to get Alpine.js state via JS evaluation
    try:
        history_data = page.evaluate("""
            () => {
                // Find the Alpine component containing historyData
                const el = document.querySelector('[x-data]');
                if (!el) return 'no x-data element found';
                const alpine = el._x_dataStack;
                if (!alpine) return 'no _x_dataStack';
                // Try to access historyData from any scope
                return 'dataStack length: ' + alpine.length;
            }
        """)
        print(f"  Alpine dataStack: {history_data}")
    except Exception as e:
        print(f"  Alpine eval error: {e}")

    # Try getting historyData directly
    try:
        history_info = page.evaluate("""
            () => {
                // Look for all x-data elements
                const elements = document.querySelectorAll('[x-data]');
                const results = [];
                elements.forEach((el, i) => {
                    const comp = window.Alpine && window.Alpine.$data ? window.Alpine.$data(el) : null;
                    results.push({
                        index: i,
                        tag: el.tagName,
                        id: el.id,
                        classes: el.className.substring(0, 50),
                        hasHistoryData: comp ? 'historyData' in comp : 'no Alpine.$data',
                    });
                });
                return results;
            }
        """)
        print(f"  x-data elements: {json.dumps(history_info, indent=2)}")
    except Exception as e:
        print(f"  x-data elements eval error: {e}")

    # Try to get historyData from the main component
    try:
        history_items = page.evaluate("""
            () => {
                const el = document.querySelector('[x-data]');
                if (!el) return 'no element';
                const comp = window.Alpine.$data(el);
                if (!comp) return 'no comp';
                if (!comp.historyData) return 'no historyData in comp, keys: ' + Object.keys(comp).join(', ');
                return {
                    items_count: comp.historyData.items ? comp.historyData.items.length : 'items undefined',
                    total: comp.historyData.total,
                    page: comp.historyData.page,
                    historyPage: comp.historyPage,
                    historyLoading: comp.historyLoading,
                    showAccuracyDetail: comp.showAccuracyDetail,
                };
            }
        """)
        print(f"  historyData state: {json.dumps(history_items, indent=2)}")
    except Exception as e:
        print(f"  historyData eval error: {e}")


def test_premier_league(p):
    """Test accuracy detail on Premier League page."""
    print("\n" + "="*60)
    print("TEST: Premier League page")
    print("="*60)

    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    console_msgs = setup_console_listener(page)
    api_requests = setup_request_listener(page)

    page.goto("http://localhost:8003/england/premier-league", wait_until="networkidle", timeout=30000)
    print(f"Page title: {page.title()}")
    print(f"URL: {page.url}")

    # Wait a bit for Alpine to initialize
    page.wait_for_timeout(2000)

    # Find and click "View details" link
    print("\nLooking for 'View details' link...")
    view_details = page.locator("text=View details").first
    if view_details.count() > 0:
        print("  Found 'View details' link, clicking...")
        view_details.click()
        page.wait_for_timeout(3000)  # wait for panel + data fetch
    else:
        print("  'View details' link NOT FOUND")
        # Try to find accuracy section
        accuracy_section = page.locator("text=Prediction Accuracy").count()
        print(f"  'Prediction Accuracy' text found: {accuracy_section > 0}")

    dump_table_state(page, "After clicking View details - Premier League")

    # Check console errors
    print("\n--- CONSOLE MESSAGES ---")
    errors = [m for m in console_msgs if m["type"] in ("error", "warning")]
    all_msgs = console_msgs[-20:]  # last 20 messages
    for msg in all_msgs:
        prefix = "ERROR" if msg["type"] == "error" else "WARN" if msg["type"] == "warning" else "LOG"
        print(f"  [{prefix}] {msg['text'][:200]}")

    # Check API requests
    print("\n--- API REQUESTS (after clicking View details) ---")
    for req in api_requests:
        print(f"  {req['status']} {req['url']}")
        if req["status"] != 200:
            print(f"    Body: {str(req['body'])[:200]}")
        elif "history" in req["url"] or "accuracy" in req["url"]:
            print(f"    Body preview: {str(req['body'])[:300]}")

    # Test pagination - click Next
    print("\n--- PAGINATION TEST ---")
    next_btn = page.locator("button:has-text('Next')").first
    if next_btn.count() > 0 and next_btn.is_visible():
        print("Clicking Next...")
        next_btn.click()
        page.wait_for_timeout(2000)
        dump_table_state(page, "After clicking Next")

        prev_btn = page.locator("button:has-text('Prev')").first
        if prev_btn.count() > 0 and prev_btn.is_visible():
            print("Clicking Prev...")
            prev_btn.click()
            page.wait_for_timeout(2000)
            dump_table_state(page, "After clicking Prev")
        else:
            print("Prev button not found or not visible")
    else:
        print("Next button not found or not visible")
        # Try to find what pagination buttons exist
        all_btns = page.locator("button").all_text_contents()
        print(f"All button texts: {all_btns[:20]}")

    # Take screenshot
    page.screenshot(path="/tmp/pl_accuracy_detail.png", full_page=False)
    print("\nScreenshot saved: /tmp/pl_accuracy_detail.png")

    browser.close()
    return console_msgs, api_requests


def test_team_page(p):
    """Test accuracy detail on Man City team page."""
    print("\n" + "="*60)
    print("TEST: Manchester City team page")
    print("="*60)

    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    console_msgs = setup_console_listener(page)
    api_requests = setup_request_listener(page)

    page.goto("http://localhost:8003/england/premier-league/manchester-city",
              wait_until="networkidle", timeout=30000)
    print(f"Page title: {page.title()}")
    print(f"URL: {page.url}")

    page.wait_for_timeout(2000)

    # Find and click "View details" link
    print("\nLooking for 'View details' link...")
    view_details = page.locator("text=View details").first
    if view_details.count() > 0:
        print("  Found 'View details' link, clicking...")
        view_details.click()
        page.wait_for_timeout(3000)
    else:
        print("  'View details' link NOT FOUND")

    dump_table_state(page, "After clicking View details - Man City")

    print("\n--- CONSOLE MESSAGES ---")
    all_msgs = console_msgs[-20:]
    for msg in all_msgs:
        prefix = "ERROR" if msg["type"] == "error" else "WARN" if msg["type"] == "warning" else "LOG"
        print(f"  [{prefix}] {msg['text'][:200]}")

    print("\n--- API REQUESTS ---")
    for req in api_requests:
        print(f"  {req['status']} {req['url']}")
        if "history" in req["url"] or "accuracy" in req["url"]:
            print(f"    Body preview: {str(req['body'])[:400]}")

    page.screenshot(path="/tmp/team_accuracy_detail.png", full_page=False)
    print("\nScreenshot saved: /tmp/team_accuracy_detail.png")

    browser.close()
    return console_msgs, api_requests


def main():
    with sync_playwright() as p:
        pl_console, pl_requests = test_premier_league(p)
        team_console, team_requests = test_team_page(p)

        print("\n" + "="*60)
        print("SUMMARY COMPARISON")
        print("="*60)

        pl_errors = [m for m in pl_console if m["type"] == "error"]
        team_errors = [m for m in team_console if m["type"] == "error"]

        print(f"PL page console errors: {len(pl_errors)}")
        for e in pl_errors:
            print(f"  {e['text'][:200]}")

        print(f"Team page console errors: {len(team_errors)}")
        for e in team_errors:
            print(f"  {e['text'][:200]}")

        print(f"\nPL page API calls: {len(pl_requests)}")
        pl_history = [r for r in pl_requests if "history" in r["url"]]
        print(f"PL page history calls: {len(pl_history)}")
        for r in pl_history:
            print(f"  {r['status']} {r['url']}")

        print(f"\nTeam page API calls: {len(team_requests)}")
        team_history = [r for r in team_requests if "history" in r["url"]]
        print(f"Team page history calls: {len(team_history)}")
        for r in team_history:
            print(f"  {r['status']} {r['url']}")


if __name__ == "__main__":
    main()
