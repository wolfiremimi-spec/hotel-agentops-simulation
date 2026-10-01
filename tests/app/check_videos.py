import os, sys
sys.path.insert(0, os.path.dirname(__file__)); import stlite
REPO = str(__import__("pathlib").Path(__file__).resolve().parents[2]); os.chdir(REPO); sys.path.insert(0, REPO)
H, st = stlite.H, sys.modules["streamlit"]
ok = []
def check(n, c, d=""): ok.append(bool(c)); print(("PASS " if c else "FAIL ") + n + ("" if c else f"  [{str(d)[:500]}]"))
def text(): return "\n".join(" ".join(map(str, o[1:])) for o in H.out)
from product import site
stlite.run_app("hotel_app.py"); t = text()
check("landing: Videos tab in the top menu", 'href="#videos">Videos</a>' in t)
check("landing: how-to videos section with both thumbnails", "Watch how it works first." in t and t.count("<div class=\"ws-vidthumb\">") == 2)
check("video files exist", all((site.ASSETS / "videos" / v["file"]).is_file() for v in site.HOW_TO_VIDEOS))
H.clicks.add("ha_play_setup"); stlite.run_app("hotel_app.py"); t = text()
vids = [o for o in H.out if o[0] == "video"]
check("play button opens the videos page", H.current_page == "product/views/videos.py", H.current_page)
check("both videos on the page, the chosen one first", len(vids) == 2 and "how_to_set_up_your_hotel" in str(vids[0]) and "cdn.jsdelivr.net" in str(vids[0]), vids)
H.clicks.add("hv_back"); stlite.run_app("hotel_app.py")
check("back button returns to the website", H.current_page == "product/views/welcome.py", H.current_page)
H.clicks.add("ha_videos"); stlite.run_app("hotel_app.py"); H.clicks.add("hv_demo"); stlite.run_app("hotel_app.py")
check("'Try the live demo' on the videos page opens the demo", H.current_page == "product/views/today.py", H.current_page)
print(f"\n{sum(ok)}/{len(ok)} checks passed")
