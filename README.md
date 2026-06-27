# HMI — Robust, Scalable PyQt6 Application Template

A starting point for building **HMI-style PyQt6 applications** (industrial
panels, control dashboards, instrument front-ends) that must run for a long
time without crashing. It bakes in the patterns that are tedious to retrofit
later: centralised fault handling, crash-proof slots, off-GUI-thread I/O, a
connection state machine, an alarm engine, and a layered structure that scales
from a 3-screen demo to a large plant HMI.

Built with **PyQt6** and managed with **[uv](https://docs.astral.sh/uv/)**.

> 📖 **Full architecture guide:** [`docs/architecture.html`](docs/architecture.html) — a
> self-contained, offline HTML document with diagrams and annotated code examples explaining the
> design and the rationale behind every choice. Open it in any browser.

---

## Quick start

```bash
uv sync                      # install deps (incl. dev group)
uv run hmi                   # launch the app
uv run python -m hmi         # equivalent

uv run pytest                # run the test suite
```

Headless (CI / over SSH): set `QT_QPA_PLATFORM=offscreen`.

Configuration is optional. Copy `config.example.json` to `config.json` to
override defaults, or set `HMI_*` environment variables (e.g.
`HMI_DEVICE_POLL_INTERVAL_MS=250`).

---

## Why this template (the robustness story)

A default PyQt app has three silent ways to die or mislead you on a 24/7 panel:

1. **An exception in a slot aborts the process.** Since PyQt 5.5 an unhandled
   exception in a slot calls `sys.excepthook` and then *aborts*. One bad button
   handler takes down the whole HMI.
2. **Worker-thread errors vanish.** `threading.excepthook` just prints to
   stderr — invisible on a kiosk.
3. **Qt's own C++ warnings bypass Python logging**, so you never see them in
   your log file.

This template closes all three:

- **`@safe_slot`** ([`core/safe_slot.py`](src/hmi/core/safe_slot.py)) wraps any
  slot so exceptions are reported and swallowed — the event loop keeps running.
- **Global hooks** ([`core/fault.py`](src/hmi/core/fault.py)) capture exceptions
  from the event loop, plain threads, and Qt's C++ message handler, funnelling
  them all into one `Fault` broadcast on the GUI thread via the `FaultBus`.
- **All device I/O runs off the GUI thread** ([`core/worker.py`](src/hmi/core/worker.py))
  with a safe `start → stop → quit → wait` lifecycle, so the UI never freezes
  and threads never leak or get destroyed mid-run.

---

## Architecture

Strictly layered, with dependencies pointing **inward** toward `core`. Data
flows in one direction: **device → service → tag store → signal bus → views**.

```
        ┌──────────────────────────────────────────────┐
        │                    views/                     │  Qt widgets, pages,
        │  MainWindow · Navigator · pages/ · widgets/    │  navigation, dialogs
        └──────────────────────────────────────────────┘
                 │ observes (signal bus)        ▲ navigation requests
                 ▼                              │
        ┌──────────────────────────────────────────────┐
        │           alarms/    ·    models/             │  alarm engine,
        │        AlarmManager      TagStore / Tag        │  process data
        └──────────────────────────────────────────────┘
                 ▲ tag updates
                 │
        ┌──────────────────────────────────────────────┐
        │                  services/                    │  threaded I/O,
        │      Service (state machine) · DeviceService   │  connection lifecycle
        └──────────────────────────────────────────────┘
                 │ depends on
                 ▼
        ┌──────────────────────────────────────────────┐
        │                     core/                     │  fault handling,
        │  fault · safe_slot · worker · signals ·        │  safe slots, threads,
        │  settings · logging · exceptions               │  config, app event bus
        └──────────────────────────────────────────────┘
```

Components never reference each other directly across layers; they communicate
through the **`SignalBus`** ([`core/signals.py`](src/hmi/core/signals.py)). This
is what keeps the dependency graph manageable as the app grows. The single
composition root, [`app.py`](src/hmi/app.py), is the only place that knows the
concrete set of services and pages and wires them together.

### Layout

```
src/hmi/
├── app.py                  # composition root — wires everything together
├── __main__.py             # `python -m hmi`
├── core/                   # stable foundation (no upward imports)
│   ├── exceptions.py       # AppError hierarchy w/ severity + recoverability
│   ├── fault.py            # Fault, FaultBus, global excepthooks, Qt handler
│   ├── safe_slot.py        # @safe_slot decorator
│   ├── worker.py           # Worker / PeriodicWorker / WorkerThread
│   ├── signals.py          # SignalBus (app-wide event bus)
│   ├── settings.py         # AppConfig: defaults < JSON < env, validated
│   └── logging_config.py   # console + rotating file logging
├── models/tag.py           # Tag, Quality, TagStore (single source of truth)
├── services/
│   ├── base.py             # Service base + ConnectionState machine
│   └── device_service.py   # example simulated PLC poller
├── alarms/manager.py       # high/low limit alarm engine
├── views/
│   ├── main_window.py      # shell: side-nav + pages + status bar
│   ├── navigation.py       # Navigator (router over QStackedWidget)
│   ├── base_page.py        # BasePage w/ on_show / on_hide lifecycle
│   ├── pages/              # Dashboard, Alarms, Settings, Control (MVVM)
│   ├── viewmodels/         # OPTIONAL MVVM layer (see below)
│   └── widgets/            # StatusIndicator, FaultNotifier
└── resources/styles/       # dark.qss theme
tests/                      # pytest-qt: safe_slot, worker, settings, viewmodel
```

---

## How to extend it

**Add a screen** — subclass `BasePage`, set `page_title`/`page_key`, build your
UI in `build_ui()`, and register it with one line in `app.py`:
`self.window.add_page(MyPage(...))`.

**Add a real device** — subclass `Service` and provide a worker (usually a
`PeriodicWorker`). In its `step()`, call your driver (Modbus/OPC-UA/serial) and
raise `DeviceError` on failure; the base class handles threading, and the
connect/degrade/fault state machine comes for free. Publish readings with
`store.update(name, value)`.

**Add an alarm** — give a `Tag` a `high_limit`/`low_limit` when you define it in
`app.py`. The `AlarmManager` evaluates updates automatically and broadcasts
`alarmRaised` / `alarmCleared`.

**Write a crash-proof slot** — decorate every method you connect to a signal
with `@safe_slot`. Combine with `@pyqtSlot` (outermost) if you want the typed
C++ slot too.

**React to app-wide events** — emit/connect on `bus()` from
[`core/signals.py`](src/hmi/core/signals.py) rather than threading references
through constructors.

---

## Optional: MVVM, where it earns its place

This template is **not** MVVM by default — most HMI screens are thin read-outs
(`set_value(...)`) with no logic worth isolating, so the simple pages bind to
the model directly through the signal bus. But screens with real presentation
logic — **commands, validation, preconditions, derived state, permission-based
enabling** — benefit from a ViewModel that holds that logic *out of the widget*
so it can be unit-tested without any UI.

The [`views/viewmodels/`](src/hmi/views/viewmodels) package demonstrates this
with one realistic example — a pump-control screen:

- [`pump_control.py`](src/hmi/views/viewmodels/pump_control.py) — the
  ViewModel: bindable `pyqtProperty` state (`can_start`, `status_text`),
  `pyqtSlot` commands (`start`/`stop`), precondition checks (device connected,
  value fresh, tank below its high limit), and explicit rejection feedback. It
  holds **no reference to its view**.
- [`control_page.py`](src/hmi/views/pages/control_page.py) — the View: renders
  VM state and forwards clicks. The [`bind()`](src/hmi/views/viewmodels/base.py)
  helper reduces widget MVVM's signature cost (manual binding) to one line per
  field.
- [`tests/test_viewmodel.py`](tests/test_viewmodel.py) — exercises all the
  command logic **with no widgets instantiated**. That testability is the
  payoff.

**It's opt-in.** The Control page is registered only when
`enable_control_demo` is true (the default). Set it to `false` — or delete the
`viewmodels/` package and `control_page.py` — to drop MVVM entirely. Use the
example as the template for your own control screens; leave the read-out pages
binding directly. MVVM and the event bus are complementary: the bus is *how*
the VM receives model updates.

---

## See the fault pipeline live

Run the app and open **Settings → "Trigger test fault"**: a `DeviceError` is
raised inside a slot. Instead of crashing, it's logged, shown briefly in the
status bar, and the app keeps running. The simulated device also drops its
"connection" at `device.failure_rate`, so you can watch the status indicator
move through *connected → degraded → faulted → connected* and the tags go
stale and recover.

---

## Testing

`pytest-qt` drives a real Qt event loop. The suite covers the load-bearing
infrastructure — the safe-slot guard, the worker lifecycle (including a failing
worker and clean stop), and config layering/validation. Run headless with
`QT_QPA_PLATFORM=offscreen uv run pytest`.
