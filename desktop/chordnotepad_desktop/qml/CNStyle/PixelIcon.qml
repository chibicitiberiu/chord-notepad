import QtQuick
import CNTheme

// A monochrome icon drawn 1:1 in device pixels: the SVG is rasterised,
// antialiased, at a whole number of device pixels (icons.py), tagged
// with the device pixel ratio, and shown at exactly that size. smooth stays on
// as a safety net: a 1:1 draw is unaffected, an accidental rescale blurs a little
// instead of stair-stepping.
// Sizes near a multiple of 12 device px snap to it, so the 24-unit grid
// lands on whole pixels (strokes don't straddle). Use it instead of
// IconImage, which blurs at a fractional ratio (pitfall 14).
Image {
    id: icon
    property string name                    // icon file name without .svg
    property url iconSource                 // or a Controls icon.source URL
    property color color: Theme.icon
    property real size: Theme.iconSize      // logical
    readonly property string resolved: name !== "" ? name
        : String(iconSource).split("/").pop().replace(/\.svg$/, "")
    readonly property int devicePx: {
        var d = Math.max(1, Math.round(size * Theme.dpr))
        var g = Math.round(d / 12) * 12
        return (g > 0 && Math.abs(g - d) <= 2) ? g : d
    }
    visible: resolved !== ""
    width: devicePx / Theme.dpr
    height: width
    smooth: true
    mipmap: false
    fillMode: Image.Stretch
    source: resolved !== "" ? "image://icons/" + resolved + "?c=" + encodeURIComponent(String(color)) + "&s=" + devicePx + "&d=" + Theme.dpr : ""
}
