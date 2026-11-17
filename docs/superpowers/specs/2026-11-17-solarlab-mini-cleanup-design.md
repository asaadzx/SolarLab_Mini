# SolarLab Mini code and documentation cleanup design

## Context

The active implementation is the MicroPython firmware in `firmware/` plus the Flask
dashboard in `laptop_app/dashboard/`. The repository also contains earlier PlatformIO
Arduino experiments (`src/`, `include/`, `firmware_pio/`, `test_wifi/`, root
`platformio.ini`) which remain for reference.

Recent hardware bring-up established the verified wiring: OLED on I2C0 with
SDA=GPIO23/SCL=GPIO21 at `0x3C`, INA219 on I2C1 with SDA=GPIO19/SCL=GPIO18 at `0x40`,
AP `SolarLab-Mini` / `solarlab123`, JSON endpoint `http://192.168.4.1/data`.
`README.md` and `docs/wiring.md` still describe the old, incorrect pins.

A real driver bug was found and fixed: `INA219.get_current()` divided the shunt
voltage twice, so 1 A read as 1 mA. The fix is deployed to the board and covered by
`tests/test_ina219.py`. All 25 host tests pass.

The Flask dashboard works when tested locally with a stub sensor response: `/`
returns 200 and `/api/latest` returns the expected JSON. It cannot be tested from
this machine against the live board because connecting the laptop to the ESP32 AP
would disconnect the AI session.

## Goals

1. Make the current code self-explanatory with concise comments and docstrings.
2. Correct and organize the documentation so it matches the verified hardware.
3. Add host-side test coverage for the dashboard proxy route.
4. Harden the webserver enough that a slow client cannot stall the sensor loop.
5. Commit the work and push it to `origin/master`.

## Non-goals

- No new features, UI redesign, or change to the JSON schema (`voltage`, `current`,
  `power`, `timestamp`).
- No deletion or restructuring of the legacy PlatformIO directories.
- No behavior change to sensor sampling, AP configuration, or OLED content.
- No changes to `deploy.py` beyond comments.

## Design

### Firmware and app code

- Add short module-level explanations and function docstrings to `firmware/config.py`,
  `firmware/boot.py`, `firmware/main.py`, `firmware/wifi_ap.py`,
  `firmware/webserver.py`, `firmware/drivers/ina219.py`,
  `firmware/drivers/ssd1306.py`, `deploy.py`, `laptop_app/receiver_http.py`, and
  `laptop_app/dashboard/app.py`.
- Document why the two I2C buses are separate, why peripheral initialization is
  non-fatal, and the current/shunt scaling math in the INA219 driver.
- In `firmware/webserver.py`, keep the public API and `handle_once()` signature, but
  set a timeout on accepted sockets and use `sendall()` instead of `send()`. This
  prevents a stalled client from blocking the one-shot loop.

### Documentation

- Rewrite `README.md` around the working MicroPython path: verified pins, AP details,
  deploy commands, dashboard commands, tests, and a short note that the PlatformIO
  folders are older experiments.
- Rewrite `docs/wiring.md` with three separated sections: power loop (panel + → fuse →
  VIN+ → VIN− → load → panel −), common-ground node (panel −, load −, INA219 GND,
  ESP32 GND), and I2C signal wiring. Include battery/charge-controller guidance,
  panel voltage/current limits, and the fact that a motor directly on the panel
  collapses the voltage.
- Add `docs/superpowers/specs/2026-11-17-solarlab-mini-cleanup-design.md` (this file)
  to follow the existing project convention.

### Tests

- Keep `tests/test_ina219.py` (register scaling, positive/negative current, power).
- Add `tests/test_dashboard.py` that starts a local stub HTTP server, points the Flask
  app's `ESP_URL` at it, and checks `/` and `/api/latest` with Flask's test client.
  Use `pytest.importorskip("flask")` so the suite still runs if Flask is absent.

### Git

- Commit the changes with conventional-style messages consistent with the existing
  history (for example `docs: ...`, `test: ...`, `refactor: ...`).
- Push `master` to `origin/master`. Do not open a pull request.

## Verification

- `python -m pytest tests/ -q` — all tests must pass.
- Confirm `/data` remains a plain JSON response and the dashboard route still proxies
  it, using the local stub test.
- Confirm `git status` is clean after the push and no build artifacts or cache files
  are added.

## Risks

- Comments must not alter behavior on the board; only the webserver socket handling
  changes functionally, and its response stays byte-for-byte the same.
- The live AP cannot be exercised from this machine without disconnecting the AI
  session, so live `/data` verification remains with the user's phone.
