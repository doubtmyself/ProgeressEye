package com.chg.progeresseye.data.repository

import com.chg.progeresseye.domain.repository.UserPlanRepository
import com.google.firebase.database.DataSnapshot
import com.google.firebase.database.DatabaseError
import com.google.firebase.database.FirebaseDatabase
import com.google.firebase.database.ValueEventListener
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import javax.inject.Inject

class UserPlanRepositoryImpl @Inject constructor() : UserPlanRepository {
    private val db = FirebaseDatabase.getInstance()
    override fun observeUserPlan(uid: String): Flow<String> = callbackFlow {
        val ref = db.reference.child("users").child(uid).child("plan")
        val listener = ref.addValueEventListener(object : ValueEventListener {
            override fun onDataChange(snapshot: DataSnapshot) {
                trySend(snapshot.getValue(String::class.java) ?: "free")
            }
            override fun onCancelled(error: DatabaseError) {}
        })
        awaitClose { ref.removeEventListener(listener) }
    }
    override fun reset() {}
}
