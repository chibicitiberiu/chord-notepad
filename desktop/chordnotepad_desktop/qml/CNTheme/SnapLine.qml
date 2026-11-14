import QtQuick

// A thin vertical line (caret, drop caret, playhead) a whole number of device
// pixels wide and on the device-pixel grid, so it is the same width wherever it
// lands at 125% / 150%. `moved` lists anything that shifts it on screen
// (e.g. the editor's scroll), so the snap is recomputed. A 1 px Rectangle
// would come out 1 or 2 device pixels wide at 125% (pitfall 13).
Item {
    id: line
    property color color: Theme.text
    property real lineWidth: Theme.caretWidth
    property var moved
    width: lineWidth
    readonly property real offset: {
        void [line.moved, line.x, line.y, line.width, Theme.dpr]    // dependencies only
        var p = line.mapToItem(null, 0, 0)
        return Theme.snapOffset(p.x)
    }
    Rectangle {
        objectName: "snapLineRect"
        x: line.offset
        width: line.lineWidth
        height: line.height
        color: line.color
        antialiasing: false
    }
}
