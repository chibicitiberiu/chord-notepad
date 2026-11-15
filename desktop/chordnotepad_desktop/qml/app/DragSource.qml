import QtQuick
import CNTheme

// Click-or-drag for sidebar items (the mockup's DragSource.qml): a palette
// tile's snippet, an identifier candidate's chord. A MouseArea, not a
// DragHandler: inside a button the DragHandler lost the moves to the
// button's grab (and could turn active on a plain click), and the
// ScrollView's Flickable would steal vertical drags; preventStealing keeps
// the gesture here (pitfall 5). It must sit above the button (z >= 0): a
// negative z child is stacked below its parent for input too (pitfall 4).
//
// A press that moves 1.5u starts the drag (`dnd`, Main.qml's: the chip by
// the pointer, the closed-hand or no-drop pointer); one that doesn't is a
// click (`tapped`, with `shift` set when Shift was held); a double click is
// `doubleTapped` where `doubleClicks` is set (its first click still
// `tapped`; the release that ends it isn't another one), else two taps. Where a click still does something while the
// editor is read-only (an identifier row), `draggable` false keeps the click and stops
// the drag; elsewhere the source is disabled, as the click it stands for.
MouseArea {
    id: src
    required property var dnd
    property string snippet
    property string kind: "snippet"
    property bool draggable: true
    property bool dragging: false
    property point pressAt
    property bool shift: false
    property bool doubleClicks: false     // a double click is its own gesture (else two taps)
    property bool doubled: false
    signal tapped()
    signal doubleTapped()
    anchors.fill: parent
    z: 1
    hoverEnabled: true
    preventStealing: true
    cursorShape: !draggable ? Qt.ArrowCursor : dragging ? Qt.ClosedHandCursor : Qt.PointingHandCursor
    onPressed: (m) => { src.pressAt = Qt.point(m.x, m.y); src.dragging = false }
    onPositionChanged: (m) => {
        if (!src.pressed || !src.draggable) return
        var p = src.mapToItem(null, m.x, m.y)
        if (!src.dragging && Math.abs(m.x - src.pressAt.x) + Math.abs(m.y - src.pressAt.y) > Theme.px(1.5)) {
            src.dragging = true
            src.dnd.begin(src.snippet, p, src.kind)
        }
        if (src.dragging) src.dnd.move(p)
    }
    onReleased: (m) => {
        if (src.dragging) { src.dragging = false; src.dnd.end(); return }
        if (src.doubled) { src.doubled = false; return }
        src.shift = (m.modifiers & Qt.ShiftModifier) !== 0
        src.tapped()
    }
    onDoubleClicked: { if (!src.doubleClicks) return; src.doubled = true; src.doubleTapped() }
    onCanceled: if (src.dragging) { src.dragging = false; src.dnd.cancel() }
}
