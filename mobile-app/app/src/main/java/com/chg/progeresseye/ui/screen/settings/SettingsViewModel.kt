package com.chg.progeresseye.ui.screen.settings

import android.app.Activity
import android.app.Application
import android.content.Context
import androidx.lifecycle.AndroidViewModel
import com.android.billingclient.api.AcknowledgePurchaseParams
import com.android.billingclient.api.BillingClient
import com.android.billingclient.api.BillingClientStateListener
import com.android.billingclient.api.BillingFlowParams
import com.android.billingclient.api.BillingResult
import com.android.billingclient.api.ProductDetails
import com.android.billingclient.api.Purchase
import com.android.billingclient.api.PurchasesUpdatedListener
import com.android.billingclient.api.PendingPurchasesParams
import com.android.billingclient.api.QueryProductDetailsParams
import com.android.billingclient.api.QueryPurchasesParams
import com.chg.progeresseye.R
import com.google.firebase.auth.FirebaseAuth
import com.google.firebase.firestore.FirebaseFirestore
import timber.log.Timber
import com.google.firebase.firestore.ListenerRegistration
import com.google.firebase.firestore.SetOptions
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update

data class SettingsUiState(
    val completionAlerts: Boolean = true,
    val stallWarnings: Boolean = true,
    val currentPlan: String = "free",
    val isAdFreeMode: Boolean = false,
    val isPolicyLoaded: Boolean = false,
    val subscriptionPrice: String? = null,
    val isBillingReady: Boolean = false,
    val isPurchaseLoading: Boolean = false,
    val billingMessage: String? = null,
)

class SettingsViewModel(application: Application) : AndroidViewModel(application) {

    private val prefs = application.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
    private val auth = FirebaseAuth.getInstance()
    private val firestore = FirebaseFirestore.getInstance("progress")
    private var userPlanListener: ListenerRegistration? = null
    private var globalPolicyListener: ListenerRegistration? = null
    private var billingClient: BillingClient? = null
    private var subscriptionProductDetails: ProductDetails? = null

    private val _uiState = MutableStateFlow(
        SettingsUiState(
            completionAlerts = prefs.getBoolean(KEY_COMPLETION_ALERTS, true),
            stallWarnings = prefs.getBoolean(KEY_STALL_WARNINGS, true),
        ),
    )
    val uiState: StateFlow<SettingsUiState> = _uiState.asStateFlow()

    private val purchasesUpdatedListener = PurchasesUpdatedListener { billingResult, purchases ->
        when (billingResult.responseCode) {
            BillingClient.BillingResponseCode.OK -> {
                if (purchases.isNullOrEmpty()) {
                    _uiState.update {
                        it.copy(
                            isPurchaseLoading = false,
                            billingMessage = getApplication<Application>().getString(R.string.settings_subscription_purchase_failed),
                        )
                    }
                } else {
                    processPurchases(purchases, showSuccessMessage = true)
                }
            }

            BillingClient.BillingResponseCode.USER_CANCELED -> {
                _uiState.update {
                    it.copy(
                        isPurchaseLoading = false,
                        billingMessage = getApplication<Application>().getString(R.string.settings_subscription_purchase_cancelled),
                    )
                }
            }

            else -> {
                _uiState.update {
                    it.copy(
                        isPurchaseLoading = false,
                        billingMessage = billingResult.debugMessage.takeIf { msg -> msg.isNotBlank() }
                            ?: getApplication<Application>().getString(R.string.settings_subscription_purchase_failed),
                    )
                }
            }
        }
    }

    init {
        observeUserPlan()
        observeGlobalPolicy()
        setupBillingClient()
    }

    fun toggleCompletionAlerts() {
        _uiState.update { current ->
            val updated = current.copy(completionAlerts = !current.completionAlerts)
            prefs.edit().putBoolean(KEY_COMPLETION_ALERTS, updated.completionAlerts).apply()
            updated
        }
    }

    fun toggleStallWarnings() {
        _uiState.update { current ->
            val updated = current.copy(stallWarnings = !current.stallWarnings)
            prefs.edit().putBoolean(KEY_STALL_WARNINGS, updated.stallWarnings).apply()
            updated
        }
    }

