from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={"width":1600,"height":900})
    pg.goto("http://127.0.0.1:8191"); pg.wait_for_timeout(5000)
    pg.mouse.click(23,116); pg.wait_for_timeout(3000)
    pg.screenshot(path="x3d.png")
