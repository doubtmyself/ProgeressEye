# Add project specific ProGuard rules here.
# You can control the set of applied configuration files using the
# proguardFiles setting in build.gradle.
#
# For more details, see
#   http://developer.android.com/guide/developing/tools/proguard.html

# If your project uses WebView with JS, uncomment the following
# and specify the fully qualified class name to the JavaScript interface
# class:
#-keepclassmembers class fqcn.of.javascript.interface.for.webview {
#   public *;
#}

# Uncomment this to preserve the line number information for
# debugging stack traces.
-keepattributes SourceFile,LineNumberTable

# If you keep the line number information, uncomment this to
# hide the original source file name.
-renamesourcefileattribute SourceFile

# Keep rules for identity/auth stack used during sign-in.
# This app relies on Credential Manager + GoogleId + Firebase Auth.
-keep class androidx.credentials.** { *; }
-keep interface androidx.credentials.** { *; }

-keep class com.google.android.libraries.identity.googleid.** { *; }
-keep class com.google.android.gms.auth.api.identity.** { *; }

# Firebase auth/runtime classes referenced across reflection/service boundaries.
-keep class com.google.firebase.auth.** { *; }
-keep class com.google.firebase.database.** { *; }
-keep class com.google.firebase.firestore.** { *; }

# Keep Play Core update classes used by in-app update flow.
-keep class com.google.android.play.core.** { *; }

# WorkManager + Room (WorkDatabase is created via reflection by Room runtime).
# Prevent stripping/renaming of generated Room implementations.
-keep class androidx.work.impl.WorkDatabase { *; }
-keep class androidx.work.impl.WorkDatabase_Impl { *; }
-keep class * extends androidx.room.RoomDatabase
-keep class **_Impl { *; }

# Keep app entry points and ViewModel used by Compose/lifecycle reflection paths.
-keep class com.chg.progeresseye.MainActivity { *; }
-keep class com.chg.progeresseye.auth.AuthViewModel { *; }
