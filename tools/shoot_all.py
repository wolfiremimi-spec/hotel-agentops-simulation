"""Full-page screenshots of every page of both apps on real Streamlit (pre-launch visual review)."""
import time, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
OUT = Path("shots"); OUT.mkdir(exist_ok=True)
log = open(OUT / "log.txt", "w")
def say(*a): print(*a, flush=True); print(*a, file=log, flush=True)
def settle(pg, s=2.5):
    time.sleep(1)
    for _ in range(80):
        if not pg.locator('[data-testid="stStatusWidget"]').count(): break
        time.sleep(0.25)
    time.sleep(s)
def shot(pg, name):
    pg.screenshot(path=str(OUT / f"{name}.png"), full_page=True)
    errs = pg.locator('[data-testid="stException"], [data-testid="stAlertContentError"]').count()
    say(name, "errors on page:", errs)
with sync_playwright() as pw:
    b = pw.chromium.launch(channel="chrome")
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    pg.goto("http://localhost:8501", wait_until="domcontentloaded"); pg.get_by_text("Cut breakfast waste.").first.wait_for(timeout=120000); settle(pg, 4)
    shot(pg, "a01_landing")
    pg.get_by_role("button", name="Try the live demo →").first.click(); settle(pg)
    shot(pg, "a02_today_start")
    pg.get_by_role("button", name="Save this morning's data and ask the agents").click(); settle(pg, 3)
    for r in pg.locator('[data-testid="stRadio"]').filter(has_text="Approve").all():
        r.get_by_text("Approve", exact=True).click(); time.sleep(0.6)
    shot(pg, "a03_today_decisions")
    pg.get_by_role("button", name="Save my decisions and today's plan").click(); settle(pg)
    shot(pg, "a04_today_saved")
    pg.get_by_role("button", name="Close out this service after breakfast →").click(); settle(pg)
    pg.get_by_role("button", name="Fill with the case study's modeled result").click(); settle(pg)
    pg.get_by_role("button", name="Save the close-out").click(); settle(pg)
    shot(pg, "a05_closeout")
    for nm, t in (("a06_orders", "Next week's order"), ("a07_log", "Decision log"), ("a08_perf", "Performance"),
                  ("a09_copilot", "Ops copilot"), ("a10_setup", "Hotel setup"), ("a11_videos", "How-to videos")):
        pg.locator('[data-testid="stSidebarNav"] a').filter(has_text=t).first.click(); settle(pg)
        shot(pg, nm)
    c = b.new_page(viewport={"width": 1440, "height": 900})
    c.goto("http://localhost:8502", wait_until="domcontentloaded"); time.sleep(8); settle(c, 3)
    shot(c, "b01_mission")
    links = c.locator('[data-testid="stSidebarNav"] a')
    names = [links.nth(i).inner_text() for i in range(links.count())]
    say("control room pages:", names)
    for i, n in enumerate(names[1:], 2):
        c.locator('[data-testid="stSidebarNav"] a').nth(i - 1).click(); settle(c, 3)
        shot(c, f"b{i:02d}_" + "".join(ch for ch in n if ch.isalnum())[:20])
    b.close()
