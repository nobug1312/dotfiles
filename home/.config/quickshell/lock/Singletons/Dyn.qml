pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io

/**
 * Wallpaper palette for the lock from the pill's matugen JSON, never sourced from on_primary_container because it can load empty and turn black.
 */
Singleton {
    readonly property string primary: adapter.primary
    readonly property string cream: adapter.cream
    readonly property string bright: adapter.bright
    readonly property string dim: adapter.dim

    FileView {
        path: (Quickshell.env("XDG_CACHE_HOME") || (Quickshell.env("HOME") + "/.cache")) + "/ricelin/colors.json"
        blockLoading: true
        watchChanges: true
        printErrors: false

        onFileChanged: reload()

        JsonAdapter {
            id: adapter
             property string primary: "#8CCFFF"
             property string cream: "#AAB4C2"
             property string bright: "#F2F5F9"
             property string dim: "#7D8999"
        }
    }
}
