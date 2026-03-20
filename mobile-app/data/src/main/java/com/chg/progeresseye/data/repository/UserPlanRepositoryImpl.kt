package com.chg.progeresseye.data.repository

import com.chg.progeresseye.data.util.FirebaseConstants
import com.chg.progeresseye.data.util.FirebaseRefs
import com.chg.progeresseye.domain.repository.UserPlanRepository
import com.google.firebase.database.DataSnapshot
import com.google.firebase.database.DatabaseError
import com.google.firebase.database.DatabaseReference
import com.google.firebase.database.FirebaseDatabase
import com.google.firebase.database.ValueEventListener
import com.google.firebase.firestore.FirebaseFirestore
import com.google.firebase.firestore.SetOptions
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.tasks.await
import timber.log.Timber
import javax.inject.Inject

/**
 * Firebase Realtime Database에서 사용자의 구독 플랜 정보를 조회하는 구현체
 */
class UserPlanRepositoryImpl @Inject constructor() : UserPlanRepository {
    private val db = FirebaseDatabase.getInstance()
    private var planRef: DatabaseReference? = null
    private var listenerRegistration: ValueEventListener? = null

    override fun observeUserPlan(uid: String): Flow<String> = callbackFlow {
        Timber.d("[PlanRepo] observeUserPlan callbackFlow 시작: uid=$uid")
        planRef = db.reference.child("users").child(uid).child("plan")
        listenerRegistration = planRef!!.addValueEventListener(object : ValueEventListener {
            override fun onDataChange(snapshot: DataSnapshot) {
                val plan = snapshot.getValue(String::class.java) ?: "free"
                Timber.d("[PlanRepo] onDataChange: plan=$plan")
                trySend(plan)
            }
            override fun onCancelled(error: DatabaseError) {
                Timber.d("[PlanRepo] onCancelled: ${error.message}")
            }
        })
        awaitClose { planRef?.removeEventListener(listenerRegistration!!) }
    }

    override fun reset() {
        listenerRegistration?.let { planRef?.removeEventListener(it) }
        listenerRegistration = null
        planRef = null
    }

    override suspend fun updateUserPlan(uid: String, plan: String) {
        FirebaseRefs.planRef(uid).setValue(plan).await()
    }

    override suspend fun recordSubscriptionPurchase(uid: String, purchaseToken: String, purchaseTime: Long) {
        val firestore = FirebaseFirestore.getInstance(FirebaseConstants.FIRESTORE_DB)
        firestore.collection("users").document(uid).set(
            mapOf(
                "purchaseToken" to purchaseToken,
                "purchaseTime" to purchaseTime,
                "planUpdatedAt" to System.currentTimeMillis()
            ),
            SetOptions.merge()
        ).await()
    }
}
