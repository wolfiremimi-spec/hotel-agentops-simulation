"""Records a narrated (captioned) walkthrough of the pilot app: one full breakfast service in the demo hotel.

Runs in GitHub Actions (see .github/workflows/record-demo.yml): the real app is started with `streamlit run`, a headed
Chromium drives it like a visitor while ffmpeg records the screen. Captions and a visible cursor are overlaid in the page.
"""
import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = os.environ.get("APP_URL", "http://localhost:8501")
OUT = Path(os.environ.get("DEMO_OUT", "demo_out"))
OUT.mkdir(exist_ok=True)
W, H = int(os.environ.get("DEMO_W", 1600)), int(os.environ.get("DEMO_H", 900))
CHROME = int(os.environ.get("DEMO_CHROME", 0))          # extra window height for the browser's own bar, cropped later
LOG = open(OUT / "log.txt", "w")


def log(*a):
    print(*a, flush=True)
    print(*a, file=LOG, flush=True)


OVERLAY_JS = r"""
() => {
  if (!document.getElementById('__cap')) {
    const c = document.createElement('div'); c.id = '__cap';
    Object.assign(c.style, {position:'fixed', left:'50%', bottom:'30px', transform:'translateX(-50%)', zIndex: 2147483646,
      background:'rgba(23,33,28,.92)', color:'#fff', font:'600 25px/1.4 Inter, "Helvetica Neue", Arial, sans-serif',
      padding:'14px 28px', borderRadius:'14px', maxWidth:'1250px', textAlign:'center', opacity:0,
      boxShadow:'0 12px 30px rgba(0,0,0,.28)', transition:'opacity .35s', pointerEvents:'none'});
    document.body.appendChild(c);
  }
  if (!document.getElementById('__cur')) {
    const m = document.createElement('div'); m.id = '__cur';
    Object.assign(m.style, {position:'fixed', left:'-100px', top:'-100px', width:'26px', height:'26px', marginLeft:'-13px',
      marginTop:'-13px', borderRadius:'50%', background:'rgba(199,168,119,.45)', border:'3px solid #1F3A2F',
      zIndex: 2147483647, pointerEvents:'none', transition:'transform .15s'});
    document.body.appendChild(m);
    document.addEventListener('mousemove', e => { m.style.left = e.clientX + 'px'; m.style.top = e.clientY + 'px'; }, true);
    document.addEventListener('mousedown', () => { m.style.transform = 'scale(.6)'; }, true);
    document.addEventListener('mouseup', () => { m.style.transform = 'scale(1)'; }, true);
  }
}
"""
CAPTION_JS = r"""(t) => { const c = document.getElementById('__cap'); if (!c) return; if (t) { c.innerHTML = t; c.style.opacity = 1; } else { c.style.opacity = 0; } }"""
CARD_JS = r"""
([title, sub, show]) => {
  let d = document.getElementById('__card');
  if (!d) { d = document.createElement('div'); d.id = '__card';
    Object.assign(d.style, {position:'fixed', inset:0, zIndex: 2147483645, background:'#1F3A2F', color:'#fff', display:'flex',
      flexDirection:'column', justifyContent:'center', padding:'0 140px', transition:'opacity .6s', opacity:0,
      font:'400 30px/1.4 Inter, "Helvetica Neue", Arial, sans-serif'});
    document.body.appendChild(d); }
  d.innerHTML = `<div style="font-size:20px;letter-spacing:.2em;text-transform:uppercase;color:#C7A877;font-weight:700">Hotel AgentOps · by Amelia Wolfire</div>
    <div style="font-size:72px;font-weight:800;line-height:1.08;margin:18px 0 22px;letter-spacing:-.01em">${title}</div>
    <div style="font-size:30px;color:#E8DDC4;max-width:1150px">${sub}</div>`;
  d.style.opacity = show ? 1 : 0; d.style.pointerEvents = show ? 'auto' : 'none';
  const cur = document.getElementById('__cur'); if (cur) cur.style.display = show ? 'none' : 'block';
}
"""


