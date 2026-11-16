"""Диагностика доступа к Notino из GitHub Actions (временный)."""
import sys, re, json, os, asyncio
URLS = sys.argv[1:] or ['https://www.notino.de/elmex/', 'https://www.notino.cz/elmex/']
os.makedirs('out', exist_ok=True)
try:
    from curl_cffi import requests as r
    for imp in ['chrome', 'safari', 'firefox']:
        for u in URLS[:2]:
            x = r.get(u, impersonate=imp, timeout=40)
            print('cffi', imp, u, x.status_code, len(x.text), 'Just a moment' in x.text)
except Exception as e:
    print('cffi err', e)
async def pw():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=False, channel='chrome', args=['--disable-blink-features=AutomationControlled'])
        ctx = await b.new_context(locale='de-DE', viewport={'width': 1300, 'height': 900},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36')
        await ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
        pg = await ctx.new_page()
        for i, u in enumerate(URLS):
            try:
                await pg.goto(u, timeout=60000)
                for _ in range(20):
                    t = await pg.title()
                    if 'moment' not in t.lower() and 'momentík' not in t.lower(): break
                    await pg.wait_for_timeout(1500)
                h = await pg.content()
                open(f'out/p{i}.html', 'w').write(h)
                print('pw', u, await pg.title(), len(h))
            except Exception as e:
                print('pw err', u, e)
        await b.close()
asyncio.run(pw())
