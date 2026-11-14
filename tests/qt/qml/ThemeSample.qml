import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import CNTheme

// The theme and a few CNStyle controls in a window with the main window's
// plumbing: what Main.qml showed in plan step C2, kept for the tests of the
// scaling recipe (tests/qt/test_qt_window.py) now that the shell has no
// caret, toolbar or heading yet. Loaded with main.load_window.
//
// The plumbing (as in Main.qml):
// - windowDpr, fontRevision and contentReady are written by DprWatcher
//   (dpr.py): the window's real device pixel ratio, a counter that makes
//   every Theme font a new instance after a ratio change, and the deferred
//   first show (DprWatcher keeps the whole window transparent until the
//   ratio has settled, then sets contentReady).
// - Resizing and Theme.scale changes bump Theme.layoutRevision, so the
//   snapped text (SnapTranslate) re-snaps.
// - altWatcher (alt_watcher.py) is the hidden menu bar's Alt handling; the
//   menus (F1) connect to its signals.
ApplicationWindow {
    id: win

    required property QtObject altWatcher
    property real windowDpr: 1.0
    property int fontRevision: 0
    property bool contentReady: false
    Binding { target: Theme; property: "dpr"; value: win.windowDpr }
    Binding { target: Theme; property: "fontRevision"; value: win.fontRevision }
    onWidthChanged: Theme.bumpLayout()
    onHeightChanged: Theme.bumpLayout()
    Connections {
        target: Theme
        function onScaleChanged() { Theme.bumpLayout() }
    }

    title: "Theme sample"
    visible: false
    minimumWidth: Theme.px(225)
    minimumHeight: Theme.px(140)
    Component.onCompleted: {
        // 400 x 250 units at 100%, as in the mockup.
        width = Math.round(Theme.px(400) / Theme.scale)
        height = Math.round(Theme.px(250) / Theme.scale)
    }

    header: Rectangle {
        implicitHeight: Theme.toolbarHeight
        color: Theme.chrome
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: Theme.gap2
            anchors.rightMargin: Theme.gap2
            spacing: Theme.gap1
            ToolButton {
                objectName: "undoButton"
                icon.source: Theme.iconUrl("undo")
                ToolTip.visible: hovered
                ToolTip.text: "Undo"
            }
            ToolButton { icon.source: Theme.iconUrl("redo") }
            ToolSeparator { }
            ToolButton {
                icon.source: Theme.iconUrl("transpose")
                text: "Transpose"
                display: AbstractButton.TextBesideIcon
            }
            Item { Layout.fillWidth: true }
            Switch {
                objectName: "darkSwitch"
                text: "Dark theme"
                checked: Theme.dark
                onToggled: Theme.dark = checked
            }
            Button {
                text: "Play"
                highlighted: true
                icon.source: Theme.iconUrl("play")
            }
        }
        Rectangle {
            anchors.bottom: parent.bottom
            width: parent.width
            height: Theme.hairline
            color: Theme.border
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.gap6
        spacing: Theme.gap3

        SText {
            objectName: "heading"
            text: "Chord Notepad"
            font: Theme.fontHeadF
            color: Theme.text
        }
        Label {
            text: "The Qt window is being built. This page shows the theme and its controls."
            color: Theme.muted
        }
        RowLayout {
            spacing: Theme.gap3
            ComboBox {
                model: ["Guitar (Standard - EADGBE)", "Ukulele (GCEA)", "Piano"]
                Layout.preferredWidth: Theme.px(60)
            }
            TextField {
                placeholderText: "Notes, e.g. C E G"
                Layout.preferredWidth: Theme.px(50)
            }
            CheckBox { text: "Word wrap" }
        }
        Row {
            spacing: Theme.gap2
            height: Theme.controlHeight
            SText {
                text: "Caret"
                font: Theme.fontS
                color: Theme.muted
                anchors.verticalCenter: parent.verticalCenter
            }
            SnapLine {
                objectName: "caret"
                height: parent.height
                color: Theme.text
            }
        }
        Item { Layout.fillHeight: true }
    }
}
