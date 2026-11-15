import QtQuick
import QtQuick.Controls
import CNTheme
import "FormTips.js" as FormTips

// A text field of the Settings window. It keeps what is typed and reports
// it on every keystroke (`edited`, so the session re-checks it) and when to
// save (`committed`: Enter or leaving the field). `shown` is the model's
// value, applied while the field doesn't have the focus (an echo of what is
// being typed never moves the cursor). `error` draws the red outline and
// ends the tooltip with "⚠ error" (Tk's mark); `tip` is the field's help,
// shared with its caption, and `range` the muted line under it ("Range 5–24").
TextField {
    id: control
    property var shown: ""
    property string error: ""
    property string tip: ""
    property string range: ""
    signal edited(string text)
    signal committed()

    Binding on text {
        value: control.shown === undefined || control.shown === null ? "" : String(control.shown)
        when: !control.activeFocus
        restoreMode: Binding.RestoreNone
    }
    onTextEdited: control.edited(control.text)
    onEditingFinished: control.committed()

    // The error outline, over the style's border (the mockup's recipe).
    Rectangle {
        anchors.fill: parent
        visible: control.error !== ""
        radius: Theme.radius
        color: "transparent"
        border.width: Math.max(Theme.hairline, Theme.devW(1.5))
        border.color: Theme.error
    }
    // A disabled field gets no hover (pitfall 16): the tooltip hangs off a HoverHandler.
    HoverHandler { id: hover }
    ToolTip.visible: hover.hovered && ToolTip.text !== ""
    ToolTip.delay: 600
    ToolTip.text: FormTips.tip(control.tip, control.error, control.range, Theme.muted)
}
