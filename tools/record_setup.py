"""Records the second walkthrough: a hotel setting up its own workspace and running its first morning with its own figures.

Runs in GitHub Actions with HA_LOCAL_DB=1 (workspaces kept in memory for the recording). The hotel is a fictional example.
"""
import datetime as dt
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from record_demo import CARD_JS, OUT, URL, W, H, CHROME, Demo, log, step  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

HOTEL = "Harbour Example Hotel"
GROUPS = ["pastry_bread", "hot_line", "fruit_yogurt", "cold_cuts_cheese"]


def history_csv(path: Path, today: dt.date) -> Path:
    """Four earlier services on today's weekday plus a week of forecast errors: the example hotel's own records."""
    cols = (["date", "occupied_rooms", "covers", "forecast_error_pct"] + [f"leftover_pct_{g}" for g in GROUPS]
            + [f"ran_out_{g}" for g in GROUPS])
    same = [(146, 258, [27, 4, 16, 11], [0, 1, 0, 0]), (152, 270, [25, 3, 15, 12], [0, 0, 0, 0]),
            (141, 249, [29, 5, 17, 10], [0, 0, 0, 0]), (149, 263, [26, 2, 14, 11], [0, 1, 0, 0])]
    rows = []
    for i, (occ, cov, left, out) in enumerate(same, 1):
        d = today - dt.timedelta(days=7 * i)
        rows.append([d.isoformat(), occ, cov, ""] + left + ["TRUE" if o else "FALSE" for o in out])
    for i, err in enumerate([6.2, 7.8, 5.4, 8.1, 6.9, 7.3], 1):
        d = today - dt.timedelta(days=i)
        rows.append([d.isoformat(), "", "", err] + [""] * 4 + [""] * 4)
    path.write_text(",".join(cols) + "\n" + "\n".join(",".join(str(v) for v in r) for r in rows) + "\n")
    return path


