package com.chg.progeresseye.util

import com.google.firebase.database.DatabaseReference
import com.google.firebase.database.FirebaseDatabase

object FirebaseRefs {
    private val db get() = FirebaseDatabase.getInstance()

    fun userRef(uid: String): DatabaseReference =
        db.reference.child("users").child(uid)

    fun planRef(uid: String): DatabaseReference =
        userRef(uid).child("plan")

    fun devicesRef(uid: String): DatabaseReference =
        userRef(uid).child("devices")

    fun deviceStatusRef(uid: String): DatabaseReference =
        userRef(uid).child("deviceStatus")

    fun heartbeatRef(uid: String): DatabaseReference =
        userRef(uid).child("heartbeat")

    fun mobileHeartbeatRef(uid: String): DatabaseReference =
        userRef(uid).child("mobileHeartbeat")

    fun mobileSessionRef(uid: String): DatabaseReference =
        userRef(uid).child("mobileSession")

    fun commandRef(uid: String, command: String): DatabaseReference =
        userRef(uid).child("commands").child(command)

    fun alertsRef(uid: String): DatabaseReference =
        userRef(uid).child("alerts")

    fun fcmTokensRef(uid: String): DatabaseReference =
        userRef(uid).child("fcmTokens")
}