class Demo:
    def __init__(self, page):
        self.p = page
        self.n = 0

    def overlay(self):
        try:
            self.p.evaluate(OVERLAY_JS)
        except Exception as ex:
            log("overlay failed", ex)

    def cap(self, text, hold=0.0):
        self.overlay()
        self.p.evaluate(CAPTION_JS, text)
        log("CAPTION", text)
        time.sleep(hold)

    def card(self, title, sub, hold):
        self.overlay()
        self.p.evaluate(CARD_JS, [title, sub, True])
        time.sleep(hold)
        self.p.evaluate(CARD_JS, [title, sub, False])
        time.sleep(0.8)

    def shot(self, name):
        self.n += 1
        try:
            self.p.screenshot(path=str(OUT / f"{self.n:02d}_{name}.png"))
        except Exception as ex:
            log("screenshot failed", ex)

    def idle(self, extra=0.6, timeout=90):
        """Wait until Streamlit has finished rerunning."""
        time.sleep(0.5)
        end = time.time() + timeout
        while time.time() < end:
            running = self.p.locator('[data-testid="stStatusWidget"]').count()
            if not running:
                break
            time.sleep(0.25)
        time.sleep(extra)

    def move_to(self, loc, steps=28):
        loc.scroll_into_view_if_needed(timeout=15000)
        time.sleep(0.4)
        b = loc.bounding_box()
        if b:
            self.p.mouse.move(b["x"] + b["width"] / 2, b["y"] + b["height"] / 2, steps=steps)
        time.sleep(0.35)

    def click(self, loc, after=1.2):
        self.move_to(loc)
        loc.click(timeout=15000)
        self.idle(after)

    def scroll(self, dy, secs=1.6):
        self.p.mouse.move(W * 0.62, H * 0.5, steps=12)
        steps = max(int(secs / 0.03), 1)
        for _ in range(steps):
            self.p.mouse.wheel(0, dy / steps)
            time.sleep(0.03)
        time.sleep(0.4)

    def to_top(self):
        self.p.evaluate("""() => { const m = document.querySelector('[data-testid="stMain"]') || document.querySelector('section.main');
                                   if (m) m.scrollTo({top: 0, behavior: 'smooth'}); window.scrollTo({top:0, behavior:'smooth'}); }""")
        time.sleep(0.9)

    def nav(self, text):
        link = self.p.locator('[data-testid="stSidebarNav"] a, [data-testid="stSidebarNavLink"]').filter(has_text=text).first
        self.click(link, after=1.5)
        self.overlay()


def step(demo, name, fn):
    try:
        fn()
        demo.shot(name)
        log("OK  ", name)
        return True
    except Exception as ex:
        log("FAIL", name, type(ex).__name__, str(ex)[:400])
        demo.shot("FAIL_" + name)
        return False


