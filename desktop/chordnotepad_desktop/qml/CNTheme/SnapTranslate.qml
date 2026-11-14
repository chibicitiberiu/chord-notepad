import QtQuick

// Moves its target so the target's scene origin sits on whole device pixels.
// Native text at a fractional device x gets uneven spacing and misshapen
// glyphs at 125%; snapping fixes it (Tibi's font test). Recomputed on the
// target's own geometry changes, the window's ratio, and Theme.layoutRevision
// (bumped, once per frame at most, on resize, splitter and sidebar changes,
// popups and workspace switches), so it doesn't map every frame. `extra` lists
// anything else that moves the target (e.g. the editor's scroll position).
Translate {
    id: snap
    property Item target
    property var extra
    readonly property point d: {
        // Read for the binding's dependencies only (void keeps qmllint quiet).
        void [Theme.layoutRevision, Theme.dpr, snap.extra]
        if (!target || !target.parent) return Qt.point(0, 0)
        void [target.width, target.height]
        // The parent's mapping of the target's position: excludes this transform.
        var p = target.parent.mapToItem(null, target.x, target.y)
        return Qt.point(Theme.snapOffset(p.x), Theme.snapOffset(p.y))
    }
    x: d.x
    y: d.y
}