def main():
    csv = history_csv(OUT / f"{HOTEL.split()[0].lower()}_history.csv", dt.date.today())
    with sync_playwright() as pw:
        headed = os.environ.get("DEMO_HEADED", "1") == "1"
        browser = pw.chromium.launch(headless=not headed, ignore_default_args=["--enable-automation"],
                                     args=[f"--window-size={W},{H + CHROME}", "--window-position=0,0", "--kiosk",
                                           "--force-device-scale-factor=1", "--disable-infobars", "--hide-scrollbars"])
        ctx = browser.new_context(no_viewport=True) if headed else browser.new_context(viewport={"width": W, "height": H})
        page = ctx.new_page()
        page.set_default_timeout(30000)
        d = Demo(page)
        page.goto(URL, wait_until="domcontentloaded")
        page.get_by_text("Cut breakfast waste.").first.wait_for(timeout=120000)
        d.idle(1.5)
        chrome = page.evaluate("window.outerHeight - window.innerHeight") if headed else 0
        (OUT / "chrome.txt").write_text(str(int(chrome)))
        (OUT / "start.txt").write_text(str(time.time()))
        results, code = [], {}

        def typ(loc, text, delay=45):
            d.move_to(loc)
            loc.click()
            loc.fill("")
            loc.type(str(text), delay=delay)
            loc.press("Tab")
            time.sleep(0.25)

        d.card("Set up your own hotel", "From an empty workspace to your first governed morning with your own figures: "
               "create, configure, import history, plan, decide and close out.", 3.5)

        def s_create():
            d.cap("Go to <b>hotel-agentops.streamlit.app</b> and click <b>Set up your hotel</b>.", 0.4)
            d.click(page.get_by_text("Set up your hotel", exact=True).first, after=1.5)
            d.cap("Create a private workspace: your hotel's name, rooms and who approves the plan.", 0.3)
            typ(page.get_by_label("Hotel name"), HOTEL)
            typ(page.get_by_label("Rooms"), "180", delay=90)
            d.click(page.get_by_role("button", name="Create workspace"), after=2.0)
        results.append(step(d, "create", s_create))

        def s_code():
            d.overlay()
            d.to_top()
            loc = page.locator(".ha-code").first
            code["v"] = loc.inner_text().strip()
            log("access code", code["v"])
            d.cap("Save your <b>access code</b>. It's how you and your team get back in, and it can't be recovered.", 0.3)
            d.move_to(loc); time.sleep(2.4)
            d.click(page.get_by_role("button", name="I've saved the code"), after=1.2)
        results.append(step(d, "access_code", s_code))

        def s_setup():
            d.cap("<b>Step 1 · Hotel setup.</b> Your costs, outlets, menu, par levels and rules.", 0.2)
            d.nav("Hotel setup")
            typ(page.get_by_label("Outlet that can use near-expiry stock"), "Staff canteen")
            typ(page.get_by_label("Food waste cost ($ per kg)"), "12.50", delay=90)
            d.click(page.get_by_role("tab", name="Menu & par levels"), after=0.6)
            d.cap("Enter your standing par: what your kitchen prepares today without AI.", 0.3)
            for label, v in (("Pastry & bread standing par (kg)", "30"), ("Hot line standing par (kg)", "46"),
                             ("Fruit & yogurt standing par (kg)", "34"), ("Cold cuts & cheese standing par (kg)", "15")):
                typ(page.get_by_label(label), v, delay=80)
            d.cap("Below it, the menu items your staff search for when they record stock.", 0.3)
            d.scroll(380, 1.1); time.sleep(1.2)
            d.click(page.get_by_role("tab", name="Governance policy"), after=0.6)
            d.cap("Your rules: how much the agents may change alone, and whether they run as AI agents.", 2.4)
            d.click(page.get_by_role("button", name="Save setup"), after=1.5)
        results.append(step(d, "setup", s_setup))

        def s_history():
            d.cap("<b>Step 2 · History.</b> Import a few weeks of past services from the spreadsheet template.", 0.3)
            up = page.locator('[data-testid="stFileUploader"]').first
            d.move_to(up); time.sleep(0.6)
            page.locator('[data-testid="stFileUploader"] input[type="file"]').first.set_input_files(str(csv))
            d.idle(1.0)
            d.click(page.get_by_role("button", name="Import these rows (replaces the baseline history)"), after=1.5)
            d.cap("Imported. The agents now plan from your hotel's own services.", 0.3)
            d.to_top(); d.click(page.get_by_role("tab", name="Baseline history"), after=0.5); time.sleep(1.8)
        results.append(step(d, "history", s_history))

        def s_morning():
            d.cap("<b>Step 3 · Every morning,</b> enter today's figures from your PMS and kitchen.", 0.2)
            d.nav("Today's plan")
            d.scroll(560, 1.2)
            typ(page.get_by_label("Occupied rooms tonight (of 180)"), "151", delay=90)
            typ(page.get_by_label("In-house guests"), "268", delay=90)
            typ(page.get_by_label("Breakfast-inclusive rooms"), "118", delay=90)
            typ(page.get_by_label("Outside breakfast bookings"), "6", delay=90)
            notes = page.get_by_label("Front-desk notes (groups arriving, early check-outs, anything unusual)")
            d.move_to(notes); notes.click(); notes.type("Tour group of 24 arriving for breakfast at 7:30.", delay=25)
            d.click(page.get_by_role("tab", name="Inventory"), after=0.5)
            typ(page.get_by_label("Hours since the inventory count", exact=False), "3", delay=90)
            d.click(page.get_by_role("tab", name="Events"), after=0.4)
            d.click(page.get_by_text("I have checked the events calendar", exact=False).first, after=0.3)
            d.click(page.get_by_role("tab", name="Guest signal"), after=0.4)
            typ(page.get_by_label("Recent guest F&B score (1–5)"), "4.62", delay=90)
            d.cap("Save it, and the agents analyse the morning.", 0.2)
            d.click(page.get_by_role("button", name="Save this morning's data and ask the agents"), after=2.5)
        results.append(step(d, "morning", s_morning))

        def s_decide():
            d.cap("<b>Step 4 · Decide.</b> Governance routes each recommendation; you approve what needs you.", 1.0)
            d.scroll(650, 1.6)
            groups = page.locator('[data-testid="stRadio"]').filter(has_text="Approve")
            n = groups.count()
            log("decision groups", n)
            for i in range(n):
                d.click(groups.nth(i).get_by_text("Approve", exact=True), after=0.4)
            d.click(page.get_by_role("button", name="Save my decisions and today's plan"), after=2.0)
            d.to_top()
            d.cap("Your plan becomes the kitchen's production sheet, ready to print.", 0.3)
            d.move_to(page.get_by_text("Printable kitchen sheet").first); time.sleep(1.8)
        results.append(step(d, "decide", s_decide))

        def s_close():
            d.cap("<b>Step 5 · After breakfast,</b> weigh what's left and close out the service.", 0.2)
            d.click(page.get_by_role("button", name="Close out this service after breakfast →"), after=1.8)
            d.overlay()
            typ(page.get_by_label("Actual covers served"), "259", delay=90)
            for label, v in (("Pastry & bread left", "2.8"), ("Hot line left", "1.1"), ("Fruit & yogurt left", "2.2"),
                             ("Cold cuts & cheese left", "0.9")):
                typ(page.get_by_label(label, exact=False), v, delay=80)
            d.click(page.get_by_role("button", name="Save the close-out"), after=2.0)
            m = page.locator('[data-testid="stMetric"]').filter(has_text="Covers").first
            got = m.inner_text() if m.count() else ""
            log("close-out covers metric:", got.replace("\n", " | "))
            if "259" not in got:
                raise AssertionError("covers not saved as typed: " + got)
            d.cap("The day is scored against your standing par, and your track record grows.", 0.3)
            d.scroll(300, 1.0); time.sleep(2.0)
        results.append(step(d, "close_out", s_close))

        def s_perf():
            d.cap("<b>Step 6 · Earned autonomy.</b> The agents start supervised and earn independence from your results.", 0.2)
            d.nav("Performance")
            time.sleep(1.0); d.scroll(420, 1.4); time.sleep(1.8)
        results.append(step(d, "performance", s_perf))

        def s_reopen():
            d.cap("Tomorrow, open your workspace with your access code.", 0.2)
            d.click(page.get_by_role("button", name="Leave workspace"), after=1.8)
            d.overlay()
            box = page.get_by_label("Access code")
            d.move_to(box)
            box.click(); box.type(code.get("v", ""), delay=70)
            d.click(page.get_by_role("button", name="Open", exact=True), after=2.0)
            d.cap(f"Back in {HOTEL}, with everything saved.", 2.4)
        results.append(step(d, "reopen", s_reopen))

        def s_end():
            d.cap("", 0.2)
            d.card("Your hotel, your figures", "<b style='color:#fff'>hotel-agentops.streamlit.app</b><br>Pilot application · "
                   "you enter your own figures; no hotel systems are connected. The hotel in this video is an example.", 4.0)
        results.append(step(d, "end", s_end))

        log("RESULTS", results)
        (OUT / "end.txt").write_text(str(time.time()))
        ctx.close(); browser.close()
        return all(results)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
