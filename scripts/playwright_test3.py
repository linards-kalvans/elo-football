"""Final verification test - read Alpine state from correct element."""

import json
from playwright.sync_api import sync_playwright, Page


def get_alpine_state_correct(page: Page) -> dict:
    """Get Alpine state from the actual x-data div (not body)."""
    return page.evaluate("""
        () => {
            // The main component is on the div with x-data="eloPage()"
            const el = document.querySelector('[x-data]');
            if (!el) return {error: 'no x-data element'};
            try {
                const comp = window.Alpine.$data(el);
                if (!comp) return {error: 'Alpine.$data returned null'};
                return {
                    element_tag: el.tagName,
                    element_id: el.id,
                    accuracyView: comp.accuracyView,
                    historyPage: comp.historyPage,
                    historyPerPage: comp.historyPerPage,
                    loadingHistory: comp.loadingHistory,
                    loadingGrid: comp.loadingGrid,
                    historyData_type: typeof comp.historyData,
                    historyData_is_null: comp.historyData === null,
                    historyData_items_count: comp.historyData && comp.historyData.items ? comp.historyData.items.length : 'N/A',
                    historyData_total: comp.historyData ? comp.historyData.total : 'N/A',
                    historyData_pages: comp.historyData ? comp.historyData.pages : 'N/A',
                    gridData_null: comp.gridData === null,
                    accuracyDetail_null: comp.accuracyDetail === null,
                    accuracy_pct: comp.accuracy ? comp.accuracy.accuracy_pct : null,
                    level: comp.level,
                    country: comp.country,
                    competition: comp.competition,
                    teamId: comp.teamId,
                };
            } catch (e) {
                return {error: String(e)};
            }
        }
    """)


def test_page(p, url: str, label: str):
    print(f"\n{'='*60}")
    print(f"TEST: {label} ({url})")
    print("="*60)

    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    console_errors = []
    page.on("console", lambda msg: console_errors.append(msg) if msg.type == "error" else None)

    api_responses = []
    def on_response(r):
        if "/api/" in r.url:
            try:
                body = r.json()
            except Exception:
                body = r.text()[:200]
            api_responses.append({"url": r.url, "status": r.status, "body": body})
    page.on("response", on_response)

    page.goto(url, wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(2000)

    print("\n[INITIAL]")
    state = get_alpine_state_correct(page)
    print(json.dumps(state, indent=2))

    print("\n[CLICK View details]")
    vd = page.locator("text=View details").first
    if vd.count() > 0:
        vd.click()
        page.wait_for_timeout(4000)

        print("\n[AFTER CLICK]")
        state = get_alpine_state_correct(page)
        print(json.dumps(state, indent=2))

        # Check table rows
        row_count = page.locator("table tbody tr").count()
        print(f"\n  All tbody rows visible: {row_count}")

        # Specifically check 3rd table (prediction history)
        tables = page.locator("table").all()
        for i, t in enumerate(tables):
            rows = t.locator("tbody tr").count()
            inner_len = len(t.inner_html())
            print(f"  Table {i+1}: {rows} rows, innerHTML length {inner_len}")

        # Test pagination
        print("\n[PAGINATION - NEXT]")
        next_btn = page.locator("button:has-text('Next')").first
        if next_btn.count() > 0 and next_btn.is_visible():
            next_btn.click()
            page.wait_for_timeout(2000)
            state = get_alpine_state_correct(page)
            print(f"  historyPage: {state.get('historyPage')}")
            print(f"  historyData_items_count: {state.get('historyData_items_count')}")

            print("\n[PAGINATION - PREV]")
            prev_btn = page.locator("button:has-text('Prev')").first
            if prev_btn.count() > 0 and prev_btn.is_visible():
                prev_btn.click()
                page.wait_for_timeout(2000)
                state = get_alpine_state_correct(page)
                print(f"  historyPage: {state.get('historyPage')}")
                print(f"  historyData_items_count: {state.get('historyData_items_count')}")
            else:
                print("  Prev button not visible")
        else:
            print("  Next button not found or not visible")

        # Check history API calls
        print("\n[HISTORY API CALLS]")
        for r in api_responses:
            if "prediction-history" in r["url"]:
                body = r["body"]
                print(f"  {r['status']} {r['url']}")
                if isinstance(body, dict):
                    print(f"    -> {len(body.get('items', []))} items, total={body.get('total')}, pages={body.get('pages')}")

    else:
        print("  'View details' NOT FOUND")
        accuracy_el = page.locator("text=Accuracy").count()
        print(f"  'Accuracy' text found: {accuracy_el}")

    print("\n[CONSOLE ERRORS]")
    for e in console_errors:
        print(f"  {e.text[:200]}")

    browser.close()


def main():
    with sync_playwright() as p:
        test_page(p, "http://localhost:8003/england/premier-league",
                  "Premier League (league scope)")
        test_page(p, "http://localhost:8003/england/premier-league/man-city",
                  "Man City (team scope)")


if __name__ == "__main__":
    main()
