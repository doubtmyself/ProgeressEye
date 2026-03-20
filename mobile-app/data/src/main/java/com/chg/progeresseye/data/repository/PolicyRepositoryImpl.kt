package com.chg.progeresseye.data.repository

import com.chg.progeresseye.domain.repository.PolicyRepository
import com.google.firebase.database.DataSnapshot
import com.google.firebase.database.DatabaseError
import com.google.firebase.database.FirebaseDatabase
import com.google.firebase.database.ValueEventListener
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import javax.inject.Inject

/**
 * Firebase Realtime Database에서 앱 전역 정책 상태를 수집하는 [PolicyRepository]의 구체화 클래스입니다.
 */
class PolicyRepositoryImpl @Inject constructor() : PolicyRepository {
    private val db = FirebaseDatabase.getInstance()
    override fun observePolicy(): Flow<Boolean> = callbackFlow {
        val ref = db.reference.child("policy").child("isAdFreeModeEnabled")
        val listener = ref.addValueEventListener(object : ValueEventListener {
            override fun onDataChange(snapshot: DataSnapshot) {
                trySend(snapshot.getValue(Boolean::class.java) ?: false)
            }
            override fun onCancelled(error: DatabaseError) {}
        })
        awaitClose { ref.removeEventListener(listener) }
    }
    override fun reset() {}
}
