import QtQuick
import QtQuick.Templates as T
import CNTheme

// Tooltip on the popup surface with a hairline border (VS Code style),
// 600 ms delay; rich text allowed for a muted shortcut.
// A disabled control gets no hover events, so a tooltip that explains why it
// is disabled hangs off a HoverHandler, not `hovered` (pitfall 16).
T.ToolTip {
    onOpened: Theme.bumpLayout()     // re-snap the text inside
    id: control
    x: parent ? (parent.width - implicitWidth) / 2 : 0
    y: parent ? parent.height + Theme.gap1 : 0
    implicitWidth: Math.min(Math.max(implicitBackgroundWidth, implicitContentWidth + leftPadding + rightPadding), Theme.px(90))
    implicitHeight: Math.max(implicitBackgroundHeight, implicitContentHeight + topPadding + bottomPadding)
    margins: Theme.gap2
    leftPadding: Theme.gap2; rightPadding: Theme.gap2
    topPadding: Theme.gap1; bottomPadding: Theme.gap1
    delay: 600
    timeout: 8000
    popupType: T.Popup.Item
    closePolicy: T.Popup.CloseOnEscape | T.Popup.CloseOnPressOutsideParent | T.Popup.CloseOnReleaseOutsideParent
    font: Theme.fontS
    contentItem: SText {
        text: control.text
        font: control.font
        wrapMode: Text.Wrap
        color: Theme.text
        textFormat: Text.StyledText
    }
    background: PopupBackground { radius: Theme.radiusSmall }
}
