package com.chg.progeresseye.data.repository

import com.chg.progeresseye.FirebaseConstants
import com.google.firebase.firestore.FirebaseFirestore
import com.google.firebase.firestore.ListenerRegistration
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import timber.log.Timber

/**
 * Firestore users/{uid}.plan 의 단일 구독자.
 * DashboardViewModel 과 SettingsViewModel 이 각자 구독하는 대신
 * 이 객체의 StateFlow 를 collect 한다.
 */
object UserPlanRepository {

    private val _userPlan = MutableStateFlow("free")
    val userPlan: StateFlow<String> = _userPlan.asStateFlow()

    private var listener: ListenerRegistration? = null

    /** 로그인 후 한 번 호출. 이미 리스너가 있으면 no-op. */
    @Synchronized
    fun startListening(uid: String) {
        if (listener != null) return
        listener = FirebaseFirestore.getInstance(FirebaseConstants.FIRESTORE_DB)
            .collection("users")
            .document(uid)
            .addSnapshotListener { snapshot, error ->
                if (error != null) {
                    Timber.e(error, "UserPlanRepository: plan listen error")
                    return@addSnapshotListener
                }
                _userPlan.value = snapshot?.getString("plan")?.lowercase() ?: "free"
            }
    }

    /** 로그아웃 시 호출. 리스너 해제 + 상태 초기화. */
    @Synchronized
    fun reset() {
        listener?.remove()
        listener = null
        _userPlan.value = "free"
    }
}
