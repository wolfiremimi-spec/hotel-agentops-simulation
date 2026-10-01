"""High-resolution, full-length captures of every page of both apps (for the product trailer)."""
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path("shots"); OUT.mkdir(exist_ok=True)
log = open(OUT / "log.txt", "w")
W, SCALE = 1440, 1.5


def say(*a):
    print(*a, flush=True); print(*a, file=log, flush=True)


def settle(pg, s=2.0):
    time.sleep(0.8)
    for _ in range(120):
        if not pg.locator('[data-testid="stStatusWidget"]').count():
            break
        time.sleep(0.25)
    time.sleep(s)


def tall(pg, name, max_h=8600):
    h = pg.evaluate("(() => { const m = document.querySelector('[data-testid=stMain]'); return m ? m.scrollHeight : document.body.scrollHeight; })()")
    h = int(min(max(h, 900), max_h))
    pg.set_viewport_size({"width": W, "height": h})
    settle(pg, 2.5)
    pg.screenshot(path=str(OUT / f"{name}.png"))
    errs = pg.locator('[data-testid="stException"]').count()
    say(name, "height", h, "errors", errs)
    pg.set_viewport_size({"width": W, "height": 900})
    settle(pg, 1.0)


def view(pg, name):
    pg.screenshot(path=str(OUT / f"{name}.png"))
    say(name, "viewport")


with sync_playwright() as pw:
    b = pw.chromium.launch(channel="chrome")
    ctx = b.new_context(viewport={"width": W, "height": 900}, device_scale_factor=SCALE)
    pg = ctx.new_page()
    pg.goto("http://localhost:8501", wait_until="domcontentloaded")
    pg.get_by_text("Cut breakfast waste.").first.wait_for(timeout=120000)
    settle(pg, 4)
    view(pg, "web_hero")
    tall(pg, "web_full")
    pg.get_by_role("button", name="Try the live demo →").first.click(); settle(pg)
    tall(pg, "app_today_start")
    pg.get_by_role("button", name="Save this morning's data and ask the agents").click(); settle(pg, 3)
    tall(pg, "app_recommendations")
    for r in pg.locator('[data-testid="stRadio"]').filter(has_text="Approve").all():
        r.get_by_text("Approve", exact=True).click(); time.sleep(0.6)
    settle(pg, 1)
    tall(pg, "app_decided")
    pg.get_by_role("button", name="Save my decisions and today's plan").click(); settle(pg)
    tall(pg, "app_saved")
    pg.get_by_role("button", name="Close out this service after breakfast →").click(); settle(pg)
    pg.get_by_role("button", name="Fill with the case study's modeled result").click(); settle(pg)
    pg.get_by_role("button", name="Save the close-out").click(); settle(pg)
    tall(pg, "app_closeout")
    for nm, t in (("app_orders", "Next week's order"), ("app_log", "Decision log"), ("app_perf", "Performance"),
                  ("app_videos", "How-to videos"), ("app_setup", "Hotel setup")):
        pg.locator('[data-testid="stSidebarNav"] a').filter(has_text=t).first.click(); settle(pg)
        tall(pg, nm)
    # a real workspace: create one and show its access code
    pg.get_by_role("button", name="Leave workspace").click(); settle(pg)
    pg.get_by_label("Hotel name").fill("Harbor Example Hotel"); pg.get_by_label("Rooms").fill("180")
    pg.get_by_role("button", name="Create workspace").click(); settle(pg)
    view(pg, "app_access_code")

    c = ctx.new_page()
    c.goto("http://localhost:8502", wait_until="domcontentloaded"); time.sleep(8); settle(c, 3)
    tall(c, "cr_mission")
    links = c.locator('[data-testid="stSidebarNav"] a')
    names = [links.nth(i).inner_text() for i in range(links.count())]
    for i, n in enumerate(names[1:], 1):
        c.locator('[data-testid="stSidebarNav"] a').nth(i).click(); settle(c, 3)
        tall(c, "cr_" + "".join(ch for ch in n.lower() if ch.isalnum())[:18])
    b.close()
