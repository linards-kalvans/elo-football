"""Deep-dive Playwright test — focus on Alpine state and table visibility."""

import json
from playwright.sync_api import sync_playwright, Page


def get_alpine_state(page: Page) -> dict:
    """Get full Alpine state from the main elokit() component."""
    return page.evaluate("""
        () => {
            // The main component is on body
            const el = document.querySelector('body');
            if (!el) return {error: 'no body'};
            try {
                const comp = window.Alpine.$data(el);
                if (!comp) return {error: 'no comp'};
                return {
                    accuracyView: comp.accuracyView,
                    historyPage: comp.historyPage,
                    historyPerPage: comp.historyPerPage,
                    historySearch: comp.historySearch,
                    loadingHistory: comp.loadingHistory,
                    loadingGrid: comp.loadingGrid,
                    historyData_items_count: comp.historyData && comp.historyData.items ? comp.historyData.items.length : 'undefined',
                    historyData_total: comp.historyData ? comp.historyData.total : 'undefined',
                    historyData_pages: comp.historyData ? comp.historyData.pages : 'undefined',
                    historyData_first_item: comp.historyData && comp.historyData.items && comp.historyData.items.length > 0
                        ? JSON.stringify(comp.historyData.items[0]).substring(0, 200)
                        : 'no items',
                    accuracy: comp.accuracy ? {
                        total: comp.accuracy.total_predictions,
                        pct: comp.accuracy.accuracy_pct,
                    } : null,
                    gridData_null: comp.gridData === null,
                    showingDetailDiv: document.querySelector('[x-show]') ? 'found x-show elements' : 'none',
                };
            } catch (e) {
                return {error: String(e)};
            }
        }
    """)


def check_detail_panel_dom(page: Page, label: str):
    """Check DOM elements related to detail panel."""
    print(f"\n--- DOM CHECK: {label} ---")

    # Try checking detail div visibility via display style
    detail_div_info = page.evaluate("""
        () => {
            // Find the div with x-show="accuracyView === 'detail'"
            const allDivs = document.querySelectorAll('div');
            let detailDiv = null;
            for (const div of allDivs) {
                const xshow = div.getAttribute('x-show');
                if (xshow && xshow.includes("accuracyView === 'detail'")) {
                    detailDiv = div;
                    break;
                }
            }
            if (!detailDiv) return {found: false};
            const style = window.getComputedStyle(detailDiv);
            return {
                found: true,
                display: style.display,
                visibility: style.visibility,
                offsetHeight: detailDiv.offsetHeight,
                hasContent: detailDiv.innerHTML.length,
            };
        }
    """)
    print(f"  Detail div: {detail_div_info}")

    # Check table
    table_info = page.evaluate("""
        () => {
            // Find prediction history table
            const tables = document.querySelectorAll('table');
            const results = [];
            for (const t of tables) {
                const tbodies = t.querySelectorAll('tbody');
                let rowCount = 0;
                for (const tb of tbodies) {
                    rowCount += tb.querySelectorAll('tr').length;
                }
                results.push({
                    id: t.id,
                    display: window.getComputedStyle(t).display,
                    rowCount: rowCount,
                    innerHTML_len: t.innerHTML.length,
                });
            }
            return results;
        }
    """)
    print(f"  Tables: {json.dumps(table_info, indent=2)}")

    # Check template x-if and x-for presence
    template_info = page.evaluate("""
        () => {
            const templates = document.querySelectorAll('template');
            const results = [];
            for (const t of templates) {
                results.push({
                    xif: t.getAttribute('x-if'),
                    xfor: t.getAttribute('x-for'),
                    nextSiblingType: t.nextSibling ? t.nextSibling.nodeType : null,
                });
            }
            return results;
        }
    """)
    print(f"  Templates (x-if/x-for): {json.dumps(template_info, indent=2)}")

    # Get Alpine state
    alpine = get_alpine_state(page)
    print(f"  Alpine state: {json.dumps(alpine, indent=2)}")

    # Check x-cloak elements
    xcloak_count = page.locator('[x-cloak]').count()
    print(f"  x-cloak elements remaining: {xcloak_count}")

    # Count visible rows in any table
    all_rows = page.locator('table tbody tr').count()
    print(f"  All table tbody tr count (any): {all_rows}")


