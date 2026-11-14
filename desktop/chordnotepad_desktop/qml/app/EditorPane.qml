import QtQuick
import QtQuick.Controls
import CNTheme

// The song text (plan steps D1-D3): a monospace TextArea whose document the
// EditorBridge (editor_bridge.py) keeps in step with the session. It paints
// the session's highlighting, applies the session's edits and sends the
// user's; this file only routes input to it and draws the overlays.
// One instance, moved between the Edit and Play workspaces (Main.qml); in
// Play it is read-only, as in the mockup.
//
// Every position here is a TextArea (UTF-16) position; the bridge converts.
// Paste goes through the bridge on every path, so the text is normalised:
// Ctrl+V and Shift+Insert (Keys), the context menu, middle-click PRIMARY
// (the MouseArea, which keeps the press from the TextArea's own paste) and
// drag and drop (the DropArea, on top of the TextArea's own drop).
Rectangle {
    id: pane
    objectName: "editorPane"
    required property var editor
    // "Type or paste a song here", shown while the text is empty.
    property string placeholder: ""
    // Play workspace: read-only (Ctrl+1 or the pencil goes back to Edit).
    property bool playMode: false
    property alias area: area
    property bool overChord: false
    color: Theme.editorBg

    // The editor's commands, for the context menu here and the menus (F1).
    readonly property Action undoAction: Action {
        objectName: "undoAction"
        text: "&Undo"; shortcut: "Ctrl+Z"
        enabled: area.canUndo && !area.readOnly
        onTriggered: area.undo()
    }
    readonly property Action redoAction: Action {
        objectName: "redoAction"
        // Ctrl+Y and Ctrl+Shift+Z on every OS (the Shortcut below takes the second).
        text: "&Redo"; shortcut: "Ctrl+Y"
        enabled: area.canRedo && !area.readOnly
        onTriggered: area.redo()
    }
    readonly property Action cutAction: Action {
        objectName: "cutAction"
        text: "Cu&t"; shortcut: "Ctrl+X"
        enabled: !area.readOnly && area.selectedText !== ""
        onTriggered: area.cut()
    }
    readonly property Action copyAction: Action {
        objectName: "copyAction"
        text: "&Copy"; shortcut: "Ctrl+C"
        enabled: area.selectedText !== ""
        onTriggered: area.copy()
    }
    readonly property Action pasteAction: Action {
        objectName: "pasteAction"
        text: "&Paste"; shortcut: "Ctrl+V"
        enabled: !area.readOnly && area.canPaste
        onTriggered: pane.editor.paste()
    }
    readonly property Action selectAllAction: Action {
        objectName: "selectAllAction"
        text: "Select &all"; shortcut: "Ctrl+A"
        enabled: area.length > 0
        onTriggered: pane.selectAll()
    }
    readonly property Action zoomInAction: Action {
        objectName: "zoomInAction"
        text: "&Larger text"; shortcut: "Ctrl+="
        onTriggered: pane.editor.zoomIn()
    }
    readonly property Action zoomOutAction: Action {
        objectName: "zoomOutAction"
        text: "&Smaller text"; shortcut: "Ctrl+-"
        onTriggered: pane.editor.zoomOut()
    }
    readonly property Action zoomResetAction: Action {
        objectName: "zoomResetAction"
        text: "&Reset text size"; shortcut: "Ctrl+0"
        onTriggered: pane.editor.zoomReset()
    }
    Shortcut {
        sequences: ["Ctrl+Shift+Z"]
        enabled: pane.redoAction.enabled
        onActivated: pane.redoAction.trigger()
    }
    Shortcut {
        // Ctrl++ is Ctrl+Shift+= on most layouts; both zoom in.
        sequences: ["Ctrl++"]
        onActivated: pane.zoomInAction.trigger()
    }

    function focusEditor() { area.forceActiveFocus() }
    // Select all with the cursor at the start (as Tk's Ctrl+A).
    function selectAll() {
        area.forceActiveFocus()
        area.select(area.length, 0)
    }
    function palette() {
        return { chord: Theme.chord, chordInvalid: Theme.chordInvalid, directive: Theme.directive,
                 directiveInvalid: Theme.directiveInvalid, comment: Theme.comment,
                 playing: Theme.playing, editorText: Theme.editorText, editorBg: Theme.editorBg }
    }
    // The character under (x, y), in the TextArea's coordinates, or -1 past
    // the text (above or below a line, before the first character).
    // positionAt gives the nearest gap between characters; the character is
    // the one after that gap, or the one before it when (x, y) is left of it.
    function charAt(x, y) {
        var p = area.positionAt(x, y)
        var r = area.positionToRectangle(p)
        if (y < r.y || y >= r.y + r.height) return -1
        return x < r.x ? p - 1 : p
    }
    // Scroll so `start`..`end` is in view, vertically and sideways (the
    // playing chord; wrap off lets the text run past the right edge).
    function ensureVisible(start, end) {
        var r0 = area.positionToRectangle(start)
        var r1 = area.positionToRectangle(Math.max(start, end))
        var f = scroll.contentItem
        var margin = Theme.px(5)
        var maxY = Math.max(0, f.contentHeight - f.height)
        if (r0.y < f.contentY + margin)
            f.contentY = Math.max(0, r0.y - Theme.px(15))
        else if (r0.y + r0.height > f.contentY + f.height - margin)
            f.contentY = Math.min(maxY, Math.max(0, r0.y - f.height / 2))
        var maxX = Math.max(0, f.contentWidth - f.width)
        if (r0.x < f.contentX + margin)
            f.contentX = Math.max(0, r0.x - Theme.px(15))
        else if (r1.x > f.contentX + f.width - margin)
            f.contentX = Math.min(maxX, Math.max(0, r0.x - f.width / 2))
    }

    Connections {
        target: Theme
        function onDarkChanged() { pane.editor.setPalette(pane.palette()) }
    }
    Connections {
        target: pane.editor
        function onPlayingMoved(start) { pane.ensureVisible(start, pane.editor.playingEnd) }
    }

    ScrollView {
        id: scroll
        objectName: "editorScroll"
        anchors.fill: parent
        TextArea {
            id: area
            objectName: "editor"
            // The text origin on whole device pixels, also while scrolling.
            transform: SnapTranslate { target: area; extra: [scroll.contentItem.contentX, scroll.contentItem.contentY] }
            textFormat: TextEdit.PlainText
            // The configured family ("TkFixedFont": the bundled Noto Sans Mono)
            // and size; the default hinting (Theme.editorFont).
            font: Theme.editorFont(pane.editor.fontFamily, pane.editor.fontSize)
            color: Theme.editorText
            selectionColor: Theme.selection
            selectedTextColor: Theme.editorText
            placeholderText: pane.placeholder
            placeholderTextColor: Theme.blend(Theme.editorText, Theme.editorBg, 0.45)
            wrapMode: pane.editor.wordWrap ? TextEdit.Wrap : TextEdit.NoWrap
            // In a ScrollView the TextArea sizes itself to the view (wrapping)
            // or to its text, but only when one of those sizes changes: a text
            // laid out wide stays wide when wrapping comes on. Start it at the
            // view's width; it follows by itself from there.
            onWrapModeChanged: if (wrapMode !== TextEdit.NoWrap) area.width = scroll.contentItem.width
            readOnly: pane.editor.readOnly || pane.playMode
            selectByMouse: true
            persistentSelection: true
            leftPadding: Theme.editorPadX; rightPadding: Theme.gap4
            topPadding: Theme.editorPadY; bottomPadding: Theme.editorPadY
            background: null
            cursorVisible: !readOnly && activeFocus
            // A caret of whole device pixels on the device grid (the default 1-logical-px
            // caret is 1 or 2 device px at 125%, depending on the column).
            cursorDelegate: SnapLine {
                id: caret
                objectName: "caret"
                height: area.cursorRectangle.height
                color: Theme.editorText
                moved: [scroll.contentItem.contentX, scroll.contentItem.contentY]
                visible: area.cursorVisible && blinkOn
                property bool blinkOn: true
                Timer {
                    interval: 530; repeat: true
                    running: area.cursorVisible
                    onRunningChanged: caret.blinkOn = true
                    onTriggered: caret.blinkOn = !caret.blinkOn
                }
                Connections {
                    target: area
                    function onCursorPositionChanged() { caret.blinkOn = true }
                }
            }
            Component.onCompleted: pane.editor.attach(area, area.textDocument, pane.palette())

            Keys.onPressed: (event) => {
                if (event.matches(StandardKey.Paste)) {
                    // Ctrl+V, Shift+Insert: normalised by the bridge.
                    event.accepted = true
                    if (!area.readOnly) pane.editor.paste()
                } else if (event.matches(StandardKey.SelectAll)) {
                    event.accepted = true
                    pane.selectAll()
                }
            }

            // Playhead: where ▶ starts (Android's marker, new on the desktop).
            Item {
                id: playhead
                objectName: "playhead"
                readonly property int pos: pane.editor.playheadPos
                readonly property rect r: {
                    void [area.contentWidth, area.contentHeight, area.width, area.font, area.length]
                    return pos >= 0 && area.contentHeight > 0 && area.width > 0
                           ? area.positionToRectangle(pos) : Qt.rect(0, 0, 0, 0)
                }
                visible: pos >= 0
                x: r.x - Theme.gap1; y: r.y
                SnapLine { lineWidth: Theme.devW(2); height: playhead.r.height; color: Theme.accent
                           moved: [scroll.contentItem.contentX, scroll.contentItem.contentY, playhead.x] }
                Rectangle {   // the cap: a small square turned 45°
                    width: Theme.px(1.5); height: width
                    x: (Theme.px(0.5) - width) / 2; y: -width / 2
                    rotation: 45
                    color: Theme.accent
                }
            }

            // The hand over valid chords only (an I-beam elsewhere, invalid
            // chords too), also while read-only.
            HoverHandler {
                id: hover
                objectName: "editorHover"
                cursorShape: pane.overChord ? Qt.PointingHandCursor : Qt.IBeamCursor
                onPointChanged: pane.overChord = pane.editor.isChordAt(
                    pane.charAt(hover.point.position.x, hover.point.position.y))
                onHoveredChanged: if (!hovered) pane.overChord = false
            }
            // A click on a chord sounds it and moves the playhead (the session
            // decides). The second click of a double-click only selects the word.
            TapHandler {
                objectName: "chordTap"
                acceptedButtons: Qt.LeftButton
                onTapped: (eventPoint, button) => {
                    if (tapCount === 1)
                        pane.editor.tapAt(pane.charAt(eventPoint.position.x, eventPoint.position.y))
                }
            }
            TapHandler {
                acceptedButtons: Qt.RightButton
                onTapped: contextMenu.popup()
            }
            // Ctrl+wheel zooms the text, one step a notch, and doesn't scroll.
            WheelHandler {
                objectName: "zoomWheel"
                acceptedModifiers: Qt.ControlModifier
                target: null
                property real notches: 0
                onWheel: (event) => {
                    notches += event.angleDelta.y / 120
                    while (notches >= 1) { pane.editor.zoomIn(); notches -= 1 }
                    while (notches <= -1) { pane.editor.zoomOut(); notches += 1 }
                    event.accepted = true
                }
            }
            // Shift+wheel scrolls sideways (wrap off), as Tk did; Qt Quick's
            // Flickable only scrolls vertically for a vertical wheel.
            WheelHandler {
                objectName: "sidewaysWheel"
                acceptedModifiers: Qt.ShiftModifier
                target: null
                onWheel: (event) => {
                    var f = scroll.contentItem as Flickable
                    var delta = event.angleDelta.x !== 0 ? event.angleDelta.x : event.angleDelta.y
                    var step = area.cursorRectangle.height * 3 * delta / 120
                    f.contentX = Math.max(0, Math.min(f.contentWidth - f.width, f.contentX - step))
                    event.accepted = true
                }
            }
            // Middle-click pastes PRIMARY (X11, Wayland) at the pointer, normalised.
            MouseArea {
                anchors.fill: parent
                acceptedButtons: Qt.MiddleButton
                onClicked: (mouse) => {
                    if (!area.readOnly) pane.editor.pasteSelectionAt(area.positionAt(mouse.x, mouse.y))
                }
            }
            // Text dragged in from elsewhere, normalised.
            DropArea {
                anchors.fill: parent
                onEntered: (drag) => { drag.accepted = drag.hasText && !area.readOnly }
                onDropped: (drop) => {
                    if (!drop.hasText || area.readOnly) return
                    pane.editor.dropText(area.positionAt(drop.x, drop.y), drop.text)
                    drop.accept(Qt.CopyAction)
                    area.forceActiveFocus()
                }
            }
        }
    }

    // Right-click: each item enabled only when it applies.
    Menu {
        id: contextMenu
        objectName: "editorContextMenu"
        MenuItem { objectName: "menuUndo"; action: pane.undoAction }
        MenuItem { objectName: "menuRedo"; action: pane.redoAction }
        MenuSeparator { }
        MenuItem { objectName: "menuCut"; action: pane.cutAction }
        MenuItem { objectName: "menuCopy"; action: pane.copyAction }
        MenuItem { objectName: "menuPaste"; action: pane.pasteAction }
        MenuItem { objectName: "menuSelectAll"; action: pane.selectAllAction }
        onClosed: area.forceActiveFocus()
    }
}
