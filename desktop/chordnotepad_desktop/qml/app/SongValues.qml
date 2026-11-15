pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import CNTheme

// The song's values above the timeline in the player bar (plan step E2):
// "100 bpm · 3/4 · Am", what the song starts with (ToolbarState).
// - The tempo is TempoReadout (Tk's scrubber when it can be changed). At a
//   speed other than 100% the tempo heard follows it, muted:
//   "95 bpm → 143 bpm (150%)" (Tibi, 2026-11-15).
// - The time and the key open D5's value picker with the toolbar's choices
//   (openPicker; a pick sends set_time_signature / set_key). Both are locked
//   while a song plays (not while paused), with Tk's tooltips.
// - A value the song sets with a directive is a link to it instead: muted,
//   underlined on hover, "Set by {key: D} in the song · click to go there",
//   and a click asks for goToDirective (the player bar switches to Edit and
//   puts the cursor in the directive, found in the live text).
Row {
    id: sv
    required property var store
    required property var player
    signal goToDirective(string value)
    signal openPicker(string kind, Item anchor)
    readonly property var tb: sv.store.states.ToolbarState
    readonly property bool playing: sv.tb.play_action === "pause"
    spacing: Theme.gap1

    function setByTip(directive) {
        return sv.player.setByTooltip("<font face='" + Theme.monoFont + "' color='" + Theme.directive + "'>"
                                      + directive + "</font>") + " · click to go there"
    }

    // A time or key value: a link to its directive, a picker opener, or
    // locked while playing. Its tooltip hangs off a HoverHandler (pitfall 16).
    component SongValue: FocusScope {
        id: val
        property string kind
        property string value
        property string setBy
        property string tip
        readonly property bool linked: val.setBy !== ""
        readonly property bool locked: !val.linked && sv.playing
        function activate() {
            if (val.linked) sv.goToDirective(val.kind)
            else if (!val.locked) sv.openPicker(val.kind, val)
        }
        implicitWidth: lbl.implicitWidth + 2 * Theme.gap1
        implicitHeight: lbl.implicitHeight + Theme.px(0.5)
        activeFocusOnTab: !val.locked
        Keys.onReturnPressed: val.activate()
        Keys.onEnterPressed: val.activate()
        Keys.onSpacePressed: val.activate()
        Rectangle {
            anchors.fill: parent
            radius: Theme.radiusSmall
            color: !val.linked && !val.locked && hov.hovered ? Theme.hover : "transparent"
            border.width: val.activeFocus ? Theme.hairline : 0
            border.color: Theme.accent
        }
        SText {
            id: lbl
            anchors.centerIn: parent
            text: val.value
            font: val.linked && hov.hovered ? Theme.fontSLink : Theme.fontS
            color: val.locked ? Theme.muted : val.linked ? (hov.hovered ? Theme.text : Theme.muted) : Theme.text
        }
        HoverHandler {
            id: hov
            cursorShape: val.locked ? Qt.ArrowCursor : Qt.PointingHandCursor
        }
        TapHandler { onTapped: val.activate() }
        ToolTip.visible: hov.hovered
        ToolTip.delay: 600
        ToolTip.text: val.linked ? sv.setByTip(val.setBy) : val.tip
    }
    component Dot: SText {
        text: "·"; font: Theme.fontS; color: Theme.muted
        anchors.verticalCenter: parent.verticalCenter
    }

    Row {
        anchors.verticalCenter: parent.verticalCenter
        spacing: Theme.px(0.5)
        TempoReadout {
            id: tempo
            store: sv.store
            player: sv.player
            anchors.verticalCenter: parent.verticalCenter
            onGoToDirective: sv.goToDirective("tempo")
        }
        SText {
            text: "bpm"; font: Theme.fontS; color: Theme.muted
            rightPadding: effective.visible ? 0 : Theme.gap1   // as far from the dot as the chips' padding
            anchors.verticalCenter: parent.verticalCenter
        }
        SText {
            id: effective
            objectName: "effectiveTempo"
            readonly property string heard: sv.player.effectiveTempo(tempo.shown, sv.tb.multiplier_pct || 100)
            text: "→ " + heard
            visible: heard !== ""
            leftPadding: Theme.gap1; rightPadding: Theme.gap1
            font: Theme.fontS; color: Theme.muted
            anchors.verticalCenter: parent.verticalCenter
        }
    }
    Dot { }
    SongValue {
        objectName: "timeValue"
        anchors.verticalCenter: parent.verticalCenter
        kind: "time"
        value: (sv.tb.beats || 4) + "/" + (sv.tb.unit || 4)
        setBy: sv.tb.time_set_by || ""
        tip: sv.player.texts.time
    }
    Dot { }
    SongValue {
        objectName: "keyValue"
        anchors.verticalCenter: parent.verticalCenter
        kind: "key"
        value: sv.player.keyLabel(sv.tb.key || "")
        setBy: sv.tb.key_set_by || ""
        tip: sv.player.texts.key
    }
}
