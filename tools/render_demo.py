"""Capture the real frontend with synthetic data; no backend or HPC connection."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import mimetypes
import platform
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.metadata import version
from pathlib import Path
from threading import Thread
from urllib.parse import urlsplit

from demo_fixture import presentation_data
from PIL import Image, ImageColor, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src/hpc_forest/webapp/static"
SIZE = (1440, 1130)
ACCENT = "#b9df75"
CHAPTERS = ["Explorer", "Vérifier", "Comprendre", "Livrer"]


class StaticHandler(BaseHTTPRequestHandler):
    """Expose only the frontend files, never the repository or a live API."""

    def do_GET(self):
        files = {"/assets/" + path.name: path for path in STATIC.iterdir() if path.is_file()}
        files["/"] = STATIC / "index.html"
        path = files.get(urlsplit(self.path).path)
        if path is None:
            self.send_error(404)
            return
        content = path.read_bytes()
        media = "text/javascript" if path.suffix in {".mjs", ".js"} else mimetypes.guess_type(path)[0]
        self.send_response(200)
        self.send_header("Content-Type", (media or "application/octet-stream") + "; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, *_args):
        pass


def font(size: int, bold=False):
    names = [
        Path("C:/Windows/Fonts") / ("segoeuib.ttf" if bold else "segoeui.ttf"),
        Path("/usr/share/fonts/truetype/dejavu") / ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"),
        Path("/System/Library/Fonts/Supplemental") / ("Arial Bold.ttf" if bold else "Arial.ttf"),
    ]
    for path in names:
        if path.is_file():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default(size=size)


def compose(screenshot: bytes, chapter: int, title: str, subtitle: str) -> Image.Image:
    canvas = Image.new("RGB", SIZE, "#101614")
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((36, 29, 76, 69), radius=11, fill=ACCENT)
    draw.text((47, 30), "F", font=font(26, True), fill="#101614")
    draw.text((89, 31), "FOREST", font=font(24, True), fill="#edf1e9")
    draw.text((217, 39), "/  APERÇU PRODUIT", font=font(13), fill="#99aa9e")
    draw.rounded_rectangle((1060, 32, 1404, 65), radius=16, outline="#40533c", fill="#1a271c")
    draw.text((1080, 37), "DÉMONSTRATION · DONNÉES SYNTHÉTIQUES", font=font(12, True), fill=ACCENT)
    draw.text((36, 86), title, font=font(30, True), fill="#edf1e9")
    draw.text((36, 131), subtitle, font=font(16), fill="#a8b9ad")
    draw.rounded_rectangle((35, 173, 1405, 1069), radius=12, fill="#1b1c1d", outline="#3b463e")
    shot = Image.open(io.BytesIO(screenshot)).convert("RGB")
    shot = shot.resize((1368, 890), Image.Resampling.LANCZOS)
    mask = Image.new("L", shot.size)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, 1367, 889), radius=10, fill=255)
    canvas.paste(shot, (36, 177), mask)
    for index, label in enumerate(CHAPTERS):
        x = 36 + index * 220
        active = index == chapter
        draw.ellipse((x, 1094, x + 8, 1102), fill=ACCENT if active else "#455248")
        draw.text((x + 18, 1085), f"0{index + 1}  {label}", font=font(16, active),
                  fill="#edf1e9" if active else "#8b9c90")
    draw.text((1054, 1090), "Interface réelle · aucun calcul ROMEO", font=font(13), fill="#8b9c90")
    return canvas


def capture(browser_path: str | None, frames_dir: Path | None = None):
    data = presentation_data()
    frames, problems = [], []
    server = ThreadingHTTPServer(("127.0.0.1", 0), StaticHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, executable_path=browser_path)
            browser_version = browser.version
            context = browser.new_context(viewport={"width": 1536, "height": 1000},
                                          device_scale_factor=1, locale="fr-FR",
                                          timezone_id="Europe/Paris", reduced_motion="reduce")

            def route_request(route):
                request = route.request
                address = urlsplit(request.url)
                if request.method != "GET" or not request.url.startswith(origin + "/"):
                    problems.append("Blocked request: " + address.path)
                    route.abort()
                elif address.path.startswith("/api/"):
                    if address.path not in data:
                        problems.append("Missing presentation fixture: " + address.path)
                    route.fulfill(status=200 if address.path in data else 404,
                                  json=data.get(address.path, {"error": "No fixture"}))
                else:
                    route.continue_()

            context.route("**/*", route_request)
            page = context.new_page()
            page.on("pageerror", lambda error: problems.append(str(error)))
            page.on("console", lambda message: problems.append(message.text) if message.type == "error" else None)
            page.add_init_script("localStorage.clear(); localStorage.setItem('forest.theme','dark');")

            def snapshot(chapter, title, subtitle, duration):
                page.evaluate("document.fonts.ready")
                image = compose(page.screenshot(animations="disabled"), chapter, title, subtitle)
                frames.append((image, duration))
                if frames_dir:
                    frames_dir.mkdir(parents=True, exist_ok=True)
                    image.save(frames_dir / f"scene-{len(frames):02}.png")
                print(f"Captured scene {len(frames)}: {title}", flush=True)

            page.goto(origin + "/#/mission/campaign/presentation")
            page.get_by_role("heading", name="Arbres de recherche").wait_for()
            page.locator(".tree").nth(2).wait_for()
            snapshot(0, "Plusieurs pistes. Une recherche traçable.",
                     "Parcourez les arbres et retrouvez chaque variante, son état et ses mesures.", 4200)

            page.locator('[data-node="T1-04"] .node-circle').click()
            panel = page.locator("#trial-panel")
            panel.get_by_text("Correction vérifiée", exact=True).wait_for()
            panel.scroll_into_view_if_needed()
            snapshot(1, "La correction avant la performance.",
                     "Inspectez les tests et les preuves attachées à la variante sélectionnée.", 2500)

            panel.get_by_role("tab", name="Mesures", exact=True).click()
            panel.locator(".samples").wait_for()
            snapshot(1, "Chaque essai conserve ses mesures.",
                     "Comparez les échantillons ; la confirmation finale reste une étape distincte.", 2800)

            panel.get_by_role("tab", name="Diff / référence", exact=True).click()
            panel.locator(".source-code").filter(has_text="reduction").wait_for()
            panel.scroll_into_view_if_needed()
            snapshot(2, "Comprenez ce qui a changé.",
                     "Lisez les sources et le diff par rapport à la référence, depuis la même interface.", 3800)

            page.locator('.sidebar a[href="#/results"]').click()
            page.get_by_role("heading", name="Votre résultat").wait_for()
            page.evaluate("window.scrollTo(0,0)")
            snapshot(3, "Un résultat confirmé, dans son contexte.",
                     "Visualisez les temps comparés et distinguez les essais corrects, incorrects et sans verdict.", 3500)
            page.get_by_role("link", name="Télécharger le projet", exact=True).scroll_into_view_if_needed()
            snapshot(3, "Du code retenu aux preuves de campagne.",
                     "Retrouvez le projet, le rapport et les mesures, avec les conditions de comparaison.", 3500)
            context.close()
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    if problems:
        raise RuntimeError("Capture failed: " + "; ".join(problems))
    return frames, browser_version


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "docs/media")
    parser.add_argument("--browser", help="Optional path to an installed Chromium executable")
    parser.add_argument("--frames", type=Path, help="Optional directory for individual scene previews")
    args = parser.parse_args()
    scenes, browser_version = capture(args.browser, args.frames)
    args.output.mkdir(parents=True, exist_ok=True)
    poster = args.output / "forest-overview.png"
    scenes[0][0].save(poster, optimize=True)

    # A single palette keeps static areas stable between scenes and fades.
    contact = Image.new("RGB", (480 * 3, 377 * 2))
    for index, (frame, _) in enumerate(scenes):
        contact.paste(frame.resize((480, 377)), ((index % 3) * 480, (index // 3) * 377))
    palette = contact.quantize(colors=240)
    # Preserve the fine chalk lines and status colors even when they occupy few pixels.
    ui_colors = ["#b9df75", "#91cef2", "#ebce8d", "#c5a5e9", "#efb5bb", "#a4d2ab",
                 "#e7a7ae", "#a4bdf3", "#4054bb", "#4658b1", "#5f8d68", "#d6d3cd",
                 "#aba69c", "#9bb6ee", "#e2c38b", "#e7e6e3"]
    palette.putpalette(palette.getpalette()[:720] + [v for color in ui_colors for v in ImageColor.getrgb(color)])
    frames, durations = [], []
    for index, (frame, duration) in enumerate(scenes):
        frames.append(frame.quantize(palette=palette, dither=Image.Dither.NONE))
        durations.append(duration)
        following = scenes[(index + 1) % len(scenes)][0]
        for alpha in (.25, .5, .75):
            frames.append(Image.blend(frame, following, alpha).quantize(palette=palette, dither=Image.Dither.NONE))
            durations.append(80)
    animation = args.output / "forest-demo.gif"
    frames[0].save(animation, save_all=True, append_images=frames[1:], duration=durations,
                   loop=0, optimize=True, disposal=1)
    with Image.open(animation) as gif:
        frame_count = gif.n_frames
        actual_duration = 0
        for index in range(frame_count):
            gif.seek(index)
            actual_duration += gif.info["duration"]
        if gif.size != SIZE or actual_duration != sum(durations) or frame_count != len(frames):
            raise RuntimeError("Encoded GIF differs from the captured sequence")
    receipt = {
        "schema": "forest-presentation-v1", "synthetic_data": True,
        "backend_started": False, "hpc_jobs_submitted": 0, "model_calls": 0,
        "browser_errors": [], "viewport": [1536, 1000], "size": list(SIZE),
        "frames": frame_count, "duration_ms": actual_duration,
        "runtime": {"python": platform.python_version(), "playwright": version("playwright"),
                    "pillow": version("Pillow"), "chromium": browser_version},
        "source_hash_normalization": "utf-8-lf",
        "source_sha256": {path.relative_to(ROOT).as_posix(): hashlib.sha256(
                              path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
                          for path in sorted([*STATIC.iterdir(), Path(__file__),
                                              ROOT / "tools/demo_fixture.py"]) if path.is_file()},
        "media": {path.name: {"bytes": path.stat().st_size,
                              "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                  for path in [animation, poster]},
    }
    (args.output / "forest-demo.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "frames": frame_count,
                      "duration_ms": actual_duration, "media": receipt["media"]}, indent=2))


if __name__ == "__main__":
    main()