    fun startProSubscription(activity: Activity) {
        if (_uiState.value.isAdFreeMode) return

        val client = billingClient
        if (client == null || !client.isReady) {
            _uiState.update {
                it.copy(
                    billingMessage = getApplication<Application>().getString(R.string.settings_subscription_billing_unavailable),
                )
            }
            setupBillingClient()
            return
        }

        val details = subscriptionProductDetails
        if (details == null) {
            _uiState.update {
                it.copy(
                    billingMessage = getApplication<Application>().getString(R.string.settings_subscription_not_ready),
                )
            }
            querySubscriptionProductDetails()
            return
        }

        val offerToken = details.subscriptionOfferDetails
            ?.firstOrNull()
            ?.offerToken

        if (offerToken.isNullOrBlank()) {
            _uiState.update {
                it.copy(
                    billingMessage = getApplication<Application>().getString(R.string.settings_subscription_not_ready),
                )
            }
            return
        }

        _uiState.update { it.copy(isPurchaseLoading = true, billingMessage = null) }

        val params = BillingFlowParams.newBuilder()
            .setProductDetailsParamsList(
                listOf(
                    BillingFlowParams.ProductDetailsParams.newBuilder()
                        .setProductDetails(details)
                        .setOfferToken(offerToken)
                        .build(),
                ),
            )
            .build()

        val result = client.launchBillingFlow(activity, params)
        if (result.responseCode != BillingClient.BillingResponseCode.OK) {
            _uiState.update {
                it.copy(
                    isPurchaseLoading = false,
                    billingMessage = result.debugMessage.takeIf { msg -> msg.isNotBlank() }
                        ?: getApplication<Application>().getString(R.string.settings_subscription_purchase_failed),
                )
            }
        }
    }

    fun clearBillingMessage() {
        _uiState.update { it.copy(billingMessage = null) }
    }

    private fun observeUserPlan() {
        val uid = auth.currentUser?.uid ?: return
        userPlanListener?.remove()
        userPlanListener = firestore.collection("users")
            .document(uid)
            .addSnapshotListener { snapshot, error ->
                if (error != null) {
                    Timber.e(error, "observeUserPlan: Firestore listener error")
                    return@addSnapshotListener
                }
                val plan = snapshot?.getString("plan")?.lowercase() ?: "free"
                _uiState.update { state ->
                    state.copy(
                        currentPlan = if (plan == "pro") "pro" else "free",
                    )
                }
            }
    }

    private fun observeGlobalPolicy() {
        globalPolicyListener?.remove()
        globalPolicyListener = firestore.collection("appConfig")
            .document("policies")
            .addSnapshotListener { snapshot, _ ->
                val globalAdFreeMode = snapshot?.getBoolean("adFreeModeGlobal") == true
                _uiState.update { state ->
                    state.copy(isAdFreeMode = globalAdFreeMode, isPolicyLoaded = true)
                }
            }
    }

    private fun setupBillingClient() {
        billingClient?.endConnection()
        billingClient = BillingClient.newBuilder(getApplication())
            .setListener(purchasesUpdatedListener)
            .enablePendingPurchases(
                PendingPurchasesParams.newBuilder()
                    .enableOneTimeProducts()
                    .build(),
            )
            .build()

        billingClient?.startConnection(object : BillingClientStateListener {
            override fun onBillingSetupFinished(billingResult: BillingResult) {
                if (billingResult.responseCode == BillingClient.BillingResponseCode.OK) {
                    _uiState.update { it.copy(isBillingReady = true) }
                    querySubscriptionProductDetails()
                    queryActiveSubscriptions()
                } else {
                    _uiState.update {
                        it.copy(
                            isBillingReady = false,
                            billingMessage = getApplication<Application>().getString(R.string.settings_subscription_billing_unavailable),
                        )
                    }
                }
            }

            override fun onBillingServiceDisconnected() {
                _uiState.update { it.copy(isBillingReady = false) }
            }
        })
    }

    private fun querySubscriptionProductDetails() {
        val client = billingClient ?: return
        if (!client.isReady) return

        val params = QueryProductDetailsParams.newBuilder()
            .setProductList(
                listOf(
                    QueryProductDetailsParams.Product.newBuilder()
                        .setProductId(PRO_SUBSCRIPTION_PRODUCT_ID)
                        .setProductType(BillingClient.ProductType.SUBS)
                        .build(),
                ),
            )
            .build()

        client.queryProductDetailsAsync(params) { billingResult, productDetailsResult ->
            if (billingResult.responseCode != BillingClient.BillingResponseCode.OK) {
                _uiState.update {
                    it.copy(
                        subscriptionPrice = null,
                        billingMessage = billingResult.debugMessage.takeIf { msg -> msg.isNotBlank() }
                            ?: getApplication<Application>().getString(R.string.settings_subscription_not_ready),
                    )
                }
                return@queryProductDetailsAsync
            }

            val details = productDetailsResult.productDetailsList
                .firstOrNull { detail: ProductDetails -> detail.productId == PRO_SUBSCRIPTION_PRODUCT_ID }
            subscriptionProductDetails = details
            _uiState.update {
                it.copy(subscriptionPrice = details?.formattedSubscriptionPrice())
            }
        }
    }

