pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import CNTheme

// The Play workspace's player bar (the mockup's PlayerBar.qml, plan steps
// E1-E3): one calm row, like a web music player.
// [⏮ ( ▶ ) ⏹] [   100 bpm · 3/4 · Am      ] [♫ Voicing ⌄ · 🎸 Instrument ⌄ | ⏲ 100% ⌄ · metronome · 🔊 ⌄]
//              [7:2 ──────timeline───────]
// The song's values sit centred on a row above the timeline (Tibi,
// 2026-11-15: no title there, the window and the tab have it), so they
// never have to hide. Narrow: the timeline shrinks to a comfortable width,
// then the voicing and instrument names collapse to icons, then the
// timeline shrinks further.
//
// Everything shown is the session's: ToolbarState (song values, speed,
// metronome, ▶'s action), PlaybackState (status, sections),
// VoicingMenuState and
// InstrumentMenuState. `player` (player_bar.py) has the texts, the
// position, the seeks and the scales; `actions` (PlaybackActions.qml) the
// shortcuts, which the buttons share.
//
// Transport: ▶ acts on press (Tk's), Shift+▶ plays from the editor's cursor,
// Space and Enter work on a focused ▶ (Shift too). ⏮ rewinds to the first
// chord and keeps playing if it was. ⏹ stops, puts the playhead back on the
// first chord and silences ringing notes (also when idle, so it is never
// disabled).
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
    readonly property var im: bar.store.states.InstrumentMenuState
    readonly property bool playing: bar.tb.play_action === "pause"
    readonly property var sections: bar.pb.sections || []
    readonly property int totalBars: bar.sections.length ? bar.sections[bar.sections.length - 1].last_bar : 0
    readonly property real speed: bar.tb.multiplier_pct || 100
    readonly property string instrumentLabel: {
        for (var f of bar.im.families || [])
            for (var c of f.items) if (parseInt(c.value) === bar.im.current) return bar.player.instrumentName(c.label)
        return ""
    }

    readonly property real units: width / Theme.u
    // Narrowing, measured from what the parts need (the values, the names and
    // the font all vary): the timeline gives way down to timelineEasy, then
    // the voicing / instrument names collapse to icons, then the timeline
    // goes on down to timelineMin.
    readonly property real timelineEasy: Theme.px(40)
    readonly property real timelineMin: Theme.px(22)
    readonly property real namesWidth: voicingBtn.textWidth + instrumentBtn.textWidth
    // Set by fitNames(), not bound: the right group's width depends on it, and a
    // binding would loop (the computation takes the names out again, so one
    // deferred pass settles).
    property bool namesShown: true
    function fitNames() {
        // The right group with icon-only names, whatever is shown now.
        var rightIcons = playerRight.implicitWidth - (bar.namesShown ? bar.namesWidth : 0)
        // The timeline's room with the names collapsed.
        var room = bar.width - mainRow.anchors.leftMargin - mainRow.anchors.rightMargin
                   - 2 * mainRow.spacing - transport.implicitWidth - rightIcons
                   - position.Layout.preferredWidth - timelineRow.spacing
        var shown = room - bar.namesWidth >= bar.timelineEasy
        if (shown !== bar.namesShown) bar.namesShown = shown
    }
    onWidthChanged: Qt.callLater(bar.fitNames)
    onNamesWidthChanged: Qt.callLater(bar.fitNames)
    Connections {
        target: playerRight
        function onImplicitWidthChanged() { Qt.callLater(bar.fitNames) }
    }
    Component.onCompleted: Qt.callLater(bar.fitNames)

    function play(fromCursor) { bar.player.playPause(fromCursor) }
    function openSongPicker(kind, anchor) {
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
        id: mainRow
        anchors.fill: parent
        anchors.leftMargin: Theme.gap4; anchors.rightMargin: Theme.gap3
        anchors.bottomMargin: Theme.hairline
        spacing: Theme.gap4

        // --- Transport -------------------------------------------------------------------------
        RowLayout {
            id: transport
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
                    text: bar.player.playTooltip(bar.tb.play_action || "play")
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
        // --- The song's values, the timeline under them -----------------------------------
        ColumnLayout {
            objectName: "middle"
            Layout.fillWidth: true
            // The timeline at its smallest (with the handle's room at either
            // end), or the values, whichever needs more.
            Layout.minimumWidth: Math.max(position.Layout.preferredWidth + timelineRow.spacing + bar.timelineMin
                                          + scrubber.Layout.leftMargin + scrubber.Layout.rightMargin,
                                          songValues.implicitWidth)
            spacing: Theme.gap1
            SongValues {
                id: songValues
                objectName: "songValues"
                Layout.alignment: Qt.AlignHCenter
                z: 1        // over the timeline's hit area, which reaches up past the track
                store: bar.store
                player: bar.player
                onGoToDirective: (v) => bar.goToDirective(v)
                onOpenPicker: (kind, anchor) => bar.openSongPicker(kind, anchor)
            }
            RowLayout {
                id: timelineRow
                Layout.fillWidth: true
                spacing: Theme.gap2
                SText {
                    id: position
                    objectName: "position"
                    Layout.preferredWidth: Math.ceil(posWidth.advanceWidth)
                    horizontalAlignment: Text.AlignRight      // snug against the track
                    text: bar.player.position
                    font: Theme.fontTabular
                    color: Theme.muted
                }
                Scrubber {
                    id: scrubber
                    player: bar.player
                    sections: bar.sections
                    playing: bar.playing
                    Layout.fillWidth: true
                    Layout.leftMargin: Theme.px(1.5); Layout.rightMargin: Theme.px(1.5)   // room for the handle at either end
                }
            }
        }

        // --- Everything else: one row of equal-height buttons, grouped ---------------------
        RowLayout {
            id: playerRight
            objectName: "playerRight"
            spacing: Theme.px(0.5)
            VoicingButton {
                id: voicingBtn
                objectName: "voicingTip"
                store: bar.store
                showText: bar.namesShown
                onEditVoicings: bar.editVoicings()
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
                tip: "Music " + (bar.player.muted ? "(muted)" : Math.round(bar.player.volume * 100) + "%") + " (wheel steps)"
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

    // --- Volume: the music's slider and mute, and the metronome's own level under them
    // (B3: no state; PlayerBarModel reads them back) ---------------------------------
    component VolumePopup: Popup {
        objectName: "volumePopup"
        padding: Theme.gap3
        implicitWidth: Theme.px(62)
        contentItem: ColumnLayout {
            spacing: Theme.gap2
            RowLayout {
                Label { text: "Music"; font: Theme.fontStrong; Layout.fillWidth: true }
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
                    id: muteBtn
                    objectName: "muteButton"
                    text: bar.player.muted ? "Unmute" : "Mute"
                    implicitHeight: Theme.controlSmall
                    onClicked: bar.player.setMuted(!bar.player.muted)
                }
            }
            // The click's own level: the music slider above leaves it alone
            // (Tibi, 2026-11-17); mute silences both.
            RowLayout {
                Layout.topMargin: Theme.gap1
                Label { text: "Metronome"; font: Theme.fontStrong; Layout.fillWidth: true }
                Label {
                    objectName: "metronomeVolumeText"
                    text: Math.round(bar.player.metronomeVolume * 100) + "%"; color: Theme.muted
                }
            }
            RowLayout {
                spacing: Theme.gap2
                Slider {
                    objectName: "metronomeVolumeSlider"
                    Layout.fillWidth: true
                    from: 0; to: 1; value: bar.player.metronomeVolume
                    onMoved: bar.player.setMetronomeVolume(value)
                }
                Item { implicitWidth: muteBtn.width }      // the sliders line up
            }
        }
    }
}
