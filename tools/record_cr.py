"""Records a short clean tour of the Control Room (the case-study simulation) for the product walkthrough video."""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from record_demo import OUT, W, H, CHROME, DSF, Demo, log, step  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

URL = os.environ.get("CR_URL", "http://localhost:8502")


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False, ignore_default_args=["--enable-automation"],
                                     args=[f"--window-size={W},{H + CHROME}", "--window-position=0,0", "--kiosk",
                                           f"--force-device-scale-factor={DSF}", "--disable-infobars", "--hide-scrollbars"])
        ctx = browser.new_context(no_viewport=True)
        page = ctx.new_page()
        page.set_default_timeout(30000)
        d = Demo(page)
        page.goto(URL, wait_until="domcontentloaded")
        page.get_by_text("Try the system yourself").first.wait_for(timeout=120000)
        d.idle(3.0)
        chrome = page.evaluate("window.outerHeight - window.innerHeight")
        (OUT / "chrome.txt").write_text(str(int(chrome)))
        (OUT / "viewport.txt").write_text(" ".join(str(v) for v in page.evaluate(
            "[window.innerWidth, window.innerHeight, window.devicePixelRatio, window.outerHeight - window.innerHeight]")))
        (OUT / "start.txt").write_text(str(time.time()))
        d.t0 = time.time(); d.overlay()
        results = []

        def s_mission():
            time.sleep(1.5)
            d.move_to(page.get_by_text("Suggested path").first); time.sleep(1.2)
            d.scroll(700, 2.0); time.sleep(1.5)
            d.scroll(600, 1.6); time.sleep(1.5)
        results.append(step(d, "cr_mission", s_mission))

        def s_live():
            d.nav("Live Service")
            time.sleep(1.5); d.scroll(600, 1.8); time.sleep(1.8)
        results.append(step(d, "cr_live", s_live))

        def s_proc():
            d.nav("Procurement")
            time.sleep(1.5); d.scroll(650, 1.8); time.sleep(1.8)
        results.append(step(d, "cr_procurement", s_proc))

        def s_gate():
            d.nav("Readiness Gate")
            time.sleep(1.5); d.scroll(650, 1.8); time.sleep(1.8)
        results.append(step(d, "cr_gate", s_gate))

        def s_value():
            d.nav("Business Value")
            time.sleep(1.5); d.scroll(650, 1.8); time.sleep(2.0)
        results.append(step(d, "cr_value", s_value))

        log("RESULTS", results)
        (OUT / "end.txt").write_text(str(time.time()))
        ctx.close(); browser.close()
        return all(results)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
