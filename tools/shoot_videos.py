"""Opens the real app, checks the how-to videos section and page, and confirms both videos load and play."""
import time, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
OUT = Path("shots"); OUT.mkdir(exist_ok=True)
log = open(OUT / "log.txt", "w")
def say(*a): print(*a, flush=True); print(*a, file=log, flush=True)
ok = True
with sync_playwright() as pw:
    b = pw.chromium.launch(); pg = b.new_page(viewport={"width": 1440, "height": 900})
    pg.goto("http://localhost:8501", wait_until="domcontentloaded"); pg.get_by_text("Cut breakfast waste.").first.wait_for(timeout=120000); time.sleep(2)
    pg.screenshot(path=str(OUT / "1_top.png"))
    pg.locator('a[href="#videos"]').first.click(); time.sleep(1.5)
    pg.screenshot(path=str(OUT / "2_videos_section.png"))
    pg.get_by_role("button", name="▶ Play: How to set up your own hotel").click(); time.sleep(4)
    say("url after play:", pg.url)
    pg.screenshot(path=str(OUT / "3_videos_page.png"), full_page=True)
    vids = pg.locator("video")
    say("video elements:", vids.count())
    for i in range(vids.count()):
        v = vids.nth(i)
        v.scroll_into_view_if_needed()
        info = v.evaluate("""async v => { v.muted = true; try { await v.play(); } catch(e) { return {err: String(e)} }
            await new Promise(r => setTimeout(r, 2500)); return {src: v.currentSrc.slice(-60), t: v.currentTime, dur: v.duration, w: v.videoWidth, rs: v.readyState}; }""")
        say("video", i, info)
        if not info.get("t") or info.get("t", 0) < 1 or not info.get("w"): ok = False
    pg.screenshot(path=str(OUT / "4_playing.png"))
    pg.get_by_role("button", name="← Back to the website").click(); time.sleep(3)
    say("back ok:", pg.get_by_text("Cut breakfast waste.").count() > 0)
    b.close()
say("RESULT", ok); sys.exit(0 if ok else 1)
