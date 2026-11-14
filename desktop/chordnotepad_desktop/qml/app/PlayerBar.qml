pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import CNTheme

// The Play workspace's player bar (the mockup's PlayerBar.qml, plan steps
// E1-E3): one calm row, like a web music player.
// [title / 100 bpm · 3/4 · Am] [⏮ ( ▶ ) ⏹] [7:2 ──timeline──] [♫ Voicing ⌄ · 🎸 Instrument ⌄ | ⏲ 100% ⌄ · metronome · 🔊 ⌄]
// Narrow: the timeline shrinks first, then the title block hides into »
// (and ▶'s tooltip), then the voicing and instrument names collapse to icons.
//
// Everything shown is the session's: ToolbarState (song values, speed,
// metronome, ▶'s action), PlaybackState (status, sections),
// DocumentState (title, unsaved dot), VoicingMenuState and
// InstrumentMenuState. `player` (player_bar.py) has the texts, the
// position, the seeks and the scales; `actions` (PlaybackActions.qml) the
// shortcuts, which the buttons share.
//
// Transport: ▶ acts on press (Tk's), Shift+▶ plays from the editor's cursor,
// Space and Enter work on a focused ▶ (Shift too). ⏮ rewinds to the first
// chord and keeps playing if it was. ⏹ stops and silences ringing notes
// (also when idle, so it is never disabled); the playhead stays.
Rectangle {
    id: bar
    objectName: "playerBar"
    required property var store
    required property var player
    required property var pickers
    required property var actions
    signal goToDirective(string value)
    signal editVoicings()
    implicitHeight: Theme.playerHeight
    color: Theme.chrome
    Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: Theme.hairline; color: Theme.border }

    readonly property var tb: bar.store.states.ToolbarState
    readonly property var pb: bar.store.states.PlaybackState
    readonly property var doc: bar.store.states.DocumentState
    readonly property var vm: bar.store.states.VoicingMenuState
    readonly property var im: bar.store.states.InstrumentMenuState
    readonly property bool playing: bar.tb.play_action === "pause"
    readonly property var sections: bar.pb.sections || []
    readonly property int totalBars: bar.sections.length ? bar.sections[bar.sections.length - 1].last_bar : 0
    readonly property string title: bar.doc.display_name || ""
    readonly property bool dirty: bar.doc.is_modified === true
    readonly property real speed: bar.tb.multiplier_pct || 100
    readonly property string lockedReason: bar.vm.locked_reason || ""
    readonly property string voicingLabel: {
        for (var g of bar.vm.groups || [])
            for (var c of g) if (c.value === bar.vm.selected) return c.label
        return ""
    }
    readonly property string instrumentLabel: {
        for (var f of bar.im.families || [])
            for (var c of f.items) if (parseInt(c.value) === bar.im.current) return bar.player.instrumentName(c.label)
        return ""
    }
    readonly property string songLine: bar.tb.bpm_display + " bpm · " + bar.tb.beats + "/" + bar.tb.unit
                                       + " · " + bar.player.keyLabel(bar.tb.key || "")

    readonly property real units: width / Theme.u
    // Narrowing: the timeline shrinks to its minimum, then the title block hides
    // (title, tempo, time, key move into », and into ▶'s tooltip), then the
    // voicing / instrument names collapse to icons.
    readonly property bool titleShown: units >= 292
    readonly property bool namesShown: units >= 258

    function play(fromCursor) { bar.player.playPause(fromCursor) }
    function openSongPicker(kind, anchor) {
        if (morePop.visible) { morePop.close(); anchor = moreBtn }   // not a popup inside a popup
        songPicker.parent = anchor
        songPicker.x = 0
        songPicker.y = anchor.height + Theme.gap1
        songPicker.openFor(bar.player.songPicker(kind))
    }

    component Sep: Rectangle {
        Layout.preferredWidth: Theme.hairline
        Layout.preferredHeight: Theme.px(5)
        Layout.leftMargin: Theme.gap2; Layout.rightMargin: Theme.gap2
        color: Theme.border
    }
    // The position box fits "00:0" (tabular figures), or "000:0" for a song of
    // 100+ bars; fixed for the whole song, so nothing moves.
    TextMetrics { id: posWidth; font: Theme.fontTabular; text: (bar.totalBars >= 100 ? "000" : "00") + ":0" }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: Theme.gap4; anchors.rightMargin: Theme.gap3
        anchors.bottomMargin: Theme.hairline
        spacing: Theme.gap4

        // --- Title and the song's values (hugs its content) ---------------------------------
        ColumnLayout {
            objectName: "titleBlock"
            visible: bar.titleShown
            // Hug the text exactly (the wider of the title and the values line), so
            // the gap to ⏮ is the real visual gap; a long title elides at 60u.
            Layout.fillWidth: false
            Layout.minimumWidth: 0
            Layout.maximumWidth: Theme.px(60)
            Layout.preferredWidth: Math.ceil(Math.max(titleRow.implicitWidth, songValues.implicitWidth))
            spacing: 0
            // The title is elided by measurement (not by the Text), so the block's
            // width is the elided text's real width and the unsaved dot survives (pitfall 17).
            TextMetrics { id: titleFit; font: Theme.fontStrong; text: bar.title; elide: Text.ElideRight; elideWidth: Theme.px(52) }
            Row {
                id: titleRow
                spacing: Theme.gap1
                SText { objectName: "playerTitle"; text: titleFit.elidedText; font: Theme.fontStrong; color: Theme.text }
                SText { objectName: "playerDirty"; visible: bar.dirty; text: "•"; font: Theme.fontStrong; color: Theme.muted }
            }
            SongValues {
                id: songValues
                store: bar.store
                player: bar.player
                onGoToDirective: (v) => bar.goToDirective(v)
                onOpenPicker: (kind, anchor) => bar.openSongPicker(kind, anchor)
            }
        }

        // --- Transport -------------------------------------------------------------------------
        RowLayout {
            spacing: Theme.gap1
            IconButton {
                objectName: "prevButton"
                iconName: "skip-previous"; tip: bar.player.texts.rewind
                implicitWidth: Theme.transportButton; implicitHeight: Theme.transportButton
                icon.width: Theme.playerIcon; icon.height: Theme.playerIcon
                onClicked: bar.player.rewind()
            }
            Button {
                id: playBtn
                objectName: "playButton"
                implicitWidth: Theme.playButton; implicitHeight: Theme.playButton
                padding: 0
                focusPolicy: Qt.TabFocus
                contentItem: Item {
                    PixelIcon {
                        id: playIcon
                        name: bar.playing ? "pause" : "play"
                        size: Theme.px(6)
                        color: Theme.textOnAccent
                        anchors.centerIn: parent
                        // Centred on its ink: MDI's triangle sits 1.5/24 right of its box.
                        anchors.horizontalCenterOffset: bar.playing ? 0 : -width * 1.5 / 24
                        transform: SnapTranslate { target: playIcon }
                    }
                }
                background: Rectangle {
                    radius: width / 2
                    color: playArea.pressed ? Theme.accentPressed : playArea.containsMouse ? Theme.accentHover : Theme.accentFill
                    Rectangle {
                        visible: playBtn.visualFocus
                        anchors.fill: parent; anchors.margins: -Theme.focusWidth
                        radius: width / 2; color: "transparent"
                        border.width: Theme.focusWidth; border.color: Theme.focusRing
                    }
                }
                // On press, as Tk's; Shift: from the cursor.
                MouseArea {
                    id: playArea
                    objectName: "playArea"
                    anchors.fill: parent
                    hoverEnabled: true
                    onPressed: (m) => bar.play((m.modifiers & Qt.ShiftModifier) !== 0)
                }
                Keys.onPressed: (e) => {
                    if (e.key === Qt.Key_Space || e.key === Qt.Key_Return || e.key === Qt.Key_Enter) {
                        if (!e.isAutoRepeat) bar.play((e.modifiers & Qt.ShiftModifier) !== 0)
                        e.accepted = true
                    }
                }
                Keys.onReleased: (e) => { if (e.key === Qt.Key_Space) e.accepted = true }
                // Its own ToolTip, not the attached one: the shared tooltip keeps the
                // text it had when the hover began, and a press changes it (Play → Pause).
                ToolTip {
                    objectName: "playTip"
                    visible: playArea.containsMouse
                    delay: 600
                    text: (bar.titleShown ? "" : "<b>" + bar.title + "</b> · " + bar.songLine + "<br>")
                          + bar.player.playTooltip(bar.tb.play_action || "play")
                          + "  <font color='" + Theme.muted + "'>F5</font>"
                }
            }
            IconButton {
                objectName: "stopButton"
                iconName: "stop"; tip: bar.player.texts.stop
                implicitWidth: Theme.transportButton; implicitHeight: Theme.transportButton
                icon.width: Theme.playerIcon; icon.height: Theme.playerIcon
                onClicked: bar.store.submit("stop")
            }
        }

        // --- Timeline: takes what is left; fixed-width, tabular position -------------------
        RowLayout {
            Layout.fillWidth: true
            Layout.minimumWidth: Theme.px(40)
            spacing: Theme.gap2
            SText {
                objectName: "position"
                Layout.preferredWidth: Math.ceil(posWidth.advanceWidth)
                horizontalAlignment: Text.AlignRight      // snug against the track
                text: bar.player.position
                font: Theme.fontTabular
                color: Theme.muted
            }
            Scrubber {
                player: bar.player
                sections: bar.sections
                playing: bar.playing
                Layout.fillWidth: true
                Layout.leftMargin: Theme.px(1.5); Layout.rightMargin: Theme.px(1.5)   // room for the handle at either end
            }
        }

        // --- Everything else: one row of equal-height buttons, grouped ---------------------
        RowLayout {
            objectName: "playerRight"
            spacing: Theme.px(0.5)
            IconButton {
                id: moreBtn
                objectName: "moreButton"
                visible: !bar.titleShown
                text: "»"
                display: AbstractButton.TextOnly
                implicitWidth: Theme.playerControl; implicitHeight: Theme.playerControl
                tip: "Song: title, tempo, time and key"
                onClicked: morePop.open()
                Popup {
                    id: morePop
                    objectName: "morePopup"
                    y: parent.height + Theme.gap1
                    padding: Theme.gap3
                    contentItem: Column {
                        spacing: Theme.gap1
                        SText { text: bar.title + (bar.dirty ? "  •" : ""); font: Theme.fontStrong; color: Theme.text }
                        SongValues {
                            store: bar.store
                            player: bar.player
                            onGoToDirective: (v) => { morePop.close(); bar.goToDirective(v) }
                            onOpenPicker: (kind, anchor) => bar.openSongPicker(kind, anchor)
                        }
                    }
                }
            }
            Sep { visible: !bar.titleShown }
            // The voicing is locked while a song plays: the button is disabled,
            // so its tooltip (with the reason) hangs off this parent (pitfall 16).
            Item {
                objectName: "voicingTip"
                implicitWidth: voicingBtn.implicitWidth
                implicitHeight: voicingBtn.implicitHeight
                HoverHandler { id: voicingHover }
                ToolTip.visible: voicingHover.hovered && !voicingMenu.visible
                ToolTip.delay: 600
                ToolTip.text: "Voicing: " + bar.voicingLabel + (bar.lockedReason ? " (" + bar.lockedReason + ")" : "")
                FlatDrop {
                    id: voicingBtn
                    objectName: "voicingButton"
                    anchors.fill: parent
                    iconName: "music"
                    text: bar.voicingLabel.replace(/ - [A-G]+\)/, ")")
                    showText: bar.namesShown
                    maxTextWidth: Theme.px(30)
                    enabled: bar.lockedReason === ""
                    checked: voicingMenu.visible
                    onClicked: voicingMenu.popup(voicingBtn, 0, voicingBtn.height + Theme.gap1)
                }
            }
            FlatDrop {
                id: instrumentBtn
                objectName: "instrumentButton"
                iconName: "guitar-acoustic"
                text: bar.instrumentLabel
                showText: bar.namesShown
                maxTextWidth: Theme.px(26)
                tip: "Instrument: " + bar.instrumentLabel + " (General MIDI " + bar.im.current + ")"
                checked: instrumentMenu.visible
                onClicked: instrumentMenu.popup(instrumentBtn, 0, instrumentBtn.height + Theme.gap1)
            }
            Sep {}
            FlatDrop {
                id: speedBtn
                objectName: "speedButton"
                iconName: "speedometer"
                text: bar.player.formatSpeed(bar.speed) + "%"
                valueColor: Math.abs(bar.speed - 100) > 0.001 ? Theme.accent : Theme.text
                tip: bar.player.texts.speed
                checked: speedPop.visible
                onClicked: speedPop.visible ? speedPop.close() : speedPop.open()
                // The wheel steps 5%, middle-click resets (left clicks and hover pass through).
                MouseArea {
                    anchors.fill: parent
                    acceptedButtons: Qt.MiddleButton
                    property real notches: 0
                    onClicked: bar.store.submit("reset_multiplier")
                    onWheel: (e) => {
                        notches += e.angleDelta.y / 120
                        while (Math.abs(notches) >= 1) {
                            var dir = notches > 0 ? 1 : -1
                            notches -= dir
                            bar.player.stepSpeed(dir)
                        }
                    }
                }
                SpeedPopup { id: speedPop; y: parent.height + Theme.gap1; x: parent.width - width }
            }
            IconButton {
                objectName: "metronomeButton"
                iconName: "metronome"
                checkable: false
                checked: bar.tb.metronome === true
                implicitWidth: Theme.playerControl; implicitHeight: Theme.playerControl
                icon.width: Theme.playerIcon; icon.height: Theme.playerIcon
                onClicked: bar.actions.metronomeAction.trigger()
                tip: bar.player.texts.metronome; shortcutHint: "Ctrl+M"
            }
            FlatDrop {
                id: volumeBtn
                objectName: "volumeButton"
                iconName: bar.player.muted || bar.player.volume <= 0 ? "volume-off" : "volume"
                tip: "Volume " + (bar.player.muted ? "(muted)" : Math.round(bar.player.volume * 100) + "%") + " (wheel steps)"
                checked: volPop.visible
                onClicked: volPop.visible ? volPop.close() : volPop.open()
                MouseArea {        // the wheel steps 5% (B3's step_volume)
                    anchors.fill: parent
                    acceptedButtons: Qt.NoButton
                    property real notches: 0
                    onWheel: (e) => {
                        notches += e.angleDelta.y / 120
                        while (Math.abs(notches) >= 1) {
                            var dir = notches > 0 ? 1 : -1
                            notches -= dir
                            bar.player.stepVolume(dir)
                        }
                    }
                }
                VolumePopup { id: volPop; y: parent.height + Theme.gap1; x: parent.width - width }
            }
        }
    }

    ValuePicker {
        id: songPicker
        objectName: "songPicker"
        model: bar.pickers
        onPicked: (v) => bar.player.applySongValue(songPicker.kind, v)
    }
    VoicingMenu { id: voicingMenu; store: bar.store; onEditVoicings: bar.editVoicings() }
    InstrumentMenu { id: instrumentMenu; store: bar.store }

    // --- Speed: live (it is playback, not text) -------------------------------------------
    component SpeedPopup: Popup {
        id: sp
        objectName: "speedPopup"
        padding: Theme.gap3
        implicitWidth: Theme.px(70)
        // The box shows the value unless it is being typed in.
        function showValue() { if (!speedBox.activeFocus) speedBox.text = bar.player.formatSpeed(bar.speed) }
        function commit() {
            var t = speedBox.text.trim()
            if (t !== "" && t !== bar.player.formatSpeed(bar.speed)) bar.store.submit("set_multiplier_text", { text: t })
        }
        onOpened: { showValue(); speedBox.forceActiveFocus(); speedBox.selectAll() }   // pitfall 23
        Connections { target: bar; function onSpeedChanged() { sp.showValue() } }
        contentItem: ColumnLayout {
            spacing: Theme.gap2
            RowLayout {
                Label { text: "Speed"; font: Theme.fontStrong; Layout.fillWidth: true }
                TextField {
                    id: speedBox
                    objectName: "speedBox"
                    Layout.preferredWidth: Theme.px(18)
                    horizontalAlignment: TextInput.AlignRight
                    // "150", "150%" or "1.5x" (the core's parse_multiplier_pct).
                    Keys.onReturnPressed: { sp.commit(); selectAll() }
                    Keys.onEnterPressed: { sp.commit(); selectAll() }
                    onActiveFocusChanged: if (!activeFocus) { sp.commit(); sp.showValue() }
                }
                Label { text: "%"; color: Theme.muted }
            }
            Slider {
                objectName: "speedSlider"
                Layout.fillWidth: true
                from: 0; to: 1
                value: bar.player.speedPosition(bar.speed)
                onMoved: {
                    var pct = bar.player.speedAt(value)
                    if (pct !== bar.speed) bar.store.submit("set_multiplier_pct", { pct: pct })
                }
            }
            Flow {
                Layout.fillWidth: true
                spacing: Theme.px(0.5)
                Repeater {
                    model: bar.player.speedPresets
                    delegate: Button {
                        required property int modelData
                        objectName: "speed:" + modelData
                        text: modelData + "%"
                        flat: Math.abs(bar.speed - modelData) > 0.001
                        highlighted: !flat
                        implicitHeight: Theme.controlSmall
                        leftPadding: Theme.gap2; rightPadding: Theme.gap2
                        onClicked: bar.store.submit("set_multiplier_pct", { pct: modelData })
                    }
                }
            }
            RowLayout {
                Label { text: "12.5% to 400%. Applies while playing."; font: Theme.fontC; color: Theme.muted; wrapMode: Text.Wrap; Layout.fillWidth: true }
                Button {
                    objectName: "speedReset"
                    text: "Reset"; implicitHeight: Theme.controlSmall
                    onClicked: bar.store.submit("reset_multiplier")
                }
            }
        }
    }

    // --- Volume: the slider and mute (B3: no state; PlayerBarModel reads them back) ----
    component VolumePopup: Popup {
        objectName: "volumePopup"
        padding: Theme.gap3
        implicitWidth: Theme.px(62)
        contentItem: ColumnLayout {
            spacing: Theme.gap2
            RowLayout {
                Label { text: "Volume"; font: Theme.fontStrong; Layout.fillWidth: true }
                Label { text: bar.player.muted ? "muted" : Math.round(bar.player.volume * 100) + "%"; color: Theme.muted }
            }
            RowLayout {
                spacing: Theme.gap2
                Slider {
                    objectName: "volumeSlider"
                    Layout.fillWidth: true
                    from: 0; to: 1; value: bar.player.volume
                    onMoved: bar.player.setVolume(value)
                }
                Button {
                    objectName: "muteButton"
                    text: bar.player.muted ? "Unmute" : "Mute"
                    implicitHeight: Theme.controlSmall
                    onClicked: bar.player.setMuted(!bar.player.muted)
                }
            }
        }
    }
}