    private fun queryActiveSubscriptions() {
        val client = billingClient ?: return
        if (!client.isReady) return

        client.queryPurchasesAsync(
            QueryPurchasesParams.newBuilder()
                .setProductType(BillingClient.ProductType.SUBS)
                .build(),
        ) { billingResult, purchases ->
            if (billingResult.responseCode != BillingClient.BillingResponseCode.OK || purchases.isNullOrEmpty()) {
                return@queryPurchasesAsync
            }
            processPurchases(purchases, showSuccessMessage = false)
        }
    }

    private fun processPurchases(purchases: List<Purchase>, showSuccessMessage: Boolean) {
        val target = purchases.firstOrNull { purchase ->
            purchase.products.contains(PRO_SUBSCRIPTION_PRODUCT_ID)
        }

        if (target == null) {
            _uiState.update { it.copy(isPurchaseLoading = false) }
            return
        }

        when (target.purchaseState) {
            Purchase.PurchaseState.PURCHASED -> {
                if (target.isAcknowledged) {
                    grantProEntitlement(showSuccessMessage)
                } else {
                    acknowledgePurchase(target, showSuccessMessage)
                }
            }

            Purchase.PurchaseState.PENDING -> {
                _uiState.update {
                    it.copy(
                        isPurchaseLoading = false,
                        billingMessage = getApplication<Application>().getString(R.string.settings_subscription_purchase_pending),
                    )
                }
            }

            else -> {
                _uiState.update { it.copy(isPurchaseLoading = false) }
            }
        }
    }

    private fun acknowledgePurchase(purchase: Purchase, showSuccessMessage: Boolean) {
        val client = billingClient ?: return
        if (!client.isReady) {
            _uiState.update {
                it.copy(
                    isPurchaseLoading = false,
                    billingMessage = getApplication<Application>().getString(R.string.settings_subscription_billing_unavailable),
                )
            }
            return
        }

        client.acknowledgePurchase(
            AcknowledgePurchaseParams.newBuilder()
                .setPurchaseToken(purchase.purchaseToken)
                .build(),
        ) { billingResult ->
            if (billingResult.responseCode == BillingClient.BillingResponseCode.OK) {
                grantProEntitlement(showSuccessMessage)
            } else {
                _uiState.update {
                    it.copy(
                        isPurchaseLoading = false,
                        billingMessage = billingResult.debugMessage.takeIf { msg -> msg.isNotBlank() }
                            ?: getApplication<Application>().getString(R.string.settings_subscription_purchase_failed),
                    )
                }
            }
        }
    }

    private fun grantProEntitlement(showSuccessMessage: Boolean) {
        if (_uiState.value.currentPlan == "pro" && !showSuccessMessage) {
            _uiState.update { it.copy(isPurchaseLoading = false) }
            return
        }

        val uid = auth.currentUser?.uid
        if (uid.isNullOrBlank()) {
            _uiState.update {
                it.copy(
                    isPurchaseLoading = false,
                    billingMessage = getApplication<Application>().getString(R.string.settings_subscription_purchase_failed),
                )
            }
            return
        }

        firestore.collection("users")
            .document(uid)
            .set(
                mapOf(
                    "plan" to "pro",
                    "planUpdatedAt" to System.currentTimeMillis(),
                ),
                SetOptions.merge(),
            )
            .addOnSuccessListener {
                _uiState.update {
                    it.copy(
                        currentPlan = "pro",
                        isPurchaseLoading = false,
                        billingMessage = if (showSuccessMessage) {
                            getApplication<Application>().getString(R.string.settings_subscription_purchase_success)
                        } else {
                            null
                        },
                    )
                }
            }
            .addOnFailureListener {
                _uiState.update {
                    it.copy(
                        isPurchaseLoading = false,
                        billingMessage = getApplication<Application>().getString(R.string.settings_subscription_purchase_failed),
                    )
                }
            }
    }

    private fun ProductDetails.formattedSubscriptionPrice(): String? {
        return subscriptionOfferDetails
            ?.firstOrNull()
            ?.pricingPhases
            ?.pricingPhaseList
            ?.firstOrNull()
            ?.formattedPrice
    }

    override fun onCleared() {
        super.onCleared()
        userPlanListener?.remove()
        userPlanListener = null
        globalPolicyListener?.remove()
        globalPolicyListener = null
        billingClient?.endConnection()
        billingClient = null
    }

    companion object {
        private const val PREFS_NAME = "settings"
        private const val KEY_COMPLETION_ALERTS = "completionAlerts"
        private const val KEY_STALL_WARNINGS = "stallWarnings"
        private const val PRO_SUBSCRIPTION_PRODUCT_ID = "pro_monthly_3000"
    }
}
