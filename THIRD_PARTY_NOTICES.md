# Third-party notices

PyPilot's application code is MIT licensed. This is an independent teaching
project, not affiliated with Cursor, VS Code, OpenAI, or the reference projects.

Bundled dependencies retain their own licenses:

| Component | Version | License / upstream |
| --- | --- | --- |
| Monaco Editor | 0.52.2 | MIT · https://github.com/microsoft/monaco-editor |
| CPython embedded runtime | 3.12.10 | PSF License · https://www.python.org/ |
| pip in embedded Python | 25.1.1 | MIT · https://github.com/pypa/pip |
| pywebview | 6.2.1 | BSD-3-Clause · https://github.com/r0x0r/pywebview |
| FastAPI | 0.162.2 | MIT · https://github.com/fastapi/fastapi |
| Uvicorn | 0.54.0 | BSD-3-Clause · https://github.com/encode/uvicorn |
| HTTPX | 0.28.1 | BSD-3-Clause · https://github.com/encode/httpx |
| MCP Python SDK | 1.30.0 | MIT · https://github.com/modelcontextprotocol/python-sdk |
| Pillow | 13.0.0 | HPND · https://github.com/python-pillow/Pillow |
| PyInstaller | 6.22.3 | GPL with bootloader distribution exception · https://pyinstaller.org/ |

Monaco's license is in `ui/vendor`; Python's license is in `runtime/python`.
The build includes installed Python dependency metadata and license files under
`_internal/*.dist-info`. PyInstaller's bootloader exception permits redistribution
of the frozen application under the application's own license. WebView2 is
provided by Microsoft under its own runtime terms. Inno Setup compiles the
installer; it is a build tool and is not included as an application dependency.

Architectural references (no source copied into the implementation):
Cline's tool review loop and Aider's repository map approach.
Refer to `docs/references.md` for verified repository
links and the scope of those references.
