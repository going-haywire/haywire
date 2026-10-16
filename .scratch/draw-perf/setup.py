import sys
from playwright.sync_api import sync_playwright
graph=sys.argv[1]
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={"width":1600,"height":900})
    pg.goto("http://127.0.0.1:8191"); pg.wait_for_timeout(5000)
    pg.get_by_text("graphs", exact=True).first.click(); pg.wait_for_timeout(800)
    pg.get_by_text(graph+".haywire").first.click(button="right"); pg.wait_for_timeout(800)
    pg.get_by_text("Load into Haystack").click(); pg.wait_for_timeout(6000)
    b.close()
