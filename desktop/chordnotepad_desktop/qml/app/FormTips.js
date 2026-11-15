.pragma library

// Tooltip texts of the Settings window's fields: the help, then the field's
// range as a muted line ("Range 5–24", SettingsModel's range_text), then
// Tk's "⚠ message" when the field is wrong (voicings_page.py
// _apply_field_mark: "{base}\n\n⚠ {message}"). CNStyle's ToolTip shows
// styled text, so the texts are escaped and their line breaks kept.

function escape(text) {
    return String(text).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
                       .replace(/\n/g, "<br>")
}

// `range` and `muted` (the theme's muted colour) are optional.
function tip(help, error, range, muted) {
    var text = help ? escape(help) : ""
    if (range)
        text += (text ? "<br>" : "") + "<font color='" + muted + "'>" + escape(range) + "</font>"
    if (error)
        text += (text ? "<br><br>" : "") + escape("⚠ " + error)
    return text
}
