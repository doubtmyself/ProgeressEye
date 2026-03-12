package com.chg.progeresseye.data.repository

import com.chg.progeresseye.FirebaseConstants
import com.google.firebase.firestore.FirebaseFirestore
import com.google.firebase.firestore.ListenerRegistration
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * Firestore appConfig/policies 의 단일 구독자.
 * 여러 ViewModel이 adFreeModeGlobal 을 개별적으로 구독하는 대신,
 * 이 객체의 StateFlow 를 collect 한다.
 */
object PolicyRepository {

    private val _adFreeModeGlobal = MutableStateFlow(false)
    val adFreeModeGlobal: StateFlow<Boolean> = _adFreeModeGlobal.asStateFlow()

    private var listener: ListenerRegistration? = null

    /** 로그인 후 한 번 호출. 이미 리스너가 있으면 no-op. */
    @Synchronized
    fun startListening() {
        if (listener != null) return
        listener = FirebaseFirestore.getInstance(FirebaseConstants.FIRESTORE_DB)
            .collection("appConfig")
            .document("policies")
            .addSnapshotListener { snapshot, _ ->
                _adFreeModeGlobal.value = snapshot?.getBoolean("adFreeModeGlobal") == true
//                _adFreeModeGlobal.value = false
            }
    }

    /** 로그아웃 시 호출. 리스너 해제 + 상태 초기화. */
    @Synchronized
    fun reset() {
        listener?.remove()
        listener = null
        _adFreeModeGlobal.value = false
    }
}
