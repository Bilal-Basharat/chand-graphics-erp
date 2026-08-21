"""
Builds the single application-wide QSS stylesheet from theme tokens.

Applied once at QApplication level (see bootstrap.py). Widgets opt into
styling via objectName (structural chrome) or the "role"/"variant"/"tone"
dynamic properties (semantic variants) rather than ad-hoc per-widget QSS.

Important QSS gotcha this file exists to avoid repeating: QWidget is the
base class of nearly every widget, including QLabel. A blanket
`background` on the `QWidget` type selector is therefore inherited by
*every* label and plain container in the app, regardless of what panel
it sits inside — the base rule below deliberately leaves `background`
unset (transparent) and only paints it on the specific containers that
should visibly have one (#Header, #Sidebar, #StatusBar, #Content, and
the [role="panel"]/[role="statTile"] cards). Same trap applies to any
call site using widget.setStyleSheet("border: none; ...") on a
container with children — a bare declaration block scopes to the whole
subtree, not just the widget itself. Always use an objectName + a rule
here instead of a local setStyleSheet() when the widget has children.

Second trap, same neighbourhood: a rule here only reaches a plain
`QWidget` subclass if that widget sets `WA_StyledBackground`. Without it
the background is simply not painted and the surface behind shows
through — which is how the navy rail came to render as a hole in the
page. QFrame subclasses paint theirs already; QWidget ones must ask.
"""
from __future__ import annotations

from app.presentation.theme import tokens as t
from app.presentation.theme.assets import checkbox_tick_url, combo_chevron_url


def _chevron_rule() -> str:
    """The combo box's drop-down mark, or nothing if the asset is
    unavailable — better a bare box than a url() pointing at nothing."""
    url = combo_chevron_url()
    if not url:
        return ""
    return (
        "QComboBox::down-arrow {"
        f" image: url({url}); width: 10px; height: 10px; }}"
        "\n    QComboBox::down-arrow:disabled { opacity: 0.4; }"
    )


def _tick_rule() -> str:
    """The checked-checkbox tick, or nothing if the asset is unavailable.

    Styling `QCheckBox::indicator` overrides the style's own painting
    including its tick, so without this a checked box is a bare filled
    square — readable, but not what a checkbox should look like.
    """
    url = checkbox_tick_url()
    return f"image: url({url});" if url else ""


