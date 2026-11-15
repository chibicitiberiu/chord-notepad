import QtQuick
import QtQuick.Controls
import CNTheme

// The song's tempo in the player bar (plan step E2). When it can be changed
// it is Tk's BPM scrubber (scrubber.py, removed in 0.6.0; the scale is the
// core's toolbar.BPM_SCALE, through PlayerBarModel):
// - a press becomes a drag after 3 px; every 4 px is one step, counted from
//   where the press started (not added up per move), magnetic to tens, sent live;
// - a click without a drag turns it into a field, everything selected and
//   the cursor at the end: Enter or keypad Enter commits, Escape cancels,
//   focus-out commits; the core's parse_bpm reads it ("119.6" is 120) and
//   keeps the old value for text it can't read;
// - the wheel steps by one, never sticking at a multiple of ten (Q2);
// - middle-click resets to 120 (nothing when it's already 120);
// - a tint that darkens on hover, the horizontal-resize cursor;
// - from the keyboard (Q10): Tab to it, Up/Down step, Enter or Space types.
// While a song plays it shows the effective tempo, read-only (plain arrow,
// no tint). When the song sets the tempo ({bpm: 90} before the first chord)
// it is a link to that directive: muted, underlined on hover, and a click
// asks for goToDirective().
FocusScope {
    id: tr
    objectName: "tempoReadout"
    required property var store
    required property var player
    signal goToDirective()

    readonly property var tb: tr.store.states.ToolbarState
    readonly property string setBy: tr.tb.bpm_set_by || ""
    readonly property bool editable: tr.tb.bpm_editable === true && tr.setBy === ""
    readonly property int value: tr.tb.bpm || 120
    readonly property int shown: tr.editable ? (tr.dragging ? tr.dragValue : tr.value)
                                            : (tr.tb.bpm_display || tr.value)
    readonly property string tip: tr.setBy !== ""
        ? tr.player.setByTooltip("<font face='" + Theme.monoFont + "' color='" + Theme.directive + "'>"
                                 + tr.setBy + "</font>") + " · click to go there"
        : tr.player.texts.bpm
    property bool editing: false
    property bool dragging: false
    property int dragValue: 0
    property real pressX: 0
    property int pressValue: 0
    property bool pressing: false
    property real notches: 0

    implicitWidth: tr.editing ? field.implicitWidth : chip.implicitWidth
    implicitHeight: chip.implicitHeight
    activeFocusOnTab: tr.editable || tr.setBy !== ""

    function send(v) { tr.store.submit("set_bpm", { bpm: v }) }
    function step(direction) { if (tr.editable) tr.player.stepBpm(direction) }
    function startEdit() {
        if (!tr.editable) return
        field.text = String(tr.value)
        tr.editing = true
        field.forceActiveFocus()
        field.select(0, field.length)          // all selected, the cursor at the end
    }
    function commit() {
        if (!tr.editing) return
        tr.editing = false
        var text = field.text.trim()
        if (text !== "" && text !== String(tr.value)) tr.store.submit("set_bpm_text", { text: text })
        if (field.activeFocus) tr.forceActiveFocus()
    }
    function cancel() {
        if (!tr.editing) return
        tr.editing = false
        tr.forceActiveFocus()
    }
    onEditableChanged: if (!tr.editable) tr.cancel()     // Play locks it (Tk's set_readonly)

    Keys.onUpPressed: tr.step(1)
    Keys.onDownPressed: tr.step(-1)
    Keys.onReturnPressed: tr.setBy !== "" ? tr.goToDirective() : tr.startEdit()
    Keys.onEnterPressed: tr.setBy !== "" ? tr.goToDirective() : tr.startEdit()
    Keys.onSpacePressed: tr.setBy !== "" ? tr.goToDirective() : tr.startEdit()

    Rectangle {
        id: chip
        objectName: "tempoChip"
        visible: !tr.editing
        implicitWidth: label.implicitWidth + 2 * Theme.gap1
        implicitHeight: label.implicitHeight + Theme.px(0.5)
        radius: Theme.radiusSmall
        color: !tr.editable ? "transparent"
               : (area.containsMouse || tr.pressing) ? Theme.pressed : Theme.hover
        border.width: tr.activeFocus && !tr.editing ? Theme.hairline : 0
        border.color: Theme.accent
        SText {
            id: label
            objectName: "tempoText"
            anchors.centerIn: parent
            text: String(tr.shown)
            font: tr.editable ? Theme.fontTabularStrong
                  : tr.setBy !== "" && area.containsMouse ? Theme.fontTabularLink : Theme.fontTabular
            color: tr.editable ? Theme.accent : tr.setBy !== "" && area.containsMouse ? Theme.text : Theme.muted
        }
        // A MouseArea with preventStealing, not a DragHandler (pitfall 5).
        MouseArea {
            id: area
            objectName: "tempoArea"
            anchors.fill: parent
            acceptedButtons: Qt.LeftButton | Qt.MiddleButton
            hoverEnabled: true
            preventStealing: true
            cursorShape: tr.editable ? Qt.SizeHorCursor : tr.setBy !== "" ? Qt.PointingHandCursor : Qt.ArrowCursor
            onPressed: (m) => {
                if (m.button === Qt.MiddleButton) {
                    if (tr.editable && tr.value !== 120) tr.store.submit("reset_bpm")
                    return
                }
                if (!tr.editable) return
                tr.pressX = mapToItem(null, m.x, m.y).x
                tr.pressValue = tr.value
                tr.dragValue = tr.value
                tr.dragging = false
                tr.pressing = true
            }
            onPositionChanged: (m) => {
                if (!tr.pressing) return
                var dx = mapToItem(null, m.x, m.y).x - tr.pressX
                if (!tr.dragging && Math.abs(dx) >= Theme.scrubThreshold) tr.dragging = true
                if (!tr.dragging) return
                var v = tr.player.bpmDragged(tr.pressValue, Math.floor(dx / Theme.scrubStep))
                if (v !== tr.dragValue) { tr.dragValue = v; tr.send(v) }
            }
            onReleased: (m) => {
                if (m.button !== Qt.LeftButton) return
                if (tr.setBy !== "") { tr.goToDirective(); return }
                var wasDrag = tr.dragging
                tr.pressing = false
                tr.dragging = false
                if (tr.editable && !wasDrag) tr.startEdit()
            }
            onCanceled: { tr.pressing = false; tr.dragging = false }
            onWheel: (w) => {
                if (!tr.editable) return
                tr.notches += w.angleDelta.y / 120
                while (Math.abs(tr.notches) >= 1) {
                    var dir = tr.notches > 0 ? 1 : -1
                    tr.notches -= dir
                    tr.step(dir)
                }
            }
        }
        ToolTip.visible: area.containsMouse && !tr.pressing
        ToolTip.delay: 600
        ToolTip.text: tr.tip
    }
    TextField {
        id: field
        objectName: "tempoField"
        visible: tr.editing
        implicitWidth: Math.max(chip.implicitWidth, Theme.px(10))
        implicitHeight: chip.implicitHeight
        anchors.verticalCenter: parent.verticalCenter
        leftPadding: Theme.gap1; rightPadding: Theme.gap1
        topPadding: 0; bottomPadding: 0
        horizontalAlignment: TextInput.AlignHCenter
        font: Theme.fontTabular
        Keys.onReturnPressed: tr.commit()
        Keys.onEnterPressed: tr.commit()
        Keys.onEscapePressed: tr.cancel()
        onActiveFocusChanged: if (!activeFocus) tr.commit()
    }
}