def test_premier_league_deep(p):
    """Deep test on Premier League page."""
    print("\n" + "="*60)
    print("DEEP TEST: Premier League page")
    print("="*60)

    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    console_msgs = []
    page.on("console", lambda msg: console_msgs.append({
        "type": msg.type, "text": msg.text
    }))

    api_responses = []
    def on_response(response):
        if "/api/" in response.url:
            try:
                body = response.json()
            except Exception:
                body = response.text()[:300]
            api_responses.append({"url": response.url, "status": response.status, "body": body})
    page.on("response", on_response)

    page.goto("http://localhost:8003/england/premier-league", wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(2000)

    print("\n[INITIAL STATE]")
    alpine = get_alpine_state(page)
    print(f"  accuracyView: {alpine.get('accuracyView')}")
    print(f"  accuracy: {alpine.get('accuracy')}")

    # Find View details button
    view_details = page.locator("text=View details")
    count = view_details.count()
    print(f"\n  'View details' link count: {count}")

    if count > 0:
        # First show what's visible before clicking
        print("\n  Before click - is detail div hidden?")
        before = page.evaluate("""
            () => {
                const allDivs = document.querySelectorAll('div');
                for (const div of allDivs) {
                    const xshow = div.getAttribute('x-show');
                    if (xshow && xshow.includes("accuracyView === 'detail'")) {
                        return {
                            display: window.getComputedStyle(div).display,
                            xshow: xshow
                        };
                    }
                }
                return {error: 'not found'};
            }
        """)
        print(f"    {before}")

        print("\n  Clicking 'View details'...")
        view_details.first.click()
        page.wait_for_timeout(4000)  # extra time for all fetches

        check_detail_panel_dom(page, "After View details click")

        # Check if there's an error causing historyData to be empty
        print("\n--- ALL CONSOLE MESSAGES (after click) ---")
        for msg in console_msgs:
            t = msg["type"]
            if t in ("error", "warning") or "history" in msg["text"].lower():
                print(f"  [{t.upper()}] {msg['text'][:300]}")

        # Check what prediction-history API returned
        print("\n--- PREDICTION HISTORY API RESPONSE ---")
        hist_calls = [r for r in api_responses if "prediction-history" in r["url"]]
        for r in hist_calls:
            print(f"  {r['status']} {r['url']}")
            body = r['body']
            if isinstance(body, dict):
                print(f"    items_count: {len(body.get('items', []))}")
                print(f"    total: {body.get('total')}")
                print(f"    pages: {body.get('pages')}")
                if body.get('items'):
                    print(f"    first item keys: {list(body['items'][0].keys())}")

        # Now deeply inspect why table rows might not render
        print("\n--- DETAILED HISTORY TABLE INSPECTION ---")
        table_detail = page.evaluate("""
            () => {
                const comp = window.Alpine.$data(document.querySelector('body'));
                if (!comp) return 'no comp';

                const histData = comp.historyData;
                if (!histData) return 'historyData is null/undefined';

                return {
                    type: typeof histData,
                    keys: Object.keys(histData),
                    items_type: typeof histData.items,
                    items_is_array: Array.isArray(histData.items),
                    items_length: histData.items ? histData.items.length : 'N/A',
                    total: histData.total,
                    pages: histData.pages,
                    page: histData.page,
                    accuracyView: comp.accuracyView,
                    loadingHistory: comp.loadingHistory,
                };
            }
        """)
        print(f"  historyData detail: {json.dumps(table_detail, indent=2)}")

        # Check the x-if condition evaluation
        xif_eval = page.evaluate("""
            () => {
                const comp = window.Alpine.$data(document.querySelector('body'));
                if (!comp) return 'no comp';
                const items = comp.historyData && comp.historyData.items;
                return {
                    condition_result: items ? items.length > 0 : 'no items',
                    items_length: items ? items.length : 0,
                    accuracyView_eq_detail: comp.accuracyView === 'detail',
                };
            }
        """)
        print(f"  x-if condition eval: {json.dumps(xif_eval, indent=2)}")

        # Scroll to table and take screenshot
        page.evaluate("""
            () => {
                const allDivs = document.querySelectorAll('div');
                for (const div of allDivs) {
                    const xshow = div.getAttribute('x-show');
                    if (xshow && xshow.includes("accuracyView === 'detail'")) {
                        div.scrollIntoView();
                        break;
                    }
                }
            }
        """)
        page.screenshot(path="/tmp/pl_detail_view.png")
        print("\n  Screenshot saved: /tmp/pl_detail_view.png")

    browser.close()


def test_man_city_deep(p):
    """Deep test on Man City page."""
    print("\n" + "="*60)
    print("DEEP TEST: Man City team page")
    print("="*60)

    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    console_msgs = []
    page.on("console", lambda msg: console_msgs.append({
        "type": msg.type, "text": msg.text
    }))

    api_responses = []
    def on_response(response):
        if "/api/" in response.url:
            try:
                body = response.json()
            except Exception:
                body = response.text()[:300]
            api_responses.append({"url": response.url, "status": response.status, "body": body})
    page.on("response", on_response)

    # Use correct slug (man-city not manchester-city)
    page.goto("http://localhost:8003/england/premier-league/man-city",
              wait_until="networkidle", timeout=30000)
    print(f"Page title: {page.title()}")
    page.wait_for_timeout(2000)

    alpine = get_alpine_state(page)
    print(f"  accuracyView: {alpine.get('accuracyView')}")
    print(f"  accuracy: {alpine.get('accuracy')}")

    view_details = page.locator("text=View details")
    count = view_details.count()
    print(f"  'View details' link count: {count}")

    if count > 0:
        print("  Clicking 'View details'...")
        view_details.first.click()
        page.wait_for_timeout(4000)

        check_detail_panel_dom(page, "Man City after View details")

        print("\n--- CONSOLE MESSAGES ---")
        for msg in console_msgs:
            if msg["type"] in ("error", "warning"):
                print(f"  [{msg['type'].upper()}] {msg['text'][:300]}")

        print("\n--- PREDICTION HISTORY API RESPONSE ---")
        hist_calls = [r for r in api_responses if "prediction-history" in r["url"]]
        for r in hist_calls:
            print(f"  {r['status']} {r['url']}")
            body = r['body']
            if isinstance(body, dict):
                print(f"    items_count: {len(body.get('items', []))}")
                print(f"    total: {body.get('total')}")

        # Inspect historyData
        table_detail = page.evaluate("""
            () => {
                const comp = window.Alpine.$data(document.querySelector('body'));
                if (!comp) return 'no comp';
                const histData = comp.historyData;
                if (!histData) return 'historyData is null/undefined';
                return {
                    keys: Object.keys(histData),
                    items_length: histData.items ? histData.items.length : 'N/A',
                    total: histData.total,
                    accuracyView: comp.accuracyView,
                };
            }
        """)
        print(f"\n  historyData detail: {json.dumps(table_detail, indent=2)}")

        page.screenshot(path="/tmp/city_detail_view.png")
        print("  Screenshot saved: /tmp/city_detail_view.png")
    else:
        print("  No 'View details' found - checking accuracy widget...")
        alpine2 = get_alpine_state(page)
        print(f"  Alpine state: {json.dumps(alpine2, indent=2)}")

        print("\n  Console messages:")
        for msg in console_msgs:
            print(f"  [{msg['type'].upper()}] {msg['text'][:200]}")

        print("\n  API calls:")
        for r in api_responses:
            print(f"  {r['status']} {r['url']}")

    browser.close()


def main():
    with sync_playwright() as p:
        test_premier_league_deep(p)
        test_man_city_deep(p)


if __name__ == "__main__":
    main()