def main():
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
        log("browser chrome height", chrome, "inner", page.evaluate("[window.innerWidth, window.innerHeight]"))
        (OUT / "start.txt").write_text(str(time.time()))
        results = []

        d.card("How to run the app", "A short walkthrough of one full breakfast service in the demo hotel: "
               "plan, decide, close out, audit and order.", 3.5)

        def s_landing():
            d.cap("Go to <b>hotel-agentops.streamlit.app</b> and click <b>Try the live demo</b>. No sign-up needed.", 1.5)
            d.scroll(450, 1.1); time.sleep(0.3); d.to_top()
            d.click(page.get_by_role("button", name="Try the live demo →"), after=2.0)
        results.append(step(d, "landing", s_landing))

        def s_today():
            d.cap("<b>Step 1 · Today's plan.</b> The Saturday morning (D-0418) is prefilled from the case study.", 2.6)
            d.cap("Each tab is a data source the agents read: occupancy, inventory, events and guest signal.", 0.6)
            for tab in ("Inventory", "Occupancy & reservations"):
                d.click(page.get_by_role("tab", name=tab), after=1.0)
            d.cap("Click <b>Save this morning's data and ask the agents</b>.", 0.4)
            d.click(page.get_by_role("button", name="Save this morning's data and ask the agents"), after=2.5)
        results.append(step(d, "today_inputs", s_today))

        def s_decide():
            d.cap("<b>Step 2 · The agents recommend.</b> Four AI specialists analyze the morning, and governance routes each decision.", 2.0)
            d.scroll(700, 1.8); time.sleep(0.6)
            d.cap("Nothing is pre-selected. For each decision, choose <b>Approve</b>, Modify, Reject or Request more context.", 0.8)
            groups = page.locator('[data-testid="stRadio"]').filter(has_text="Approve")
            n = groups.count()
            log("decision groups", n)
            for i in range(n):
                d.click(groups.nth(i).get_by_text("Approve", exact=True), after=0.4)
            d.cap("Then save the plan.", 0.3)
            d.click(page.get_by_role("button", name="Save my decisions and today's plan"), after=2.0)
        results.append(step(d, "decide", s_decide))

        def s_saved():
            d.to_top()
            d.cap("The approved plan becomes the kitchen's production sheet: print it or download it.", 1.0)
            d.move_to(page.get_by_text("Printable kitchen sheet").first); time.sleep(1.4)
            d.scroll(450, 1.2); time.sleep(0.4)
            d.cap("<b>Step 3 · After breakfast,</b> close out the service.", 0.5)
            d.click(page.get_by_role("button", name="Close out this service after breakfast →"), after=2.0)
        results.append(step(d, "saved_plan", s_saved))

        def s_close():
            d.overlay()
            d.cap("Record what actually happened. In the demo, fill in the case study's result.", 1.0)
            d.click(page.get_by_role("button", name="Fill with the case study's modeled result"), after=1.2)
            d.click(page.get_by_role("button", name="Save the close-out"), after=2.0)
            d.cap("The day is scored against standing par: <b>23.3 kg</b> of waste instead of <b>47.3 kg</b>, and no stockouts.", 1.0)
            d.scroll(400, 1.2); time.sleep(1.6)
        results.append(step(d, "close_out", s_close))

        def s_log():
            d.cap("<b>Step 4 · Decision log.</b> Every decision, who made it, and the rule that routed it.", 0.3)
            d.nav("Decision log")
            time.sleep(0.8); d.scroll(650, 1.6)
            sel = page.locator('[data-testid="stSelectbox"]').filter(has_text="Decision").first
            d.click(sel, after=0.6)
            opt = page.get_by_role("option", name="D-0418")
            if opt.count():
                d.click(opt.first, after=1.2)
            d.cap("Follow D-0418 end to end: input, agent, governance, human decision, action and outcome.", 1.0)
            d.scroll(350, 1.0); time.sleep(1.8)
        results.append(step(d, "decision_log", s_log))

        def s_perf():
            d.cap("<b>Step 5 · Performance & autonomy.</b> Autonomy is earned from the hotel's own record through eight readiness checks.", 0.3)
            d.nav("Performance")
            time.sleep(1.4); d.scroll(600, 1.6); time.sleep(1.6)
        results.append(step(d, "performance", s_perf))

        def s_order():
            d.cap("<b>Step 6 · Next week's order.</b> Order less of what's left over and more of what runs out.", 0.3)
            d.nav("Next week's order")
            time.sleep(0.8); d.scroll(750, 1.8); time.sleep(1.8)
            d.cap("Review the suggestion, change any quantity and approve it. A manager approves every order.", 0.6)
            d.click(page.get_by_role("button", name="Approve and log this order"), after=1.6)
        results.append(step(d, "order", s_order))

        def s_end():
            d.cap("The guided tour in the sidebar tracks each step. That's a full governed day.", 2.8)
            d.cap("", 0.3)
            d.card("Try it yourself", "<b style='color:#fff'>hotel-agentops.streamlit.app</b><br>Demo runs on modeled "
                   "case-study data · no live hotel systems are connected.", 4.0)
        results.append(step(d, "end", s_end))

        log("RESULTS", results)
        (OUT / "end.txt").write_text(str(time.time()))
        ctx.close()
        browser.close()
        return all(results)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
