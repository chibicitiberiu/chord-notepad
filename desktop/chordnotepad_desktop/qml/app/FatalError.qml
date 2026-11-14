import QtQuick

// "Chord Notepad couldn't start." (error_presenter.show_fatal_error). Plain
// QtQuick only: start-up may have failed before the style or the theme could
// load, so this window uses neither.
Window {
    id: win
    required property string message
    required property string appName
    title: win.appName
    visible: true
    width: Math.max(420, body.implicitWidth + 48)
    height: body.implicitHeight + ok.height + 72
    color: "#ffffff"
    Text {
        id: body
        objectName: "fatalMessage"
        x: 24; y: 24
        width: Math.min(implicitWidth, 560)
        text: win.message
        textFormat: Text.PlainText
        wrapMode: Text.WrapAtWordBoundaryOrAnywhere
        color: "#1d1f24"
    }
    Rectangle {
        id: ok
        objectName: "fatalOk"
        anchors.right: parent.right; anchors.bottom: parent.bottom
        anchors.margins: 16
        width: 88; height: 30; radius: 4
        color: okArea.pressed ? "#1f5fbf" : "#2b6fd6"
        focus: true
        Keys.onReturnPressed: win.close()
        Keys.onEnterPressed: win.close()
        Keys.onEscapePressed: win.close()
        Text { anchors.centerIn: parent; text: "OK"; color: "#ffffff" }
        MouseArea { id: okArea; anchors.fill: parent; onClicked: win.close() }
    }
}
