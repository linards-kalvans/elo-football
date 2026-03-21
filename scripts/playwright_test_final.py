"""Final diagnostic — confirm the Alpine scope issue and data flow."""

import json
from playwright.sync_api import sync_playwright


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        for url, label in [
            ("http://localhost:8003/england/premier-league", "PL"),
            ("http://localhost:8003/england/premier-league/man-city", "Man City"),
        ]:
            page = browser.new_page()
            console_msgs = []
            page.on("console", lambda m: console_msgs.append(m))

            page.goto(url, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(2000)

            # Click view details
            vd = page.locator("text=View details")
            if vd.count() > 0:
                vd.first.click()
                page.wait_for_timeout(4000)

            # Comprehensive DOM inspection
            result = page.evaluate("""
                () => {
                    // Get ALL x-data elements and their Alpine state
                    const elements = document.querySelectorAll('[x-data]');
                    const alpineData = [];
                    elements.forEach((el, i) => {
                        let data = null;
                        try {
                            data = window.Alpine.$data(el);
                        } catch(e) {}

                        alpineData.push({
                            index: i,
                            tag: el.tagName,
                            id: el.id || '(none)',
                            xdata_attr: el.getAttribute('x-data').substring(0, 50),
                            has_historyData: data ? ('historyData' in data) : false,
                            has_accuracyView: data ? ('accuracyView' in data) : false,
                            accuracyView: data ? data.accuracyView : null,
                            historyData_items: data && data.historyData && data.historyData.items
                                ? data.historyData.items.length : 'N/A',
                            historyData_total: data && data.historyData ? data.historyData.total : 'N/A',
                        });
                    });

                    // Find the eloPage component specifically
                    let eloPageEl = null;
                    elements.forEach(el => {
                        if (el.getAttribute('x-data') === 'eloPage()') eloPageEl = el;
                    });

                    let eloPageData = null;
                    if (eloPageEl) {
                        try {
                            const d = window.Alpine.$data(eloPageEl);
                            eloPageData = {
                                accuracyView: d.accuracyView,
                                historyData_items: d.historyData && d.historyData.items ? d.historyData.items.length : 'N/A',
                                historyData_total: d.historyData ? d.historyData.total : 'N/A',
                                historyData_pages: d.historyData ? d.historyData.pages : 'N/A',
                                loadingHistory: d.loadingHistory,
                                level: d.level,
                                teamId: d.teamId,
                                competition: d.competition,
                            };
                        } catch(e) {
                            eloPageData = {error: String(e)};
                        }
                    }

                    // Table row counts
                    const tables = document.querySelectorAll('table');
                    const tableInfo = [];
                    tables.forEach((t, i) => {
                        const rows = t.querySelectorAll('tbody tr').length;
                        tableInfo.push({index: i, rows: rows, html_len: t.innerHTML.length});
                    });

                    // Check x-if template for historyData.items.length > 0
                    let xifRendered = false;
                    const templates = document.querySelectorAll('template');
                    templates.forEach(t => {
                        if (t.getAttribute('x-if') === 'historyData.items.length > 0') {
                            // If rendered, nextSibling would be an element; if not, a comment
                            const ns = t.nextSibling;
                            xifRendered = ns && ns.nodeType === 1; // element node
                        }
                    });

                    return {
                        alpineData,
                        eloPageData,
                        tableInfo,
                        xifRendered,
                    };
                }
            """)

            print(f"\n{'='*60}")
            print(f"RESULT: {label} ({url})")
            print("="*60)
            print("\n[x-data elements]")
            for d in result["alpineData"]:
                print(f"  [{d['index']}] {d['tag']} x-data={d['xdata_attr']}")
                print(f"       has_historyData={d['has_historyData']}, has_accuracyView={d['has_accuracyView']}")
                if d['has_historyData']:
                    print(f"       historyData items={d['historyData_items']}, total={d['historyData_total']}")
                if d['has_accuracyView']:
                    print(f"       accuracyView={d['accuracyView']}")

            print("\n[eloPage() component]")
            print(json.dumps(result["eloPageData"], indent=2))

            print("\n[Tables]")
            for t in result["tableInfo"]:
                print(f"  Table {t['index']+1}: {t['rows']} rows, html_len={t['html_len']}")

            print(f"\n[x-if 'historyData.items.length > 0' rendered]: {result['xifRendered']}")

            # Check console warnings
            warnings = [m for m in console_msgs if m.type in ("warning", "error")
                        and "historyData" in m.text or "items" in m.text.lower()]
            if warnings:
                print("\n[Key console messages about historyData]")
                for w in warnings[:5]:
                    print(f"  [{w.type}] {w.text[:200]}")

            page.close()

        browser.close()


if __name__ == "__main__":
    main()
