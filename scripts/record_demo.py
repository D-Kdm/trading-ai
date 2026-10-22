"""
Records a short demo video of the dashboard (for LinkedIn / YouTube).

Extra tools needed (only for this script, not for the app):
    pip install playwright imageio-ffmpeg
The server must be running first:
    uvicorn main:app --reload
Then run:
    python scripts/record_demo.py
Output: media/trading-ai-demo.mp4  (1920x1080, ~40 seconds, no sound)

How it works: Playwright drives your installed Chrome, Chrome streams a
screenshot every time the page changes, and ffmpeg stitches them into an MP4.
"""
import asyncio
import base64
import os
import subprocess

import imageio_ffmpeg
from playwright.async_api import async_playwright

URL = "http://127.0.0.1:8000/"
W, H, FPS = 1920, 1080, 30
OUT = os.path.join(os.path.dirname(__file__), "..", "media", "trading-ai-demo.mp4")

# Injected into the page: a visible cursor, a caption bar, and intro/outro cards
OVERLAY_JS = """
(() => {
  const css = document.createElement('style');
  css.textContent = `
    #fake-cursor { position: fixed; z-index: 9999; width: 22px; height: 22px; margin: -11px 0 0 -11px;
      border-radius: 50%; background: rgba(255,255,255,.9); box-shadow: 0 0 0 6px rgba(109,124,255,.35);
      pointer-events: none; transition: transform .12s; left: -50px; top: -50px; }
    #fake-cursor.down { transform: scale(.7); }
    #caption { position: fixed; z-index: 9998; left: 50%; bottom: 48px; transform: translate(-50%, 20px);
      padding: 16px 28px; border-radius: 16px; font: 600 26px Inter, sans-serif; color: #fff;
      background: rgba(17,22,31,.92); border: 1px solid #2a3344; box-shadow: 0 20px 60px rgba(0,0,0,.5);
      opacity: 0; transition: all .4s ease; white-space: nowrap; }
    #caption.show { opacity: 1; transform: translate(-50%, 0); }
    #card { position: fixed; inset: 0; z-index: 10000; display: grid; place-items: center; text-align: center;
      background: radial-gradient(900px 500px at 50% 40%, #1a2040, #0a0d14 70%); color: #fff;
      font-family: Inter, sans-serif; transition: opacity .7s ease; }
    #card.hide { opacity: 0; pointer-events: none; }
    #card .logo { width: 96px; height: 96px; border-radius: 28px; margin: 0 auto 32px; display: grid; place-items: center;
      background: linear-gradient(135deg, #6d7cff, #3fc1ff); box-shadow: 0 20px 60px rgba(109,124,255,.45); }
    #card h1 { font-size: 84px; font-weight: 800; letter-spacing: -0.03em; margin: 0; }
    #card h1 span { background: linear-gradient(90deg,#6d7cff,#3fc1ff); -webkit-background-clip: text; color: transparent; }
    #card p { font-size: 30px; color: #a3abbd; margin: 20px 0 0; }
    #card .stack { margin-top: 40px; display: flex; gap: 14px; justify-content: center; }
    #card .stack b { font-size: 22px; font-weight: 600; padding: 10px 20px; border-radius: 999px;
      background: rgba(109,124,255,.14); color: #c3c9ff; }
    #card small { display: block; margin-top: 36px; font-size: 18px; color: #5b6478; }
  `;
  document.head.appendChild(css);

  const cursor = Object.assign(document.createElement('div'), { id: 'fake-cursor' });
  const caption = Object.assign(document.createElement('div'), { id: 'caption' });
  const card = Object.assign(document.createElement('div'), { id: 'card', className: 'hide' });
  document.body.append(cursor, caption, card);

  addEventListener('mousemove', e => { cursor.style.left = e.clientX + 'px'; cursor.style.top = e.clientY + 'px'; });
  addEventListener('mousedown', () => cursor.classList.add('down'));
  addEventListener('mouseup', () => cursor.classList.remove('down'));

  const logo = '<div class="logo"><svg width="52" height="52" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 17 9 11 13 15 21 7"/><polyline points="15 7 21 7 21 13"/></svg></div>';
  window.demo = {
    caption(text) {
      caption.classList.remove('show');
      setTimeout(() => { caption.textContent = text; if (text) caption.classList.add('show'); }, text ? 250 : 0);
    },
    card(html) { card.innerHTML = logo + html; card.classList.remove('hide'); },
    hideCard() { card.classList.add('hide'); },
  };
})();
"""

INTRO = """
  <h1>Trading <span>AI</span></h1>
  <p>An AI-powered trading dashboard I built for NSE stocks</p>
  <div class="stack"><b>LightGBM</b><b>PyTorch LSTM</b><b>Optuna</b><b>FastAPI</b></div>
"""
OUTRO = """
  <h1>Trading <span>AI</span></h1>
  <p>Features &rarr; 5 competing models &rarr; walk-forward validation &rarr; backtest</p>
  <div class="stack"><b>Python</b><b>LightGBM</b><b>PyTorch</b><b>Optuna</b><b>FastAPI</b><b>Fyers API</b></div>
  <small>Educational project &mdash; not financial advice</small>
"""


