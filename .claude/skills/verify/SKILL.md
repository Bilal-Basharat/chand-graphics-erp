---
name: verify
description: Build, launch and drive the Chand Graphics ERP desktop app (PySide6) against an isolated copy of the database, capture screenshots, and render generated PDFs for inspection.
---

# Verifying this app

PySide6 6.11 desktop app, Python 3.14, SQLite. `./.venv/Scripts/python.exe` is
the interpreter — there is no `python` on PATH that has PySide6.

## Never run against `data/erp.db`

That is the user's real development database. A GUI driver that boots the
app without `ERP_DATA_DIR` set **will write to it** — creating sales,
consuming stock, cancelling jobs. Always:

```bash
mkdir -p "$SCRATCH/erpdata"
cp data/erp.db data/session.json data/sign_in.json "$SCRATCH/erpdata/"
export ERP_DATA_DIR="$SCRATCH/erpdata"
```

`session.json` is `{"user_id": 1}` — copying it is what makes the app open
signed in, so no password is needed. `data/erp.v*.backup` are snapshots of
the real database, not fixtures.

## Driving it

There is no CLI and no server. The surface is the window, so a driver
script builds the shell the way `app/bootstrap.py` does and pumps the event
loop by hand:

```python
from app.bootstrap import configure_application, configure_locale
configure_locale(); load_dotenv(ENV_FILE); init_db()
container = AppContainer(); container.create_initializer().initialize()
app = QApplication(sys.argv); configure_application(app)
window = MainWindow(container, SessionViewModel(container)); window.show()
```

`configure_application` exists for exactly this — call it, or the harness
sees un-themed defaults and "finds" problems the real app does not have.

- **Pump, don't `app.exec()`**: `while time.monotonic() < end: app.processEvents(); time.sleep(0.01)`.
  Every screen loads through `run_async` on a QThreadPool, so allow ~2s
  after `window.navigate(route)` before asserting anything.
- **Screenshots**: `widget.grab().save(path)`. Grabs come out at the
  display's device pixel ratio (1.25x here), so measure in the image, not
  in logical pixels.
- **Row buttons** are painted by `RowActionsDelegate`, not real widgets.
  Click them through the delegate's own geometry — never guess an offset,
  and never assume the button you want is the rightmost:

  ```python
  delegate = table.itemDelegateForColumn(table.model().columnCount() - 1)
  point = delegate._button_rects(table.visualRect(index))[0].center()  # [0] = first action
  QTest.mouseClick(table.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point)
  ```

  Getting this wrong on the job list lands on **Cancel**, which is a real
  destructive use case.
- **Modal dialogs** block the driver inside `exec()`. Schedule the work
  that inspects them first: `QTimer.singleShot(900, handler)`, then click.
  `QApplication.activeModalWidget()` is the dialog.

## Record cards, PDF and print

`dialogs/record_card_dialog.py` renders a card; `records/paper.py` puts it
on A4. To drive Save-as-PDF and Print without a file chooser or a spooler,
stub only the *user's choice*:

```python
QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (path, "PDF document (*.pdf)"))
QMessageBox.information = staticmethod(lambda *a, **k: None)

def _fake_print_exec(self):                       # QPrintDialog
    self.printer().setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    self.printer().setOutputFileName(path)
    return QDialog.DialogCode.Accepted
QPrintDialog.exec = _fake_print_exec
```

Everything after the dialog is then the real path. **Look at the output** —
render it back to an image:

```python
d = QPdfDocument(); d.load(pdf); d.render(0, QSize(900, 1273)).save(png)
```

Gotcha the page layout already works around: Qt's rich-text engine lays out
`<hr>` and then draws nothing. Rules on the page are a 1pt table row with a
background colour. Per-cell `border-bottom` does work.

## Things that are not verification

Don't run `pytest` — the 26 tests are backend-only and prove nothing about
a screen. Don't import a view model and call it; the bugs live in the
wiring between the view, the delegate and the stylesheet.
