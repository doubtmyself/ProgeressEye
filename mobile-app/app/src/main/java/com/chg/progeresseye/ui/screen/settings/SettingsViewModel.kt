package com.chg.progeresseye.ui.screen.settings

import android.app.Activity
import android.app.Application
import android.content.Context
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.chg.progeresseye.NotificationPrefs
import com.chg.progeresseye.domain.repository.PolicyRepository
import com.chg.progeresseye.domain.repository.UserPlanRepository
import com.chg.progeresseye.domain.usecase.GetCurrentUserUidUseCase
import com.chg.progeresseye.domain.usecase.RecordSubscriptionPurchaseUseCase
import com.chg.progeresseye.domain.usecase.UpdateUserPlanUseCase
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.launch
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
import com.chg.progeresseye.util.isPro
import com.chg.progeresseye.util.toNormalizedPlan
import timber.log.Timber
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update

/**
 * 설정 화면의 UI 상태 데이터를 보관하는 데이터 클래스
 */
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

@HiltViewModel
/**
 * 설정 화면의 비즈니스 로직과 UI 상태를 관리하는 ViewModel
 */
class SettingsViewModel @Inject constructor(
    application: Application,
    private val userPlanRepository: UserPlanRepository,
    private val policyRepository: PolicyRepository,
    private val getCurrentUserUidUseCase: GetCurrentUserUidUseCase,
    private val updateUserPlanUseCase: UpdateUserPlanUseCase,
    private val recordSubscriptionPurchaseUseCase: RecordSubscriptionPurchaseUseCase
) : AndroidViewModel(application) {

    private val prefs = application.getSharedPreferences(NotificationPrefs.PREFS_NAME, Context.MODE_PRIVATE)
    private var billingClient: BillingClient? = null
    private var subscriptionProductDetails: ProductDetails? = null

    private val _uiState = MutableStateFlow(
        SettingsUiState(
            completionAlerts = prefs.getBoolean(NotificationPrefs.KEY_COMPLETION_ALERTS, true),
            stallWarnings = prefs.getBoolean(NotificationPrefs.KEY_STALL_WARNINGS, true),
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
        getCurrentUserUidUseCase()?.let { uid ->
            viewModelScope.launch {
                userPlanRepository.observeUserPlan(uid).collect { plan ->
                    _uiState.update { state ->
                        state.copy(currentPlan = plan.toNormalizedPlan())
                    }
                }
            }
        }
        viewModelScope.launch {
            policyRepository.observePolicy().collect { adFreeMode ->
                _uiState.update { state ->
                    state.copy(isAdFreeMode = adFreeMode, isPolicyLoaded = true)
                }
            }
        }
        setupBillingClient()
    }

    fun toggleCompletionAlerts() {
        _uiState.update { current ->
            val updated = current.copy(completionAlerts = !current.completionAlerts)
            prefs.edit().putBoolean(NotificationPrefs.KEY_COMPLETION_ALERTS, updated.completionAlerts).apply()
            updated
        }
    }

    fun toggleStallWarnings() {
        _uiState.update { current ->
            val updated = current.copy(stallWarnings = !current.stallWarnings)
            prefs.edit().putBoolean(NotificationPrefs.KEY_STALL_WARNINGS, updated.stallWarnings).apply()
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

    fun refreshSubscriptionStatus() {
        if (billingClient?.isReady == true) {
            queryActiveSubscriptions()
        } else {
            setupBillingClient()
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
                .firstOrNull { detail -> detail.productId == PRO_SUBSCRIPTION_PRODUCT_ID }
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
            if (billingResult.responseCode != BillingClient.BillingResponseCode.OK) return@queryPurchasesAsync

            if (purchases.isNullOrEmpty()) {
                val uid = getCurrentUserUidUseCase() ?: return@queryPurchasesAsync
                viewModelScope.launch {
                    try { updateUserPlanUseCase(uid, "free") } catch (e: Exception) { Timber.w(e) }
                }
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
                    grantProEntitlement(target, showSuccessMessage)
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
                grantProEntitlement(purchase, showSuccessMessage)
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

    private fun grantProEntitlement(purchase: Purchase, showSuccessMessage: Boolean) {
        if (_uiState.value.currentPlan.isPro() && !showSuccessMessage) {
            _uiState.update { it.copy(isPurchaseLoading = false) }
            return
        }

        val uid = getCurrentUserUidUseCase()
        if (uid.isNullOrBlank()) {
            _uiState.update {
                it.copy(
                    isPurchaseLoading = false,
                    billingMessage = getApplication<Application>().getString(R.string.settings_subscription_purchase_failed),
                )
            }
            return
        }

        viewModelScope.launch {
            try {
                updateUserPlanUseCase(uid, "pro")
                recordSubscriptionPurchaseUseCase(uid, purchase.purchaseToken, purchase.purchaseTime)
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
            } catch (e: Exception) {
                Timber.e(e)
                _uiState.update {
                    it.copy(
                        isPurchaseLoading = false,
                        billingMessage = getApplication<Application>().getString(R.string.settings_subscription_purchase_failed),
                    )
                }
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
        billingClient?.endConnection()
        billingClient = null
    }

    companion object {
        private const val PRO_SUBSCRIPTION_PRODUCT_ID = "pro_monthly_3000"
    }
}