async def main():
    frames = []   # (timestamp in seconds, jpeg bytes)

    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome", headless=True)
        page = await browser.new_page(viewport={"width": W, "height": H})
        await page.goto(URL, wait_until="networkidle")
        await page.wait_for_function("document.getElementById('lastPrice').textContent.includes('₹')")
        await page.evaluate(OVERLAY_JS)
        await page.evaluate("html => demo.card(html)", INTRO)
        await page.wait_for_timeout(800)

        # Start streaming screenshots
        cdp = await page.context.new_cdp_session(page)

        def on_frame(params):
            frames.append((params["metadata"]["timestamp"], base64.b64decode(params["data"])))
            asyncio.ensure_future(cdp.send("Page.screencastFrameAck", {"sessionId": params["sessionId"]}))

        cdp.on("Page.screencastFrame", on_frame)
        await cdp.send("Page.startScreencast", {"format": "jpeg", "quality": 92, "maxWidth": W, "maxHeight": H})

        mouse = page.mouse
        wait = page.wait_for_timeout
        caption = lambda t: page.evaluate("t => demo.caption(t)", t)

        async def center(selector):
            box = await page.locator(selector).first.bounding_box()
            return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2

        async def click(selector):
            x, y = await center(selector)
            await mouse.move(x, y, steps=25)
            await wait(250)
            await mouse.down(); await wait(90); await mouse.up()
            await page.locator(selector).first.click()

        # --- Scene 1: intro card ---
        await mouse.move(W / 2, H / 2)
        await wait(2600)
        await page.evaluate("demo.hideCard()")
        await wait(900)

        # --- Scene 2: hover across the chart ---
        await caption("Live 5-minute candles · moving averages · buy/sell signals")
        box = await page.locator("#chart").bounding_box()
        y = box["y"] + box["height"] * 0.45
        await mouse.move(box["x"] + 60, y, steps=20)
        await mouse.move(box["x"] + box["width"] - 90, y - 40, steps=110)
        await wait(600)

        # --- Scene 3: switch stocks ---
        await caption("Switch between stocks instantly")
        for name in ["TCS", "INFY", "RELIANCE"]:
            await click(f"#symbols button:text-is('{name}')")
            await wait(1300)

        # --- Scene 4: train the model ---
        await caption("One click: Optuna tunes LightGBM, an LSTM trains, 5 models compete")
        await click("#trainBtn")
        await page.wait_for_selector("#toast:not([hidden])", timeout=300_000)
        await wait(2400)

        # --- Scene 5: prediction + honest accuracy ---
        await caption("The AI predicts the next candle — and shows how accurate it really is")
        await mouse.move(*(await center("#aiPrediction")), steps=30)
        await wait(1300)
        await mouse.move(*(await center("#accuracy")), steps=30)
        await wait(1600)

        # --- Scene 6: backtest ---
        await caption("Backtested on unseen data — AI vs rules vs buy & hold, with costs")
        await page.evaluate("document.getElementById('equityChart').scrollIntoView({ behavior: 'smooth', block: 'center' })")
        await wait(1200)
        box = await page.locator("#equityChart").bounding_box()
        await mouse.move(box["x"] + 40, box["y"] + box["height"] / 2, steps=15)
        await mouse.move(box["x"] + box["width"] - 60, box["y"] + box["height"] / 2, steps=90)
        await wait(800)

        # --- Scene 7: model lab ---
        await caption("Walk-forward validation, confusion matrix, Optuna results")
        await page.evaluate("document.getElementById('modelsBody').scrollIntoView({ behavior: 'smooth', block: 'center' })")
        await wait(1400)
        await mouse.move(*(await center("#modelsBody tr.best")), steps=30)
        await wait(2400)

        # --- Scene 8: outro card ---
        await caption("")
        await page.evaluate("html => demo.card(html)", OUTRO)
        await wait(3200)

        await cdp.send("Page.stopScreencast")
        await browser.close()

    write_video(frames)


def write_video(frames):
    """Turn the screenshots (taken at uneven times) into a smooth 30 fps MP4."""
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    frames.sort(key=lambda f: f[0])
    start, end = frames[0][0], frames[-1][0]

    ffmpeg = subprocess.Popen(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error",
         "-f", "image2pipe", "-framerate", str(FPS), "-vcodec", "mjpeg", "-i", "-",
         "-vf", f"scale={W}:{H}", "-c:v", "libx264", "-pix_fmt", "yuv420p",
         "-crf", "18", "-preset", "slow", "-movflags", "+faststart", OUT],
        stdin=subprocess.PIPE,
    )
    i = 0
    for n in range(int((end - start) * FPS) + 1):
        t = start + n / FPS
        while i + 1 < len(frames) and frames[i + 1][0] <= t:
            i += 1
        ffmpeg.stdin.write(frames[i][1])   # repeat the latest screenshot for this moment
    ffmpeg.stdin.close()
    ffmpeg.wait()
    print(f"Saved {os.path.abspath(OUT)}  ({end - start:.1f} s, {len(frames)} screenshots)")


if __name__ == "__main__":
    asyncio.run(main())
