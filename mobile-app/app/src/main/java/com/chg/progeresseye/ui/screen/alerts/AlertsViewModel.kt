package com.chg.progeresseye.ui.screen.alerts

import android.util.Log
import androidx.lifecycle.ViewModel
import com.chg.progeresseye.data.model.AlertItem
import com.chg.progeresseye.data.model.AlertType
import com.google.firebase.auth.FirebaseAuth
import com.google.firebase.database.DataSnapshot
import com.google.firebase.database.DatabaseError
import com.google.firebase.database.DatabaseReference
import com.google.firebase.database.FirebaseDatabase
import com.google.firebase.database.ValueEventListener
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update

// ═════════════════════════════════════════════════════════
// AlertsViewModel — RTDB listener for user alerts
// ═════════════════════════════════════════════════════════

class AlertsViewModel : ViewModel() {
    private val auth = FirebaseAuth.getInstance()
    private val db = FirebaseDatabase.getInstance()

    private val _alerts = MutableStateFlow<List<AlertItem>>(emptyList())
    val alerts: StateFlow<List<AlertItem>> = _alerts.asStateFlow()

    private val _isLoading = MutableStateFlow(true)
    val isLoading: StateFlow<Boolean> = _isLoading.asStateFlow()

    private var alertsRef: DatabaseReference? = null
    private var alertsListener: ValueEventListener? = null
    private val readAlertIds = mutableSetOf<String>()

    init {
        startListening()
    }

    private fun startListening() {
        if (alertsListener != null) return

        val uid = auth.currentUser?.uid
        if (uid == null) {
            _isLoading.value = false
            _alerts.value = emptyList()
            return
        }

        alertsRef = db.reference.child("users").child(uid).child("alerts")
        alertsListener = object : ValueEventListener {
            override fun onDataChange(snapshot: DataSnapshot) {
                val parsedAlerts = snapshot.children
                    .mapNotNull { parseAlert(it) }
                    .sortedByDescending { it.timestamp }
                    .map { alert ->
                        if (readAlertIds.contains(alert.id)) alert.copy(isRead = true) else alert
                    }

                _alerts.value = parsedAlerts
                _isLoading.value = false
            }

            override fun onCancelled(error: DatabaseError) {
                Log.e(TAG, "alerts:onCancelled", error.toException())
                _isLoading.value = false
            }
        }
        alertsRef?.addValueEventListener(alertsListener!!)
    }

    private fun parseAlert(snapshot: DataSnapshot): AlertItem? {
        val id = snapshot.key ?: return null
        val type = when (snapshot.child("type").getValue(String::class.java)) {
            "completion" -> AlertType.COMPLETION
            "stall" -> AlertType.STALL
            "image_change" -> AlertType.IMAGE_CHANGE
            "offline" -> AlertType.OFFLINE
            else -> return null
        }

        val title = snapshot.child("title").getValue(String::class.java) ?: "ProgressEye"
        val body = snapshot.child("body").getValue(String::class.java) ?: return null
        val deviceId = snapshot.child("deviceId").getValue(String::class.java) ?: ""
        val timestamp = snapshot.child("ts").getValue(Long::class.java) ?: 0L

        return AlertItem(
            id = id,
            type = type,
            title = title,
            body = body,
            deviceName = deviceId,
            timestamp = timestamp,
            isRead = readAlertIds.contains(id),
        )
    }

    /** Mark a single alert as read. */
    fun markAsRead(alertId: String) {
        readAlertIds.add(alertId)
        _alerts.update { list ->
            list.map { if (it.id == alertId) it.copy(isRead = true) else it }
        }
    }

    /** Delete a single alert from RTDB + local list. */
    fun deleteAlert(alertId: String) {
        alertsRef?.child(alertId)?.removeValue()
        readAlertIds.remove(alertId)
        _alerts.update { list -> list.filter { it.id != alertId } }
    }

    /** Clear all alerts. */
    fun clearAll() {
        readAlertIds.clear()
        alertsRef?.removeValue()
        _alerts.value = emptyList()
    }

    override fun onCleared() {
        alertsListener?.let { listener ->
            alertsRef?.removeEventListener(listener)
        }
        alertsListener = null
        super.onCleared()
    }

    companion object {
        private const val TAG = "AlertsViewModel"
    }
}
