package com.chg.progeresseye.data.repository

import com.chg.progeresseye.data.util.FirebaseConstants
import com.chg.progeresseye.domain.repository.PolicyRepository
import com.google.firebase.firestore.FirebaseFirestore
import com.google.firebase.firestore.ListenSource
import com.google.firebase.firestore.MetadataChanges
import com.google.firebase.firestore.SnapshotListenOptions
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import timber.log.Timber
import javax.inject.Inject

/**
 * Firestore appConfig/policies 문서에서 전역 광고 제거 정책을 수집하는 [PolicyRepository] 구현체입니다.
 */
class PolicyRepositoryImpl @Inject constructor() : PolicyRepository {
    private val firestore = FirebaseFirestore.getInstance(FirebaseConstants.FIRESTORE_DB)

    override fun observePolicy(): Flow<Boolean> = callbackFlow {
        Timber.d("[PolicyRepo] observePolicy callbackFlow 시작")
        val docRef = firestore.collection("appConfig").document("policies")
        val options = SnapshotListenOptions.Builder()
            .setMetadataChanges(MetadataChanges.INCLUDE)
            .setSource(ListenSource.DEFAULT)
            .build()
        val registration = docRef.addSnapshotListener(options) { snapshot, error ->
            if (error != null) {
                Timber.e("[PolicyRepo] snapshot error: ${error.message}")
                return@addSnapshotListener
            }
            val value = snapshot?.getBoolean("adFreeModeGlobal") ?: false
            Timber.d("[PolicyRepo] onSnapshot: adFreeModeGlobal=$value")
            trySend(value)
        }
        awaitClose { registration.remove() }
    }

    override fun reset() {}
}
