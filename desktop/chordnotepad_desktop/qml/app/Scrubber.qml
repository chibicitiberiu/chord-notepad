pragma ComponentBehavior: Bound
import QtQuick
import CNTheme

// The timeline in song time (the mockup's Scrubber.qml, plan step E1): one
// rounded segment per section of the song (PlaybackState.sections, B2), its
// width in proportion to its bars, small gaps between them, like YouTube's
// chapter segments. The fill runs through the segments to the bars played
// (PlayerBarModel.played: the beat under way counts). The hovered segment
// thickens and a preview names the section with the position and the length
// ("verse 2 · 53:1 / 56"), kept inside the track. A click or a drag seeks
// (PlayerBarModel.seekBar); a gap maps to the boundary bar.
//
// Seeking while a song plays restarts it, so a drag then only previews (the
// handle follows the pointer) and seeks where it is let go; idle, the
// playhead follows the drag (that is silent and cheap).
Item {
    id: scrub
    objectName: "timeline"
    required property var player
    property var sections: []          // [{label, first_bar, last_bar, repeat}]
    property bool playing: false
    readonly property int bars: sections.length ? sections[sections.length - 1].last_bar : 0
    readonly property int gap: Theme.px(0.75)
    // The segments, rebuilt only when they change: every ping publishes the
    // sections again, and a new model would recreate the delegates (losing
    // the hover and the press on them).
    property var segs: []
    function layout() {
        var s = sections, out = [], n = s.length
        var total = n ? s[n - 1].last_bar : 0
        if (!n || total <= 0) {
            out = [{ name: "", bar: 1, bars: 1, x: 0, w: width }]
        } else {
            var avail = Math.max(1, width - (n - 1) * gap), x = 0
            for (var i = 0; i < n; ++i) {
                var count = s[i].last_bar - s[i].first_bar + 1
                var w = count / total * avail
                out.push({ name: scrub.sectionName(s[i]), bar: s[i].first_bar, bars: count, x: x, w: w })
                x += w + gap
            }
        }
        if (JSON.stringify(out) !== JSON.stringify(segs)) segs = out
    }
    onSectionsChanged: layout()
    onWidthChanged: layout()
    onGapChanged: layout()
    Component.onCompleted: layout()
    readonly property bool active: bars > 0
    property int hoverSeg: -1
    property int dragBar: 0            // the bar a drag while playing will seek to
    property int lastSeek: 0
    implicitHeight: Theme.px(4)

    // A loop back to the top of the song is labelled "@start" by the core.
    function sectionName(s) { return s.label === "@start" ? "start" : s.label }
    function xForBars(b) {             // bars from the start (0..bars) -> x on the track
        for (var i = 0; i < segs.length; ++i) {
            var g = segs[i]
            if (b <= g.bar - 1 + g.bars) return g.x + Math.max(0, b - (g.bar - 1)) / g.bars * g.w
        }
        return width
    }
    function segAt(x) {                // a gap belongs to the segment after it
        for (var i = 0; i < segs.length; ++i) if (x < segs[i].x + segs[i].w) return i
        return segs.length - 1
    }
    function barAt(x) {
        var g = segs[segAt(x)]
        if (x < g.x) return g.bar                       // in the gap: the boundary bar
        return Math.max(1, Math.min(bars, g.bar + Math.floor((x - g.x) / Math.max(1, g.w) * g.bars)))
    }
    function seek(bar) {
        if (bar === lastSeek) return
        lastSeek = bar
        scrub.player.seekBar(bar)
    }
    readonly property real shown: area.pressed && playing && dragBar > 0 ? dragBar - 1 : player.played

    Repeater {
        // By count, so a relayout (a new width) moves the delegates instead of
        // making new ones.
        model: scrub.segs.length
        delegate: Item {
            id: seg
            required property int index
            readonly property var g: scrub.segs[index] || ({ x: 0, w: 0 })
            readonly property bool hot: scrub.active && area.containsMouse && scrub.hoverSeg === index
            objectName: "seg" + index
            x: g.x; width: g.w
            height: hot ? Theme.scrubberHeight * 2 : Theme.scrubberHeight
            anchors.verticalCenter: parent.verticalCenter
            Behavior on height { NumberAnimation { duration: Theme.fast } }
            Rectangle { anchors.fill: parent; radius: height / 2; color: Theme.borderStrong }
            Rectangle {   // the part already played
                width: Math.max(0, Math.min(seg.width, scrub.xForBars(scrub.shown) - seg.x))
                height: parent.height; radius: height / 2
                color: Theme.accentFill
                visible: scrub.active && width > 0
            }
        }
    }
    Rectangle {  // handle
        objectName: "timelineHandle"
        width: Theme.px(3); height: width; radius: width / 2
        x: scrub.xForBars(scrub.shown) - width / 2
        anchors.verticalCenter: parent.verticalCenter
        color: Theme.control
        border.width: Theme.hairline
        border.color: Theme.accent
        visible: scrub.active && (area.containsMouse || area.pressed || scrub.playing)
    }
    MouseArea {             // preventStealing: the drag stays ours (pitfall 5)
        id: area
        objectName: "timelineArea"
        anchors.fill: parent
        anchors.topMargin: -Theme.gap2; anchors.bottomMargin: -Theme.gap2   // easier to hit than the thin track
        enabled: scrub.active
        hoverEnabled: true
        preventStealing: true
        cursorShape: Qt.PointingHandCursor
        onPositionChanged: (m) => {
            scrub.hoverSeg = scrub.segAt(m.x)
            if (!pressed) return
            if (scrub.playing) scrub.dragBar = scrub.barAt(m.x)
            else scrub.seek(scrub.barAt(m.x))
        }
        onPressed: (m) => {
            scrub.lastSeek = 0
            scrub.dragBar = scrub.barAt(m.x)
            scrub.seek(scrub.dragBar)
        }
        onReleased: (m) => {
            if (scrub.playing) scrub.seek(scrub.barAt(m.x))
            scrub.dragBar = 0
        }
        onExited: scrub.hoverSeg = -1
    }
    Rectangle {   // seek preview
        objectName: "timelinePreview"
        visible: scrub.active && area.containsMouse
        readonly property int bar: scrub.barAt(area.mouseX)
        readonly property string name: scrub.hoverSeg >= 0 && scrub.hoverSeg < scrub.segs.length
                                       ? scrub.segs[scrub.hoverSeg].name : ""
        readonly property string text: (name ? name + " · " : "") + bar + ":1 / " + scrub.bars
        x: Math.max(-Theme.gap2, Math.min(scrub.width - width + Theme.gap2, area.mouseX - width / 2))
        y: -height - Theme.gap2
        z: 20
        width: tip.implicitWidth + 2 * Theme.gap2
        height: tip.implicitHeight + Theme.gap1
        radius: Theme.radiusSmall
        color: Theme.popup
        border.width: Theme.hairline; border.color: Theme.border
        SText {
            id: tip
            anchors.centerIn: parent
            text: parent.text
            font: Theme.fontTabularCaption
            color: Theme.text
        }
    }
}
