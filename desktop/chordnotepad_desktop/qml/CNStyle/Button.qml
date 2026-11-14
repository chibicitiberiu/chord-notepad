import QtQuick
import QtQuick.Templates as T
import CNTheme

// Every CNStyle control sets implicitWidth/implicitHeight from its background
// and content: a Templates control has zero implicit size (pitfall 3).
//
// Desktop buttons, Theme.radius corners: highlighted = accent fill
// (the one primary action), default = neutral raised with a hairline border,
// flat = no chrome until hovered.
T.Button {
    id: control
    implicitWidth: Math.max(implicitBackgroundWidth, implicitContentWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(implicitBackgroundHeight, implicitContentHeight + topPadding + bottomPadding)
    leftPadding: Theme.px(3); rightPadding: Theme.px(3)
    topPadding: Theme.gap1; bottomPadding: Theme.gap1
    spacing: Theme.gap2
    hoverEnabled: true
    font: Theme.fontMedium
    icon.width: Theme.iconSmall; icon.height: Theme.iconSmall
    icon.color: fg
    readonly property color fg: !enabled ? Theme.disabled : highlighted ? Theme.textOnAccent : Theme.text
    contentItem: IconText {
        spacing: control.spacing
        display: control.display
        iconSource: control.icon.source
        iconColor: control.icon.color
        iconSize: control.icon.width
        text: control.text
        font: control.font
        color: control.fg
    }
    background: Rectangle {
        implicitWidth: Theme.px(18)
        implicitHeight: Theme.controlHeight
        radius: Theme.radius
        color: control.highlighted
               ? (!control.enabled ? Theme.controlPressed : control.down ? Theme.accentPressed
                  : control.hovered ? Theme.accentHover : Theme.accentFill)
               : control.flat
                 ? (control.down ? Theme.pressed : control.hovered ? Theme.hover : "transparent")
                 : (control.down ? Theme.controlPressed : control.hovered ? Theme.controlHover : Theme.control)
        border.width: control.highlighted || control.flat ? 0 : Theme.hairline
        border.color: Theme.borderStrong
        FocusRing { visible: control.visualFocus }
    }
}
