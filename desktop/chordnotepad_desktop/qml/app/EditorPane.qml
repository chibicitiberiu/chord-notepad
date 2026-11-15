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
// drag and drop (the DropArea, on top of the TextArea's own drop). A dragged
// file isn't text: Main.qml's DropArea opens it, and the editor turns it down.
//
// Drag and drop from the sidebars (`dnd`, Main.qml's; the mockup's): a palette
// tile or an identifier chord dragged over the text shows the drop caret
// where it would go in, snapped off the middle of a word or directive
// (EditorBridge.dropPosition, the core's snippets.drop_offset); the drop is
// insert_snippet there (one undo step, spaced, a directive's value
// selected). While read-only (playing, paused, the Play workspace) there is
// no caret and the pointer is the no-drop sign.
//
// Directives (plan steps D4, D5): the hover card 450 ms after the pointer
// rests on one (EditorBridge.hintAt), the caret's hint in the status bar
// (`status`, StatusBarModel: told when the caret may have moved), and the ▾
// chip after a directive's value with its ValuePicker (`pickers`,
// ValuePickerModel). The chip is for the directive under the pointer, kept
// over a sticky region (the directive, the chip and the gap between them)
// and for 300 ms after the pointer leaves it (pitfall 19), else for the
// caret's directive; never while read-only (playing, the Play workspace).
// Alt+Down opens the caret's picker.
//
// The find bar (FindBar.qml, find_bar.py) sits under the text: Ctrl+F,
// Ctrl+H, F3 / Shift+F3; its matches are tinted in the text and the
// selected one takes the find colour instead of the selection's.
Rectangle {
    id: pane
    objectName: "editorPane"
    required property var editor
    required property var status
    required property var pickers
    // The drag from the sidebars (Main.qml): its `accepting` is set here.
    required property var dnd
    property int dropPos: -1           // where a dragged tile or chord would go in, or -1
    // FilesModel: a dragged file isn't text to insert (Main.qml's DropArea opens it).
    property var files: null
    // "Type or paste a song here", shown while the text is empty.
    property string placeholder: ""
    // Play workspace: read-only (Ctrl+1 or the pencil goes back to Edit).
    property bool playMode: false
    property alias area: area
    property bool overChord: false
    // Alt is down (the pointer over a chord is then the I-beam, not the hand).
    property bool altHeld: false
    color: Theme.editorBg

    // --- The hover card (D4) -------------------------------------------------------
    property var hint: ({})            // the card shown (EditorBridge.hintAt), or {}
    property int hoverPos: -1          // the character under the pointer, or -1
    function showHintAt(pos) {
        if (picker.visible || pos < 0) return
        var h = pane.editor.hintAt(pos)
        if (h.start === undefined) { pane.hint = ({}); return }
        var r = area.positionToRectangle(h.start)
        h.x = r.x; h.y = r.y + r.height + Theme.gap1
        pane.hint = h
    }
    function hideHint() { hintTimer.stop(); pane.hint = ({}) }
    Timer { id: hintTimer; interval: 450; onTriggered: pane.showHintAt(pane.hoverPos) }

    // --- The ▾ value picker (D5) ----------------------------------------------------
    // The chip's target: the hovered directive while the pointer is over the
    // sticky region or within the grace period, else the caret's.
    property var sticky: ({})
    readonly property var caretPicker: pane.pickers.caretPicker
    readonly property var pickDir: area.readOnly ? ({})
                                   : sticky.end !== undefined ? sticky
                                   : caretPicker.end !== undefined ? caretPicker : ({})
    property var pickerFor: ({})
    property int hoverPickPos: -2      // the character the hover target was looked up for
    property var hoverPick: ({})
    function hoverTarget(pos) {
        if (pos !== pane.hoverPickPos) {
            pane.hoverPickPos = pos
            pane.hoverPick = pos >= 0 ? pane.pickers.pickerAt(pos) : ({})
        }
        return pane.hoverPick
    }
    // The directive, the chip and the strip between them, a little wider.
    function inChipRegion(x, y) {
        if (sticky.end === undefined) return false
        var r0 = area.positionToRectangle(sticky.start)
        var m = Theme.px(1.5)
        return x >= r0.x - m && x <= pickBtn.x + pickBtn.width + m
               && y >= r0.y - m && y <= r0.y + r0.height + m
    }
    Timer {
        id: chipGrace
        objectName: "chipGrace"
        interval: 300
        onTriggered: if (!picker.visible && !pickBtn.hovered) pane.sticky = ({})
    }
    function openPicker(d) {
        if (d.end === undefined || area.readOnly) return
        pane.pickerFor = d
        pane.hideHint()
        var r = area.positionToRectangle(d.end)
        picker.x = Math.max(0, r.x - Theme.px(8)); picker.y = r.y + r.height + Theme.gap1
        picker.openFor(d)
    }
    function closePicker() { picker.close(); pane.sticky = ({}); pane.hideHint() }
    function replaceValue(v) {
        pane.pickers.apply(pane.pickerFor, v)     // one undo step; the caret goes after the }
        area.forceActiveFocus()
    }
    // Alt+Down, and Edit › Change value…: the picker of the directive value
    // at the caret (off elsewhere and while read-only).
    readonly property Action pickerAction: Action {
        objectName: "pickerAction"
        text: "C&hange value…"; shortcut: "Alt+Down"
        enabled: !area.readOnly && pane.caretPicker.end !== undefined && !picker.visible
        onTriggered: pane.openPicker(pane.caretPicker)
    }
    // The caret may have moved, or the text under it changed: the status
    // bar's hint (150 ms later) and the caret's picker.
    // Both ends of the selection may move at once: one look afterwards.
    property bool selectionPending: false
    function selectionMoved() {
        if (pane.selectionPending) return
        pane.selectionPending = true
        Qt.callLater(function () { pane.selectionPending = false; pane.editor.selectionMoved() })
    }
    function caretTouched() {
        pane.status.schedule()
        pane.pickers.refreshCaret()
    }

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
    // Find and replace (the bar under the text, FindBar.qml).
    readonly property Action findAction: Action {
        objectName: "findAction"
        text: "&Find…"; shortcut: "Ctrl+F"
        onTriggered: findBar.open(false)
    }
    readonly property Action replaceAction: Action {
        objectName: "replaceAction"
        // In Play the text is only read: the bar opens on Find.
        text: "R&eplace…"; shortcut: "Ctrl+H"
        onTriggered: findBar.open(true)
    }
    readonly property Action findNextAction: Action {
        objectName: "findNextAction"
        text: "Find &next"; shortcut: "F3"
        onTriggered: pane.findAgain(false)
    }
    readonly property Action findPreviousAction: Action {
        objectName: "findPreviousAction"
        text: "Find pre&vious"; shortcut: "Shift+F3"
        onTriggered: pane.findAgain(true)
    }
    // Line operations (one undo step each, the session's commands over
    // text_ops): refused while the text is read-only, as typing is.
    function lineOp(command, extra) {
        if (area.readOnly) { pane.status.refuseEdit(); return }
        pane.editor.lineOp(command, extra || ({}))
    }
    readonly property Action duplicateAction: Action {
        objectName: "duplicateAction"
        text: "&Duplicate line or selection"; shortcut: "Ctrl+D"
        enabled: !area.readOnly
        onTriggered: pane.lineOp("duplicate_lines")
    }
    readonly property Action deleteLineAction: Action {
        objectName: "deleteLineAction"
        text: "Delete l&ine"; shortcut: "Ctrl+Shift+K"
        enabled: !area.readOnly
        onTriggered: pane.lineOp("delete_lines")
    }
    // Ctrl+Shift+Up/Down, as Kate: Alt+Down is the ▾ value picker's.
    readonly property Action moveUpAction: Action {
        objectName: "moveUpAction"
        text: "&Move line up"; shortcut: "Ctrl+Shift+Up"
        enabled: !area.readOnly
        onTriggered: pane.lineOp("move_lines", { offset: -1 })
    }
    readonly property Action moveDownAction: Action {
        objectName: "moveDownAction"
        text: "Move line do&wn"; shortcut: "Ctrl+Shift+Down"
        enabled: !area.readOnly
        onTriggered: pane.lineOp("move_lines", { offset: 1 })
    }
    // Comments are // to the end of the line (the parser's); indenting is a tab per line.
    readonly property Action toggleCommentAction: Action {
        objectName: "toggleCommentAction"
        text: "Toggle c&omment"; shortcut: "Ctrl+/"
        enabled: !area.readOnly
        onTriggered: pane.lineOp("toggle_comment")
    }
    // Tab and Shift+Tab in the text (Keys below); no window shortcut, so
    // Tab still moves the focus everywhere else. The menus show the keys.
    readonly property Action indentAction: Action {
        objectName: "indentAction"
        text: "Indent lines"
        enabled: !area.readOnly
        onTriggered: { area.forceActiveFocus(); pane.lineOp("indent_lines", { outdent: false }) }
    }
    readonly property Action unindentAction: Action {
        objectName: "unindentAction"
        text: "Unindent lines"
        enabled: !area.readOnly
        onTriggered: { area.forceActiveFocus(); pane.lineOp("indent_lines", { outdent: true }) }
    }
    // Select line: the selection's lines whole, one more on each repeat (also while read-only).
    readonly property Action selectLineAction: Action {
        objectName: "selectLineAction"
        text: "Select &line"; shortcut: "Ctrl+L"
        enabled: area.length > 0
        onTriggered: { area.forceActiveFocus(); pane.editor.selectLine() }
    }
    readonly property Action goToLineAction: Action {
        objectName: "goToLineAction"
        text: "&Go to line…"; shortcut: "Ctrl+G"
        onTriggered: findBar.openGoToLine()
    }
    // Overwrite mode: the Insert key, in the text (the menus show the key).
    readonly property Action overwriteAction: Action {
        id: overwrite
        objectName: "overwriteAction"
        text: "&Overwrite mode"
        checkable: true
        checked: area.overwriteMode
        onTriggered: {
            area.overwriteMode = !area.overwriteMode
            overwrite.checked = Qt.binding(function () { return area.overwriteMode })
            area.forceActiveFocus()
        }
    }
    // F3 with the bar closed finds the last query again; with none yet, the bar opens.
    function findAgain(backward) {
        if (!pane.editor.finder.findAgain(backward)) findBar.open(false)
    }
    property alias findBar: findBar
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

    // The keys to the text, unless a dialog is open: a menu that opened it
    // closes after it (its onClosed would take the keys from the dialog),
    // and a deferred call may run while it is up.
    function focusEditor() { if (!pane.editor.modalPopupOpen(Overlay.overlay)) area.forceActiveFocus() }
    // Whether a key would change the text (typing, deleting, a new line, a paste or cut).
    function editsKey(event) {
        if (event.matches(StandardKey.Paste) || event.matches(StandardKey.Cut)) return true
        if (event.key === Qt.Key_Backspace || event.key === Qt.Key_Delete || event.key === Qt.Key_Return
                || event.key === Qt.Key_Enter || event.key === Qt.Key_Tab || event.key === Qt.Key_Backtab)
            return true
        // The line operations' keys (their actions are off while read-only, so the keys come here).
        var lineKeys = [[Qt.Key_D, Qt.ControlModifier], [Qt.Key_K, Qt.ControlModifier | Qt.ShiftModifier],
                        [Qt.Key_Slash, Qt.ControlModifier],
                        [Qt.Key_Up, Qt.ControlModifier | Qt.ShiftModifier],
                        [Qt.Key_Down, Qt.ControlModifier | Qt.ShiftModifier]]
        var held = event.modifiers & (Qt.ControlModifier | Qt.ShiftModifier | Qt.AltModifier | Qt.MetaModifier)
        if (lineKeys.some(function (k) { return k[0] === event.key && k[1] === held })) return true
        var mods = event.modifiers & ~(Qt.ShiftModifier | Qt.KeypadModifier)
        return mods === Qt.NoModifier && event.text !== "" && event.text.charCodeAt(0) >= 32
    }
    // Select all, the caret at the end as in other editors (so End, Shift+Up
    // and the rest go on from there; Tk put it at the start), the view kept.
    function selectAll() {
        area.forceActiveFocus()
        pane.holdView()
        area.relocking = true
        area.select(0, area.length)
        area.relocking = false
        pane.restoreView()
    }

    // --- Keys the TextArea doesn't do (or not as other editors do) ------------------
    // Put the caret at `pos`, or with `extend` move the selection's moving end there.
    function moveCaret(pos, extend) {
        if (extend) area.moveCursorSelection(pos, TextEdit.SelectCharacters)
        else area.cursorPosition = pos
    }
    // Page Up / Page Down: the caret a viewport (less a line) up or down, on
    // the column it had before the first of a run of page moves, and the
    // view with it, so the caret stays where it is on screen.
    property real pageX: -1
    property bool paging: false
    function pageMove(dir, extend) {
        var f = scroll.contentItem
        var r = area.cursorRectangle
        var line = Math.max(1, r.height)
        var page = Math.max(line, Math.floor((f.height - line) / line) * line)
        if (pane.pageX < 0) pane.pageX = r.x
        // Within the text's lines (positionAt above the first gives the text's start).
        var y = Math.max(area.topPadding + line / 2,
                         Math.min(area.topPadding + area.contentHeight - line / 2, r.y + line / 2 + dir * page))
        var target = area.positionAt(pane.pageX + 1, y)
        f.contentY = Math.max(0, Math.min(f.contentHeight - f.height, f.contentY + dir * page))
        pane.paging = true
        pane.moveCaret(target, extend)
        pane.paging = false
    }
    // Ctrl+Up / Ctrl+Down: the view a line, the caret where it is.
    function scrollLines(n) {
        var f = scroll.contentItem
        f.contentY = Math.max(0, Math.min(f.contentHeight - f.height,
                                          f.contentY + n * area.cursorRectangle.height))
    }
    function palette() {
        return { chord: Theme.chord, chordInvalid: Theme.chordInvalid, directive: Theme.directive,
                 directiveInvalid: Theme.directiveInvalid, comment: Theme.comment,
                 playing: Theme.playing, editorText: Theme.editorText, editorBg: Theme.editorBg,
                 findMatch: Theme.findMatch, occurrence: Theme.occurrence }
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
        pane.releaseView()
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

    // Keep the scroll position across a lock change or a workspace switch:
    // the TextArea follows its caret (when it moves, and when a new size
    // re-wraps the text), which is the user's to move, not ours. For a
    // moment after the change (the move to the other workspace's host lays
    // the editor out again a frame or two later) the view is put back
    // whenever it moves; scrolling to the playing chord, or a caret that
    // really moved, ends that.
    property point heldView: Qt.point(0, 0)
    property bool holding: false
    function holdView() {
        if (!pane.holding)
            pane.heldView = Qt.point(scroll.contentItem.contentX, scroll.contentItem.contentY)
        pane.holding = true
        viewHold.restart()
    }
    function restoreView() {
        if (!pane.holding) return
        var f = scroll.contentItem
        var x = Math.max(0, Math.min(pane.heldView.x, f.contentWidth - f.width))
        var y = Math.max(0, Math.min(pane.heldView.y, f.contentHeight - f.height))
        if (f.contentX !== x) f.contentX = x
        if (f.contentY !== y) f.contentY = y
    }
    // To the other workspace's host (Main.qml), the view kept.
    function moveTo(host) {
        if (pane.parent === host) return
        pane.holdView()
        pane.parent = host
        pane.restoreView()
    }
    function releaseView() { pane.holding = false; viewHold.stop() }
    Timer { id: viewHold; interval: 200; onTriggered: pane.holding = false }
    Connections {
        target: scroll.contentItem
        function onContentXChanged() { pane.restoreView() }
        function onContentYChanged() { pane.restoreView() }
        function onContentHeightChanged() { pane.restoreView() }
    }

    Connections {
        target: Theme
        function onDarkChanged() { pane.editor.setPalette(pane.palette()) }
    }
    Connections {
        target: pane.editor
        function onPlayingMoved(start) { pane.ensureVisible(start, pane.editor.playingEnd) }
        // A click in the chord sheet or on the seek bar: show the playhead's chord.
        function onRevealRequested(pos) { pane.ensureVisible(pos, pos) }
        // Another document: show its first line (the bridge put the caret
        // there; the view may have followed the text's end first).
        function onDocumentReset() {
            pane.releaseView()
            Qt.callLater(function () {
                scroll.contentItem.contentX = 0
                scroll.contentItem.contentY = 0
            })
        }
        // The text changed (not only its highlighting): the card and the
        // sticky target were placed for the old text.
        function onTextChanged() {
            pane.hideHint()
            if (!picker.visible) pane.sticky = ({})
            pane.hoverPickPos = -2
            pane.caretTouched()
        }
    }

    FontMetrics { id: editorMetrics; font: area.font }

    ScrollView {
        id: scroll
        objectName: "editorScroll"
        anchors.top: parent.top; anchors.left: parent.left; anchors.right: parent.right
        anchors.bottom: findBar.top
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
            // The find bar's selected match shows in the find colour.
            selectionColor: pane.editor.finder.currentSelected ? Theme.findCurrent : Theme.selection
            selectedTextColor: Theme.editorText
            placeholderText: pane.placeholder
            placeholderTextColor: Theme.blend(Theme.editorText, Theme.editorBg, 0.45)
            wrapMode: pane.editor.wordWrap ? TextEdit.Wrap : TextEdit.NoWrap
            // In a ScrollView the TextArea sizes itself to the view (wrapping)
            // or to its text, but only when one of those sizes changes: a text
            // laid out wide stays wide when wrapping comes on. Start it at the
            // view's width; it follows by itself from there.
            onWrapModeChanged: if (wrapMode !== TextEdit.NoWrap) area.width = scroll.contentItem.width
            // Read-only while playing or paused, and in Play. Set by hand, not
            // bound: TextEdit moves the caret to the end of the text whenever
            // readOnly changes, so the caret and the selection are put back.
            // The view stays where it was too: the TextArea scrolls to the
            // caret whenever it moves, so playback stopping, Play or Edit
            // would jump to it (pane.holdView).
            readonly property bool locked: pane.editor.readOnly || pane.playMode
            property bool relocking: false
            onLockedChanged: {
                pane.holdView()
                area.relocking = true
                var caret = area.cursorPosition
                var anchor = caret === area.selectionStart ? area.selectionEnd : area.selectionStart
                area.readOnly = locked
                area.select(anchor, caret)
                area.relocking = false
                pane.restoreView()
                if (locked) pane.closePicker()      // a song started, or Play
            }
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
                // Overwrite mode: a block over the character the next key replaces.
                Rectangle {
                    objectName: "overwriteCaret"
                    visible: area.overwriteMode
                    x: caret.offset
                    width: {
                        void [area.cursorPosition, area.text, area.font, area.width]
                        var r0 = area.cursorRectangle
                        var r1 = area.positionToRectangle(Math.min(area.length, area.cursorPosition + 1))
                        return r1.y === r0.y && r1.x > r0.x ? r1.x - r0.x : editorMetrics.averageCharacterWidth
                    }
                    height: caret.height
                    color: Qt.rgba(Theme.editorText.r, Theme.editorText.g, Theme.editorText.b, 0.28)
                }
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
            Component.onCompleted: {
                area.readOnly = area.locked
                pane.editor.attach(area, area.textDocument, pane.palette())
            }
            onCursorPositionChanged: {
                if (!pane.paging) pane.pageX = -1
                pane.caretTouched()
                // A caret the user (or an edit) moved: the view follows it again.
                if (!area.relocking) pane.releaseView()
            }
            onActiveFocusChanged: {
                if (activeFocus) pane.caretTouched()
                else pane.altHeld = false      // Alt+Tab: the release goes to another window
            }
            // The find bar's "3 of 7" follows the selection.
            onSelectionStartChanged: pane.selectionMoved()
            onSelectionEndChanged: pane.selectionMoved()
            Keys.onReleased: (event) => {
                if (event.key === Qt.Key_Alt) pane.altHeld = false
                pane.status.schedule()
            }

            Keys.onPressed: (event) => {
                if (event.key === Qt.Key_Alt) pane.altHeld = true
                // Typing into the text a song locks: the status bar says why (Q9).
                if (area.readOnly && pane.editsKey(event)) pane.status.refuseEdit()
                var mods = event.modifiers & ~Qt.KeypadModifier
                var shift = (mods & Qt.ShiftModifier) !== 0
                var plain = (mods & ~Qt.ShiftModifier) === Qt.NoModifier
                var ctrl = (mods & ~Qt.ShiftModifier) === Qt.ControlModifier
                if ((event.key === Qt.Key_Return || event.key === Qt.Key_Enter)
                        && mods !== Qt.NoModifier && (plain || ctrl)) {
                    // Ctrl+Enter and Shift+Enter are a new line too (Qt does
                    // nothing for the first, and the second would put a line
                    // separator, not a newline, in the text).
                    event.accepted = true
                    if (!area.readOnly) pane.editor.typeNewline()
                } else if (event.key === Qt.Key_Home && plain) {
                    // Home: the first non-blank character, then the line's start.
                    event.accepted = true
                    pane.moveCaret(pane.editor.homePosition(area.cursorPosition), shift)
                } else if (event.key === Qt.Key_End && mods === Qt.NoModifier
                           && area.selectionStart !== area.selectionEnd) {
                    // End over a selection: the caret at the selection's end
                    // (the later of its two ends), not at the line's end.
                    event.accepted = true
                    pane.moveCaret(area.selectionEnd, false)
                } else if ((event.key === Qt.Key_PageDown || event.key === Qt.Key_PageUp) && plain) {
                    event.accepted = true
                    pane.pageMove(event.key === Qt.Key_PageDown ? 1 : -1, shift)
                } else if ((event.key === Qt.Key_Up || event.key === Qt.Key_Down) && mods === Qt.ControlModifier) {
                    event.accepted = true
                    pane.scrollLines(event.key === Qt.Key_Down ? 1 : -1)
                } else if (event.key === Qt.Key_Tab && mods === Qt.NoModifier
                           && /[\n\u2029]/.test(area.selectedText)) {
                    // Tab over several lines indents them (else it types a tab).
                    event.accepted = true
                    pane.lineOp("indent_lines", { outdent: false })
                } else if (event.key === Qt.Key_Backtab) {
                    // Shift+Tab unindents the selection's lines, or the caret's.
                    event.accepted = true
                    pane.lineOp("indent_lines", { outdent: true })
                } else if (event.key === Qt.Key_Insert && mods === Qt.NoModifier) {
                    // Insert: overwrite mode on or off (the status bar shows OVR).
                    event.accepted = true
                    area.overwriteMode = !area.overwriteMode
                } else if (event.key === Qt.Key_Escape && mods === Qt.NoModifier && findBar.shown) {
                    event.accepted = true
                    findBar.close()
                } else if (event.matches(StandardKey.Paste)) {
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
                    // Not past the end: a new, shorter song arrives before the
                    // session moves the playhead onto it (Qt warns "out of range").
                    return pos >= 0 && pos <= area.length && area.contentHeight > 0 && area.width > 0
                           ? area.positionToRectangle(pos) : Qt.rect(0, 0, 0, 0)
                }
                visible: pos >= 0 && pos <= area.length
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
            // chords too, and over a chord while Alt is held: Alt+click and
            // Alt+drag select its text), also while read-only.
            // The hover card and the chip's sticky target follow the pointer too.
            HoverHandler {
                id: hover
                objectName: "editorHover"
                cursorShape: pane.overChord && !pane.altHeld ? Qt.PointingHandCursor : Qt.IBeamCursor
                onPointChanged: {
                    pane.altHeld = (hover.point.modifiers & Qt.AltModifier) !== 0
                    var px = hover.point.position.x, py = hover.point.position.y
                    var pos = pane.charAt(px, py)
                    pane.overChord = pane.editor.isChordAt(pos)
                    // Over the chip, the picker, or the strip to the chip: keep the
                    // target (the chip overlaps the next character, which may
                    // belong to another directive). Else retarget, or start the
                    // grace period.
                    if (pickBtn.hovered || picker.visible || pane.inChipRegion(px, py)) {
                        chipGrace.stop()
                        var t0 = pane.hoverTarget(pos)
                        if (t0.end !== undefined && t0.start === pane.sticky.start) pane.sticky = t0
                    } else {
                        var t = pane.hoverTarget(pos)
                        if (t.end !== undefined) { pane.sticky = t; chipGrace.stop() }
                        else if (pane.sticky.end !== undefined && !chipGrace.running) chipGrace.start()
                    }
                    if (pickBtn.hovered) { pane.hideHint(); return }
                    // The card goes when the pointer leaves its directive; a new
                    // one shows once the pointer rests on a character. (Qt Quick
                    // sends the handler the same point again whenever the scene
                    // changes under it, the caret's blink too: that isn't a move.)
                    if (pane.hint.start !== undefined && !(pos >= pane.hint.start && pos < pane.hint.end))
                        pane.hint = ({})
                    if (pos !== pane.hoverPos) {
                        pane.hoverPos = pos
                        hintTimer.restart()
                    }
                }
                onHoveredChanged: if (!hovered) {
                    pane.overChord = false
                    pane.hoverPos = -1
                    if (!picker.visible) { pane.hideHint(); chipGrace.restart() }
                }
            }
            // Clicks on chords (every one plays, none selects; Alt+click is
            // text) are text_mouse.py's. This handler only updates the status
            // bar and hides the hover card.
            TapHandler {
                objectName: "chordTap"
                acceptedButtons: Qt.LeftButton
                onTapped: pane.status.schedule()
                // A click hides the hover card.
                onPressedChanged: if (pressed) pane.hideHint()
            }
            TapHandler {
                acceptedButtons: Qt.RightButton
                onTapped: contextMenu.popup()
            }
            // Ctrl+wheel zooms the text, one step a notch, and doesn't scroll.
            // Both wheel handlers take the touchpad too: on Wayland Qt tags every
            // pointer event, a mouse wheel's included, with the seat's touchpad
            // device, and a WheelHandler only takes the mouse by default.
            WheelHandler {
                objectName: "zoomWheel"
                acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
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
                acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
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
            // No shape of its own: a MouseArea has the arrow by default, and a
            // child's shape wins over the hover handler's I-beam (pitfall 28).
            MouseArea {
                anchors.fill: parent
                acceptedButtons: Qt.MiddleButton
                cursorShape: undefined
                onClicked: (mouse) => {
                    if (!area.readOnly) pane.editor.pasteSelectionAt(area.positionAt(mouse.x, mouse.y))
                }
            }
            // The ▾ value picker, right after the directive's closing brace.
            AbstractButton {
                id: pickBtn
                objectName: "pickChip"
                readonly property rect r: {
                    void [area.contentWidth, area.contentHeight, area.width, area.font, area.length]
                    return pickBtn.placed ? area.positionToRectangle(pane.pickDir.end) : Qt.rect(0, 0, 0, 0)
                }
                readonly property bool placed: pane.pickDir.end !== undefined && pane.pickDir.end <= area.length
                                               && area.contentHeight > 0
                visible: placed
                x: r.x + Theme.px(0.25); y: r.y
                width: Theme.px(3.5); height: r.height
                hoverEnabled: true
                focusPolicy: Qt.NoFocus
                z: 5
                onClicked: pane.openPicker(pane.pickDir)
                onHoveredChanged: if (!hovered) chipGrace.restart()
                ToolTip.visible: hovered && !picker.visible
                ToolTip.delay: 500
                ToolTip.text: "Pick a value  <font color='" + Theme.muted + "'>Alt+Down</font>"
                background: Rectangle {
                    radius: Theme.radiusSmall
                    color: pickBtn.down ? Theme.controlPressed : pickBtn.hovered ? Theme.controlHover : Theme.popup
                    border.width: Theme.hairline
                    border.color: pickBtn.hovered ? Theme.borderStrong : Theme.border
                }
                contentItem: Item {
                    id: chevronBox
                    PixelIcon {
                        anchors.centerIn: chevronBox
                        name: "chevron-down"
                        size: Theme.px(3.5)
                        color: Theme.directive
                    }
                }
            }
            ValuePicker {
                id: picker
                model: pane.pickers
                onPicked: (v) => pane.replaceValue(v)
                onClosed: { chipGrace.restart(); pane.focusEditor() }
            }
            HintCard {
                hint: pane.hint
                visible: pane.hint.start !== undefined
                x: Math.max(Theme.gap2, pane.hint.x || 0)
                y: pane.hint.y || 0
            }

            // Text dragged in from elsewhere, normalised; a tile or chord
            // from the sidebars (Drag.keys "snippet") where the drop caret is.
            DropArea {
                objectName: "editorDrop"
                anchors.fill: parent
                function fromSidebar(d) { return d.keys.indexOf("snippet") >= 0 }
                function isFile(d) { return pane.files !== null && d.hasUrls && pane.files.hasFiles(d.urls) }
                function track(d) {
                    pane.dropPos = area.readOnly ? -1 : pane.editor.dropPosition(area.positionAt(d.x, d.y))
                    pane.dnd.accepting = !area.readOnly
                }
                onEntered: (drag) => {
                    if (fromSidebar(drag)) track(drag)
                    else drag.accepted = drag.hasText && !area.readOnly && !isFile(drag)
                }
                onPositionChanged: (drag) => { if (fromSidebar(drag)) track(drag) }
                onExited: { pane.dropPos = -1; pane.dnd.accepting = false }
                onDropped: (drop) => {
                    if (fromSidebar(drop)) {
                        var p = pane.dropPos
                        pane.dropPos = -1
                        if (!area.readOnly && p >= 0 && pane.editor.dropSnippet(p, pane.dnd.snippet)) {
                            drop.accept()
                            pane.focusEditor()
                        }
                        return
                    }
                    if (!drop.hasText || area.readOnly || isFile(drop)) return
                    pane.editor.dropText(area.positionAt(drop.x, drop.y), drop.text)
                    drop.accept(Qt.CopyAction)
                    area.forceActiveFocus()
                }
            }
            // The drop caret: where a dragged tile or chord would go in.
            SnapLine {
                objectName: "dropCaret"
                readonly property rect r: pane.dropPos >= 0 && pane.dropPos <= area.length
                                          ? area.positionToRectangle(pane.dropPos) : Qt.rect(0, 0, 0, 0)
                visible: pane.dropPos >= 0
                x: r.x - width / 2; y: r.y
                lineWidth: Theme.devW(2); height: r.height
                color: Theme.accent
                moved: [(scroll.contentItem as Flickable).contentX, (scroll.contentItem as Flickable).contentY]
                z: 6
            }
        }
    }

    // Find, Replace and Go to line, under the text.
    FindBar {
        id: findBar
        finder: pane.editor.finder
        canReplace: !pane.playMode
        anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
        height: implicitHeight
        onClosed: pane.focusEditor()
    }

    // Right-click: each item enabled only when it applies (the edits not while
    // the text is read-only). Undo, Redo | Cut, Copy, Paste, Select all |
    // Find, Replace, Go to line | Toggle comment, Duplicate, Delete line.
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
        MenuSeparator { }
        MenuItem { objectName: "menuFind"; action: pane.findAction }
        MenuItem { objectName: "menuReplace"; action: pane.replaceAction }
        MenuItem { objectName: "menuGoToLine"; action: pane.goToLineAction }
        MenuSeparator { }
        MenuItem { objectName: "menuToggleComment"; action: pane.toggleCommentAction }
        MenuItem { objectName: "menuDuplicate"; action: pane.duplicateAction }
        MenuItem { objectName: "menuDeleteLine"; action: pane.deleteLineAction }
        onClosed: pane.focusEditor()
    }
}