def build_stylesheet() -> str:
    return f"""
    * {{
        font-family: "{t.FONT_FAMILY}";
        outline: none;
    }}

    QWidget {{
        background: transparent;
        color: {t.INK};
        font-size: 13px;
    }}

    /* Top-level windows (dialogs, message boxes, the main window's own
       central widget) paint their own backing store — an unset/transparent
       background on a top-level widget falls back to solid black on
       Windows instead of showing the window behind it. QDialog/QMainWindow
       aren't QLabel's base class, so painting them here doesn't reopen the
       QWidget-cascade problem the base rule above avoids. */
    QDialog, QMainWindow {{
        background: {t.CANVAS};
    }}

    /* ---------------- Structural chrome ---------------- */
    QWidget#Header {{
        background: {t.SURFACE};
        border-bottom: 1px solid {t.LINE};
    }}
    QWidget#Sidebar {{
        background: {t.NAVY};
        border-right: 1px solid {t.NAVY_LINE};
    }}
    QWidget#StatusBar {{
        background: {t.SURFACE};
        border-top: 1px solid {t.LINE};
    }}
    QWidget#Content {{
        background: {t.CANVAS};
    }}
    QLabel#BrandMark {{
        background: {t.NAVY};
        color: white;
        font-weight: {t.WEIGHT_SEMIBOLD};
        font-size: 12px;
        border-radius: 7px;
    }}
    QLabel#BrandName {{
        color: {t.INK};
        font-weight: {t.WEIGHT_SEMIBOLD};
        font-size: 14px;
    }}
    QLabel#BrandSub {{
        color: {t.MUTED};
        font-size: 10px;
    }}

    /* ---------------- Sidebar nav ---------------- */
    /* The rail's scroller is a mechanism, not a surface: it and the rows
       it holds let the navy through rather than painting over it. */
    QScrollArea#SidebarScroll, QWidget#SidebarRows {{
        background: transparent;
        border: none;
    }}
    /* The rail's own scrollbar. The app-wide handle is a light grey made
       for white panels; against navy it reads as a bright stripe down the
       edge of the menu. */
    QScrollArea#SidebarScroll QScrollBar::handle:vertical {{
        background: {t.NAVY_LINE};
    }}
    QScrollArea#SidebarScroll QScrollBar::handle:vertical:hover {{
        background: {t.NAV_GROUP};
    }}
    QLabel[role="navLabel"] {{
        color: {t.NAV_GROUP};
        background: transparent;
        font-size: 10px;
        font-weight: {t.WEIGHT_SEMIBOLD};
        letter-spacing: 0.6px;
    }}
    QPushButton[role="navItem"] {{
        background: transparent;
        color: {t.NAV_IDLE};
        border: none;
        text-align: left;
        padding: 8px 10px;
        border-radius: {t.RADIUS_SM}px;
        font-size: 13px;
        font-weight: {t.WEIGHT_MEDIUM};
    }}
    /* Hover is a lift, not a selection. Painting it the same blue as the
       checked row made every row you passed over look like the one you
       were on. */
    QPushButton[role="navItem"]:hover {{
        background: {t.NAV_HOVER};
        color: {t.NAVY_TEXT};
    }}
    QPushButton[role="navItem"]:checked {{
        background: {t.PRIMARY};
        color: white;
        font-weight: {t.WEIGHT_SEMIBOLD};
    }}
    /* A row inside a folder. Indented past the icon column it does not
       use, so its label starts where the labels above it do. */
    QPushButton[role="navItem"][depth="1"] {{
        padding-left: 33px;
        font-size: 12.5px;
    }}
    /* Collapsed rail: the icon is all that's left, so centre it instead of
       leaving it indented where the text used to start. Last, so it wins
       over the indent above — though a folder's rows are hidden by then
       anyway. */
    QPushButton[role="navItem"][collapsed="true"] {{
        padding: 8px 0px;
        text-align: center;
    }}

    QPushButton[role="sidebarFoot"] {{
        background: transparent;
        color: {t.NAV_IDLE};
        border: none;
        border-top: 1px solid {t.NAVY_LINE};
        border-radius: 0px;
        padding: 11px 22px;
        font-size: 12.5px;
        font-weight: {t.WEIGHT_MEDIUM};
        text-align: left;
    }}
    QPushButton[role="sidebarFoot"][collapsed="true"] {{
        padding: 11px 0px;
        text-align: center;
    }}
    QPushButton[role="sidebarFoot"]:hover {{
        color: {t.NAVY_TEXT};
        background: {t.NAVY_RAISED};
    }}

    /* ---------------- Buttons ---------------- */
    /* Base look matches the "outline" variant, so any button that never
       gets a variant property (e.g. QDialogButtonBox's auto-generated
       Ok/Cancel) still renders as a real, visible button by default. */
    QPushButton {{
        background: {t.SURFACE};
        color: {t.INK};
        border: 1px solid {t.LINE};
        border-radius: {t.RADIUS_SM}px;
        padding: 7px 13px;
        font-size: 13px;
        font-weight: {t.WEIGHT_SEMIBOLD};
    }}
    QPushButton:hover {{
        background: {t.CANVAS};
    }}
    QPushButton[variant="primary"] {{
        background: {t.PRIMARY};
        color: white;
        border-color: {t.PRIMARY};
    }}
    QPushButton[variant="primary"]:hover {{
        background: {t.PRIMARY_HOVER};
        border-color: {t.PRIMARY_HOVER};
    }}
    QPushButton[variant="primary"]:disabled {{
        background: {t.LINE};
        border-color: {t.LINE};
        color: {t.MUTED};
    }}
    QPushButton[variant="outline"] {{
        background: {t.SURFACE};
        color: {t.INK};
        border: 1px solid {t.LINE};
    }}
    QPushButton[variant="outline"]:hover {{
        background: {t.CANVAS};
    }}
    QPushButton[variant="danger"] {{
        background: {t.DANGER};
        color: white;
        border-color: {t.DANGER};
    }}
    QPushButton[variant="danger"]:hover {{
        background: #c11f1f;
        border-color: #c11f1f;
    }}
    /* A button that reads as text: for the secondary way out of a screen
       ("Forgot password?"), where a bordered button would compete with
       the one action the screen is actually for. */
    QPushButton[variant="link"] {{
        background: transparent;
        color: {t.PRIMARY};
        border: none;
        padding: 2px 0;
        font-weight: {t.WEIGHT_MEDIUM};
    }}
    QPushButton[variant="link"]:hover {{
        color: {t.PRIMARY_HOVER};
        text-decoration: underline;
    }}
    QPushButton[variant="link"]:disabled {{
        color: {t.MUTED};
        text-decoration: none;
    }}

    /* ---------------- Inputs ---------------- */
    QLineEdit, QComboBox, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox {{
        background: {t.SURFACE};
        border: 1px solid {t.LINE};
        border-radius: {t.RADIUS_SM}px;
        padding: 7px 10px;
        font-size: 13.5px;
        color: {t.INK};
        selection-background-color: {t.PRIMARY_TINT};
    }}
    /* A field you cannot type into should not invite you to try. After
       the rule above, so it wins on a plain QLineEdit. */
    QLineEdit:read-only {{
        background: {t.CANVAS};
        color: {t.MUTED};
    }}
    QLineEdit:hover, QComboBox:hover, QTextEdit:hover, QPlainTextEdit:hover,
    QSpinBox:hover, QDoubleSpinBox:hover {{
        border: 1px solid {t.NAVY_TEXT_SOFT};
    }}
    QLineEdit:focus, QComboBox:focus, QTextEdit:focus, QPlainTextEdit:focus,
    QSpinBox:focus, QDoubleSpinBox:focus {{
        border: 1px solid {t.PRIMARY};
    }}
    QComboBox {{
        min-height: 22px;
        padding-right: 30px;
    }}
    QComboBox::drop-down {{
        border: none;
        width: 28px;
        subcontrol-origin: padding;
        subcontrol-position: center right;
    }}
    {_chevron_rule()}
    /* A searchable combo (widgets/searchable_combo.py) is a box with a
       QLineEdit inside it, which the generic input rule above also
       matches — so without this the search field draws its own bordered
       white box inside the combo's own. Same trap, and the same fix by
       objectName, as the spin box further down. */
    QLineEdit#ComboSearchField {{
        background: transparent;
        border: none;
        border-radius: 0px;
        padding: 0px;
    }}
    /* The combo that names what a whole screen is about — the ledgers'
       customer and supplier pickers. Set bold because the rows below it
       are meaningless without it: it is a heading that happens to be a
       control. The inner field is named too; the text of an editable
       combo is drawn by that, not by the box around it. */
    QComboBox[role="subject"],
    QComboBox[role="subject"] QLineEdit#ComboSearchField {{
        font-weight: {t.WEIGHT_SEMIBOLD};
    }}
    /* The open combo's list: flat, same surface and radius as the box it
       drops out of, rather than the platform's boxed popup. The list of
       search matches is styled with it: a completer's popup is a
       top-level view of its own rather than a child of the combo, so the
       descendant selector never reaches it and it would otherwise drop
       out of the same box looking like a different control. */
    QComboBox QAbstractItemView, QListView#ComboSearchPopup {{
        background: {t.SURFACE};
        border: 1px solid {t.LINE};
        border-radius: {t.RADIUS_SM}px;
        padding: 4px;
        outline: none;
        selection-background-color: {t.PRIMARY_TINT};
        selection-color: {t.INK};
    }}
    QComboBox QAbstractItemView::item, QListView#ComboSearchPopup::item {{
        min-height: 26px;
        padding: 0px 8px;
        border-radius: 4px;
        color: {t.INK};
    }}

    /* ---------------- Modern spin stepper (widgets/modern_spinbox.py) ----
       A composite of our own +/- QPushButtons around a borderless
       QSpinBox, styled as one seamless control — see that file for why
       (native spin arrows don't reliably follow QSS). */
    QWidget#ModernSpinBox {{
        background: {t.SURFACE};
        border: 1px solid {t.LINE};
        border-radius: {t.RADIUS_SM}px;
        min-height: 36px;
    }}
    QWidget#ModernSpinBox:hover {{
        border: 1px solid {t.NAVY_TEXT_SOFT};
    }}
    QSpinBox#ModernSpinBoxField {{
        background: transparent;
        border: none;
        border-radius: 0px;
        padding: 0px;
    }}
    /* A QSpinBox is a composite: the editable part is an internal child
       QLineEdit named "qt_spinbox_lineedit", which the generic QLineEdit
       rule above also matches — so without this it draws its own bordered
       white box *inside* our borderless field. It has to be selected by
       that objectName; a descendant selector does not reach Qt-internal
       children. Every spin box in this app is a ModernSpinBox field, so
       the unscoped selector is safe. */
    QLineEdit#qt_spinbox_lineedit {{
        background: transparent;
        border: none;
        border-radius: 0px;
        padding: 0px;
    }}
    QPushButton#SpinStepUp, QPushButton#SpinStepDown {{
        background: {t.SURFACE};
        color: {t.INK_SOFT};
        border: none;
        padding: 0px;
        min-width: 32px;
        max-width: 32px;
        font-size: 16px;
        font-weight: {t.WEIGHT_SEMIBOLD};
        border-radius: 0px;
    }}
    QPushButton#SpinStepUp:disabled, QPushButton#SpinStepDown:disabled {{
        color: {t.LINE};
        background: {t.SURFACE};
    }}
    QPushButton#SpinStepDown {{
        border-right: 1px solid {t.LINE};
        border-top-left-radius: {t.RADIUS_SM}px;
        border-bottom-left-radius: {t.RADIUS_SM}px;
    }}
    QPushButton#SpinStepUp {{
        border-left: 1px solid {t.LINE};
        border-top-right-radius: {t.RADIUS_SM}px;
        border-bottom-right-radius: {t.RADIUS_SM}px;
    }}
    QPushButton#SpinStepUp:hover, QPushButton#SpinStepDown:hover {{
        background: {t.PRIMARY_TINT}; color: {t.PRIMARY};
    }}
    QPushButton#SpinStepUp:pressed, QPushButton#SpinStepDown:pressed {{
        background: {t.PRIMARY}; color: white;
    }}

    /* Inline form error (sign-in). A tinted band rather than a modal —
       a wrong password is an expected event, not an interruption. */
    QLabel#FormError {{
        background: {t.DANGER_TINT};
        color: {t.DANGER};
        border: 1px solid {t.DANGER};
        border-radius: {t.RADIUS_SM}px;
        padding: 8px 10px;
        font-size: 12.5px;
        font-weight: {t.WEIGHT_MEDIUM};
    }}
    /* Same block, same place in the form, recoloured — so a success
       message and a failure message never shift the layout between
       them. Set via the "tone" property; see qss.repolish. */
    QLabel#FormError[tone="success"] {{
        background: {t.SUCCESS_TINT};
        color: {t.SUCCESS};
        border-color: {t.SUCCESS};
    }}

    /* ---------------- Checkboxes ---------------- */
    QCheckBox {{
        font-size: 13px;
        color: {t.INK_SOFT};
        spacing: 8px;
    }}
    QCheckBox::indicator {{
        width: 16px;
        height: 16px;
        border: 1px solid {t.LINE};
        border-radius: 4px;
        background: {t.SURFACE};
    }}
    QCheckBox::indicator:hover {{
        border: 1px solid {t.PRIMARY};
    }}
    QCheckBox::indicator:checked {{
        background: {t.PRIMARY};
        border: 1px solid {t.PRIMARY};
        {_tick_rule()}
    }}
    QCheckBox:disabled {{
        color: {t.MUTED};
    }}

    /* ---------------- Header user chip ---------------- */
    QFrame#UserChip {{
        background: transparent;
        border: 1px solid transparent;
        border-radius: {t.RADIUS_SM}px;
    }}
    QFrame#UserChip:hover {{
        background: {t.CANVAS};
        border: 1px solid {t.LINE};
    }}
    QLabel#UserAvatar {{
        background: {t.PRIMARY_TINT};
        color: {t.PRIMARY};
        border-radius: 7px;
        font-weight: {t.WEIGHT_SEMIBOLD};
        font-size: 12px;
    }}
    /* Numbered step badge in multi-step dialogs (New purchase). */
    QLabel#StepBadge {{
        background: {t.PRIMARY};
        color: white;
        border-radius: 11px;
        font-size: 11px;
        font-weight: {t.WEIGHT_SEMIBOLD};
    }}
    QLabel#ProfileAvatar {{
        background: {t.PRIMARY_TINT};
        color: {t.PRIMARY};
        border-radius: 12px;
        font-weight: {t.WEIGHT_SEMIBOLD};
        font-size: 20px;
    }}

    /* ---------------- Menus (user chip, context menus) ---------------- */
    QMenu {{
        background: {t.SURFACE};
        border: 1px solid {t.LINE};
        border-radius: {t.RADIUS_SM}px;
        padding: 6px;
    }}
    QMenu::item {{
        padding: 7px 22px 7px 12px;
        border-radius: 5px;
        font-size: 13px;
        color: {t.INK};
    }}
    QMenu::item:selected {{
        background: {t.PRIMARY_TINT};
        color: {t.PRIMARY};
    }}
    QMenu::item:disabled {{
        color: {t.MUTED};
    }}
    QMenu::separator {{
        height: 1px;
        background: {t.LINE};
        margin: 5px 8px;
    }}

    QLabel[role="fieldLabel"] {{
        font-size: 13px;
        font-weight: {t.WEIGHT_SEMIBOLD};
        color: {t.INK};
    }}
    QLabel[role="fieldHelp"] {{
        font-size: 12px;
        color: {t.MUTED};
    }}

    /* ---------------- Text roles ---------------- */
    QLabel[role="crumb"] {{
        font-size: 12.5px;
        color: {t.MUTED};
    }}
    QLabel[role="pageTitle"] {{
        font-size: 24px;
        font-weight: {t.WEIGHT_BOLD};
        color: {t.INK};
    }}
    QLabel[role="pageSub"] {{
        font-size: 13px;
        color: {t.MUTED};
    }}
    QLabel[role="panelTitle"] {{
        font-size: 14.5px;
        font-weight: {t.WEIGHT_SEMIBOLD};
        color: {t.INK};
    }}
    QLabel[role="panelSub"] {{
        font-size: 12.5px;
        color: {t.MUTED};
    }}

    /* ---------------- Panels / cards ---------------- */
    QFrame[role="panel"] {{
        background: {t.SURFACE};
        border: 1px solid {t.LINE};
        border-radius: {t.RADIUS}px;
    }}
    QFrame[role="statTile"] {{
        background: {t.SURFACE};
        border: 1px solid {t.LINE};
        border-radius: {t.RADIUS}px;
    }}
    QLabel[role="statLabel"] {{
        font-size: 12.5px;
        font-weight: {t.WEIGHT_BOLD};
        color: {t.MUTED};
    }}
    QLabel[role="statValue"] {{
        font-size: 26px;
        font-weight: {t.WEIGHT_BOLD};
        color: {t.INK};
    }}
    QLabel[role="statUnit"] {{
        font-size: 13px;
        font-weight: {t.WEIGHT_SEMIBOLD};
        color: {t.MUTED};
    }}
    QLabel[role="statNote"] {{
        font-size: 11.5px;
        color: {t.MUTED};
    }}

    /* ---------------- Record card (dialogs/record_card_dialog.py) ----
       A read-only window onto one document. The head names the record and
       the foot carries the two ways off it; both are pinned, so they are
       banded off the page that scrolls between them. */
    QFrame[role="cardBand"] {{
        background: {t.SURFACE};
        border: none;
        border-bottom: 1px solid {t.LINE};
    }}
    QFrame[role="cardFoot"] {{
        background: {t.SURFACE};
        border: none;
        border-top: 1px solid {t.LINE};
    }}
    /* The record's own words, set apart from the figures above them: a
       tinted block reads as something someone typed rather than as one
       more computed line. */
    QLabel[role="cardNote"] {{
        background: {t.CANVAS};
        border: 1px solid {t.LINE};
        border-radius: {t.RADIUS_SM}px;
        padding: 10px 12px;
        color: {t.INK_SOFT};
        font-size: 12.5px;
    }}

    /* ---------------- Tags / pills ---------------- */
    QLabel[role="tag"][tone="success"] {{
        background: {t.SUCCESS_TINT}; color: {t.SUCCESS};
        border-radius: 9px; font-size: 11px; font-weight: {t.WEIGHT_SEMIBOLD};
        padding: 2px 8px;
    }}
    QLabel[role="tag"][tone="info"] {{
        background: {t.INFO_TINT}; color: {t.INFO};
        border-radius: 9px; font-size: 11px; font-weight: {t.WEIGHT_SEMIBOLD};
        padding: 2px 8px;
    }}
    QLabel[role="tag"][tone="warning"] {{
        background: {t.WARNING_TINT}; color: {t.WARNING};
        border-radius: 9px; font-size: 11px; font-weight: {t.WEIGHT_SEMIBOLD};
        padding: 2px 8px;
    }}
    QLabel[role="tag"][tone="danger"] {{
        background: {t.DANGER_TINT}; color: {t.DANGER};
        border-radius: 9px; font-size: 11px; font-weight: {t.WEIGHT_SEMIBOLD};
        padding: 2px 8px;
    }}
    /* A state with no colour of its own — a draft job, an expense that is
       simply recorded. Same chip, so it sits in line with the ones that do. */
    QLabel[role="tag"][tone="muted"] {{
        background: {t.CANVAS}; color: {t.MUTED};
        border-radius: 9px; font-size: 11px; font-weight: {t.WEIGHT_SEMIBOLD};
        padding: 2px 8px;
    }}
    QLabel[role="pill"][tone="ok"] {{ color: {t.MUTED}; font-weight: {t.WEIGHT_SEMIBOLD}; font-size: 12.5px; }}
    QLabel[role="pill"][tone="low"] {{ color: {t.WARNING}; font-weight: {t.WEIGHT_SEMIBOLD}; font-size: 12.5px; }}
    QLabel[role="pill"][tone="out"] {{ color: {t.DANGER}; font-weight: {t.WEIGHT_SEMIBOLD}; font-size: 12.5px; }}

    /* ---------------- Tables ---------------- */
    /* Tables always sit inside a [role="panel"], which already draws the
       frame — a border here would double it up along every edge. Only the
       top rule is kept, to separate the header row from the toolbar. */
    QTableView {{
        background: {t.SURFACE};
        border: none;
        border-top: 1px solid {t.LINE};
        border-radius: 0px;
        gridline-color: {t.LINE_SOFT};
        selection-background-color: {t.PRIMARY_TINT};
        selection-color: {t.INK};
        font-size: 13px;
    }}
    /* Cell and header padding must match exactly, or a heading sits a few
       pixels off the column it labels. */
    QTableView::item {{
        padding: 8px 12px;
        border-bottom: 1px solid {t.LINE_SOFT};
    }}
    QHeaderView::section {{
        background: {t.CANVAS};
        color: {t.MUTED};
        font-size: 11px;
        font-weight: {t.WEIGHT_SEMIBOLD};
        border: none;
        border-bottom: 1px solid {t.LINE};
        padding: 8px 12px;
    }}

    /* The grouped payment lists are QTreeViews. They are the same table
       visually — same surface, same header, same row rule — with a
       disclosure arrow on the rows that have detail. Row height comes from
       ::item here because a tree has no vertical header to set it on. */
    QTreeView {{
        background: {t.SURFACE};
        border: none;
        border-top: 1px solid {t.LINE};
        border-radius: 0px;
        selection-background-color: {t.PRIMARY_TINT};
        selection-color: {t.INK};
        font-size: 13px;
    }}
    QTreeView::item {{
        height: 38px;
        padding: 0px 12px;
        border-bottom: 1px solid {t.LINE_SOFT};
    }}
    /* Left untouched on purpose: styling ::branch replaces the native
       arrow with an image, and there is no image to give it. The style's
       own indicator is drawn instead, which is what we want. */

    /* ---------------- Recent activity (widgets/activity_list.py) ----
       The scroller and its body are mechanism, not surface: they let the
       panel through. Only the rows paint. */
    QScrollArea#ActivityScroll, QWidget#ActivityBody {{
        background: transparent;
        border: none;
    }}
    QFrame[role="activityRow"] {{
        background: transparent;
        border: none;
        border-bottom: 1px solid {t.LINE_SOFT};
    }}
    QFrame[role="activityRow"]:hover {{
        background: {t.CANVAS};
    }}
    /* Selected is the full accent, not the tint the tables use: this is
       one row picked out of a feed you are reading, not a row a toolbar is
       about to act on. */
    QFrame[role="activityRow"][selected="true"] {{
        background: {t.PRIMARY};
    }}
    QLabel[role="activityTitle"] {{
        color: {t.INK};
        font-size: 13px;
        font-weight: {t.WEIGHT_SEMIBOLD};
        background: transparent;
    }}
    QLabel[role="activityMeta"] {{
        color: {t.MUTED};
        font-size: 12px;
        background: transparent;
    }}
    QLabel[role="activityWhen"] {{
        color: {t.MUTED};
        font-size: 11.5px;
        background: transparent;
    }}
    QFrame[role="activityRow"][selected="true"] QLabel {{
        color: white;
    }}

    /* ---------------- Panel summary figures (widgets/summary_strip.py) ----
       Each figure is boxed so two of them side by side read as two
       separate numbers rather than as one run-on total. */
    QWidget#SummaryFigure {{
        background: {t.CANVAS};
        border: 1px solid {t.LINE};
        border-radius: {t.RADIUS_SM}px;
    }}

    /* ---------------- Uncosted-profit caveat (views/profit_and_loss_view.py)
       A warning about the figures directly above it, so it is tinted
       rather than quiet: a profit that does not know what some of its
       stock cost must not be read as if it did. */
    QLabel#uncostedCaveat {{
        background: {t.WARNING_TINT};
        color: {t.WARNING};
        border: 1px solid {t.WARNING};
        border-radius: {t.RADIUS_SM}px;
        padding: 10px 14px;
    }}

    /* ---------------- Quick-add row ---------------- */
    QFrame#AddRowStrip {{
        background: {t.PRIMARY_TINT};
        border: none;
        border-top: 1px solid {t.LINE};
    }}

    /* ---------------- Misc ---------------- */
    /* A page scroller is a mechanism, not a surface: it and its viewport
       let the screen's own background through. Named explicitly rather
       than styling QScrollArea broadly, per the note at the top of this
       file about rules that leak into a whole subtree. */
    QScrollArea#PageScroll,
    QScrollArea#PageScroll > QWidget#qt_scrollarea_viewport,
    QWidget#PageScrollBody {{
        background: transparent;
        border: none;
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 10px;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: {t.LINE};
        border-radius: 5px;
        min-height: 24px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    /* Horizontal was never styled, so any table that overflowed grew a
       native scrollbar in the middle of an otherwise flat surface. */
    QScrollBar:horizontal {{
        background: transparent;
        height: 10px;
        margin: 0;
    }}
    QScrollBar::handle:horizontal {{
        background: {t.LINE};
        border-radius: 5px;
        min-width: 24px;
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px;
    }}
    QScrollBar::add-page, QScrollBar::sub-page {{
        background: transparent;
    }}
    """
