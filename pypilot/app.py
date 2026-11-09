from __future__ import annotations
import argparse
import asyncio
import multiprocessing
import os
import shutil
import socket
import sys
import threading
import time


def main():
    multiprocessing.freeze_support()
    if "--diagnostics" in sys.argv:
        import certifi
        import httpx
        import traceback
        print("Python:", sys.version)
        print("CA bundle:", certifi.where(), "exists:", os.path.isfile(certifi.where()))
        try:
            with httpx.Client() as client:
                print("HTTP client / TLS initialization: OK")
        except Exception:
            traceback.print_exc()
        return
    if "--mcp-demo" in sys.argv:
        from .sample_mcp import main as mcp_main
        mcp_main()
        return
    parser = argparse.ArgumentParser(description="PyPilot desktop / headless backend")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--workspace")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--token", help="headless local API token (use an environment variable outside demos)")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    from .config import Settings, assets_dir
    from .server import create_app
    import uvicorn
    settings = Settings()
    workspace = args.workspace or settings.values.get("workspace")
    if not workspace or not os.path.isdir(workspace):
        demo = settings.root / "demo-project"
        if not demo.exists():
            shutil.copytree(assets_dir() / "demo_project", demo)
        workspace = str(demo)
    settings.update({"workspace": workspace})
    token = args.token or os.environ.get("PYPILOT_SESSION_TOKEN")
    app = create_app(settings, workspace, token)
    # Prebind an ephemeral loopback socket; no port-race and no LAN exposure.
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", args.port))
    port = sock.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", log_config=None, access_log=False, loop="asyncio")
    server = uvicorn.Server(config)
    if args.headless:
        print(f"PyPilot backend: {url}", flush=True)
        print(f"Session token: {app.state.token}", flush=True)
        server.run(sockets=[sock])
        return
    import webview
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)

    class DesktopAPI:
        def choose_folder(self):
            chosen = window.create_file_dialog(webview.FileDialog.FOLDER)
            return chosen[0] if chosen else None

        def save_text(self, content, filename):
            chosen = window.create_file_dialog(webview.FileDialog.SAVE, save_filename=filename, file_types=("Markdown (*.md)",))
            if chosen:
                from pathlib import Path
                target = chosen if isinstance(chosen, str) else chosen[0]
                Path(target).write_text(content, "utf-8")
                return target
            return None

    window = webview.create_window("PyPilot · Python 编程工作台", url, width=1440, height=920, min_size=(1060, 680), js_api=DesktopAPI(), background_color="#111419")
    def closed():
        server.should_exit = True
    window.events.closed += closed
    try:
        webview.start(debug=args.debug, gui="edgechromium" if sys.platform == "win32" else None, private_mode=False, storage_path=str(settings.root / "webview"))
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        sock.close()


if __name__ == "__main__":
    main()

