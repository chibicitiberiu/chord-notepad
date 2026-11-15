pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import CNTheme
import CNSheet

// The chord sheet (plan step E4): flat view tabs, (Edit) the Voicing
// selector, the zoom and ×, then the strip, drawn by SheetView
// (chord_sheet.py: a viewport-sized QQuickPaintedItem replaying the core's
// packed draw ops). One instance, moved between the Edit panel (F9) and
// the Play workspace's strip, as in the mockup.
//
// Everything comes from ChordSheetState: the views and why the fretted
// ones are off (a disabled tab's tooltip), the zoom (the core's rules:
// ×1.2 a step, 50-250%, per view, kept; none on the piano roll), what plays
// (`current_index`, the yellow column) and the playhead's chord
// (`cursor_index`, the edge mark). A tab sends set_chord_sheet_view only
// when clicked, so a view the core falls back to (Fret cards on a piano
// voicing) isn't kept as the user's choice. A click on a chord sends
// audition: it sounds and, with the Qt playhead, seeks.
Rectangle {
    id: pane
    objectName: "chordSheetPane"
    required property var store
    required property var model
    property var editor: null              // the EditorBridge: a tap shows the chord in the text
    property bool closable: false          // Edit: × hides the panel (F9)
    property bool showVoicing: false       // Edit only: Play has Voicing in its player bar
    property bool active: false            // on screen: fetch and paint
    signal closeRequested()
    signal editVoicings()
    property alias view: sheet
    color: Theme.panel

    readonly property var st: pane.store.states.ChordSheetState
    readonly property var views: pane.st.views || []
    readonly property string activeView: pane.st.active_view || ""
    readonly property real zoom: pane.st.zoom || 1.0
    readonly property bool zoomable: pane.st.zoom_supported === true

    // Ctrl+wheel's eighths of a notch not turned into zoom steps yet (touchpads).
    property real zoomWheel: 0
    function zoomBy(steps, anchorX) {
        if (!pane.zoomable || steps === 0) return
        sheet.zoomAnchor = anchorX === undefined ? -1 : anchorX
        pane.store.submit("chord_sheet_zoom", { step: steps })
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: Theme.panelHeader
            color: Theme.panel
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: Theme.gap2; anchors.rightMargin: Theme.gap1
                spacing: Theme.gap1
                Row {
                    objectName: "sheetTabs"
                    Layout.fillHeight: true
                    Repeater {
                        model: pane.views
                        // A disabled tab gets no hover: the reason hangs off this parent (pitfall 16).
                        Item {
                            id: tab
                            required property var modelData
                            required property int index
                            readonly property bool available: tab.modelData.available === true
                            objectName: "sheetTab:" + tab.modelData.view_id
                            implicitWidth: tabButton.implicitWidth
                            height: parent ? parent.height : implicitHeight
                            HoverHandler { id: tabHover }
                            ToolTip.visible: tabHover.hovered && (tab.available || (pane.st.disabled_reason || "") !== "")
                            ToolTip.delay: tab.available ? 800 : 400
                            ToolTip.text: tab.available ? "Alt+" + (tab.index + 1) : (pane.st.disabled_reason || "")
                            TabButton {
                                id: tabButton
                                anchors.fill: parent
                                text: tab.modelData.label
                                enabled: tab.available
                                checkable: false
                                checked: tab.modelData.view_id === pane.activeView
                                focusPolicy: Qt.NoFocus
                                onClicked: if (!checked) pane.store.submit("set_chord_sheet_view", { view_id: tab.modelData.view_id })
                            }
                        }
                    }
                }
                Item { Layout.fillWidth: true }
                VoicingButton {
                    objectName: "sheetVoicingTip"
                    visible: pane.showVoicing
                    store: pane.store
                    buttonName: "sheetVoicing"
                    menuName: "sheetVoicingMenu"
                    compact: true
                    // The label collapses below 150 units.
                    showText: pane.width > Theme.px(150)
                    onEditVoicings: pane.editVoicings()
                }
                Item { visible: pane.showVoicing; Layout.preferredWidth: Theme.gap2 }
                Label {
                    objectName: "sheetZoomLabel"
                    text: Math.round(pane.zoom * 100) + "%"
                    visible: pane.zoomable
                    color: Theme.muted; font: Theme.fontS
                }
                IconButton {
                    objectName: "sheetZoomOut"
                    iconName: "magnify-minus"; tip: "Zoom out"; shortcutHint: "Ctrl+wheel"
                    visible: pane.zoomable
                    enabled: pane.zoom > 0.5 + 1e-6
                    onClicked: pane.zoomBy(-1)
                }
                IconButton {
                    objectName: "sheetZoomIn"
                    iconName: "magnify-plus"; tip: "Zoom in"; shortcutHint: "Ctrl+wheel"
                    visible: pane.zoomable
                    enabled: pane.zoom < 2.5 - 1e-6
                    onClicked: pane.zoomBy(1)
                }
                Rectangle {   // hairline between the controls and ×
                    visible: pane.closable
                    Layout.preferredWidth: Theme.hairline; Layout.preferredHeight: Theme.px(4.5)
                    Layout.leftMargin: Theme.gap1; Layout.rightMargin: Theme.gap1
                    color: Theme.border
                }
                IconButton {
                    objectName: "sheetClose"
                    iconName: "close"; tip: "Hide the chord sheet"; shortcutHint: "F9"
                    visible: pane.closable
                    onClicked: pane.closeRequested()
                }
            }
            Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: Theme.hairline; color: Theme.border }
        }
        SheetView {
            id: sheet
            objectName: "sheetView"
            Layout.fillWidth: true
            Layout.fillHeight: true
            model: pane.model
            active: pane.active
            dark: Theme.dark
            dpr: Theme.dpr
            surface: Theme.panel
            playingColor: Theme.sheetPlaying
            edgeColor: Theme.accent
            fontFamily: Theme.uiFont
            playingIndex: pane.st.current_index === null || pane.st.current_index === undefined ? -1 : pane.st.current_index
            cursorIndex: pane.st.cursor_index === null || pane.st.cursor_index === undefined ? -1 : pane.st.cursor_index
            // The wheel scrolls (sideways too); Ctrl+wheel zooms about the pointer.
            WheelHandler {
                objectName: "sheetWheel"
                acceptedModifiers: Qt.NoModifier
                onWheel: (e) => {
                    var d = e.pixelDelta.x !== 0 || e.pixelDelta.y !== 0
                            ? (e.pixelDelta.x !== 0 ? -e.pixelDelta.x : -e.pixelDelta.y)
                            : (e.angleDelta.x !== 0 ? -e.angleDelta.x : -e.angleDelta.y)
                    sheet.scrollBy(d)
                }
            }
            WheelHandler {
                objectName: "sheetZoomWheel"
                acceptedModifiers: Qt.ControlModifier
                onWheel: (e) => {
                    pane.zoomWheel += e.angleDelta.y
                    var steps = pane.zoomWheel > 0 ? Math.floor(pane.zoomWheel / 120) : Math.ceil(pane.zoomWheel / 120)
                    if (steps === 0) return
                    pane.zoomWheel -= steps * 120
                    pane.zoomBy(steps, e.x)
                }
            }
            HoverHandler { cursorShape: Qt.PointingHandCursor }
            // Dragging scrolls sideways, by how far the pointer moved since the
            // press. A drag past the system threshold isn't a tap, so it
            // doesn't audition; a playing follow takes over again at the next
            // chord, as it does after the wheel.
            DragHandler {
                id: sheetDrag
                objectName: "sheetDrag"
                target: null
                yAxis.enabled: false
                cursorShape: Qt.ClosedHandCursor
                property real startScroll: 0
                onActiveChanged: if (active) startScroll = sheet.scrollX
                onTranslationChanged: if (active) sheet.scrollX = startScroll - translation.x
            }
            TapHandler {
                onTapped: (ev) => {
                    var i = sheet.chordAt(ev.position.x, ev.position.y)
                    if (i < 0) return
                    pane.store.submit("audition", { index: i })
                    if (pane.editor) pane.editor.revealPlayhead()
                }
            }
            // The staff draws every chord as a whole note for now.
            Label {
                objectName: "staffNotice"
                visible: pane.activeView === "staff"
                anchors.left: parent.left; anchors.leftMargin: Theme.gap2
                anchors.bottom: sheetBar.top; anchors.bottomMargin: Theme.px(0.5)
                width: Math.min(implicitWidth, parent.width - 2 * Theme.gap2)
                elide: Text.ElideRight
                text: "Rhythm isn't shown yet: every chord is drawn as a whole note."
                font: Theme.fontC
                color: Theme.muted
            }
            ScrollBar {
                id: sheetBar
                objectName: "sheetScrollBar"
                anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
                anchors.leftMargin: sheet.gutterWidth
                orientation: Qt.Horizontal
                readonly property real viewport: Math.max(0, sheet.width - sheet.gutterWidth)
                size: sheet.contentWidth > 0 ? Math.min(1, viewport / sheet.contentWidth) : 1
                position: sheet.contentWidth > 0 ? sheet.scrollX / sheet.contentWidth : 0
                onPositionChanged: if (pressed) sheet.scrollX = position * sheet.contentWidth
                policy: ScrollBar.AlwaysOn
            }
        }
    }
}
