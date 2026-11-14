import QtQuick
import QtQuick.Templates as T
import CNTheme

// A popup can only take focus once it is open: call forceActiveFocus() in
// onOpened, not when asking it to open (pitfall 23).
T.Popup {
    onOpened: Theme.bumpLayout()     // re-snap the text inside
    implicitWidth: Math.max(implicitBackgroundWidth, implicitContentWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(implicitBackgroundHeight, implicitContentHeight + topPadding + bottomPadding)
    padding: Theme.gap3
    popupType: T.Popup.Item
    font: Theme.font
    background: PopupBackground { }
}
