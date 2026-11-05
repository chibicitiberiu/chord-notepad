# R8 rules for the release build (both flavours), on top of
# proguard-android-optimize.txt and the rules the libraries ship: Chaquopy's
# plugin adds its own (keeps com.chaquo.python.** and the kotlin.jvm.functions
# classes its proxies use), and kotlinx.serialization, Play Billing, AndroidX
# and Compose bring theirs in their jars.
#
# What's left is the Kotlin that Python reaches by name through Chaquopy
# (docs/ANDROID.md, "Bridge contract"). Chaquopy wraps a Java object as its
# runtime class and finds methods by reflection, so a renamed or removed
# method only fails when Python calls it, on the device. BridgeR8RulesTest
# checks these rules against the classes and against the Python that calls them.

# Python calls event_sink.onEvent(type_name, json) for every state and event
# (chordnotepad_android/host.py).
-keep interface com.tibich.chordnotepad.bridge.EventSink { *; }

# Python calls readText, writeText, writeBytes, isAvailable, recent,
# addRecent, setMaxRecent, describe and rename on the document store
# (chordnotepad_android/android_store.py).
-keep interface com.tibich.chordnotepad.bridge.DocumentStoreBridge { *; }

# The objects Python gets are the implementations (RepositoryEventSink,
# SafDocumentStore), and Chaquopy looks the methods up on that class, so
# their public methods keep their names too, not only the interfaces'.
-keepclassmembers class * implements com.tibich.chordnotepad.bridge.EventSink {
    public <methods>;
}
-keepclassmembers class * implements com.tibich.chordnotepad.bridge.DocumentStoreBridge {
    public <methods>;
}

# android_store.py tells a provider without rename support apart by the
# exception's simple class name (RENAME_UNSUPPORTED), so the class keeps its
# name and isn't merged into DocumentStoreException.
-keep class com.tibich.chordnotepad.bridge.RenameUnsupportedException { *; }

# Line numbers and a fixed source file name in stack traces, so a crash from
# a release build can be retraced with its mapping.txt (Play does this with
# the mapping inside the AAB; docs/RELEASE.md, "Each Android release").
-keepattributes SourceFile,LineNumberTable
-renamesourcefileattribute SourceFile
