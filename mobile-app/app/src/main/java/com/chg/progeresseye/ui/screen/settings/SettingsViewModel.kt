package com.chg.progeresseye.ui.screen.settings

import android.app.Activity
import android.app.Application
import android.content.Context
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.chg.progeresseye.NotificationPrefs
import com.chg.progeresseye.data.util.FirebaseConstants
import com.chg.progeresseye.domain.repository.PolicyRepository
import com.chg.progeresseye.domain.repository.UserPlanRepository
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
import com.google.firebase.auth.FirebaseAuth
import com.google.firebase.database.FirebaseDatabase
import com.google.firebase.firestore.FirebaseFirestore
import com.google.firebase.firestore.SetOptions
import com.chg.progeresseye.util.FirebaseRefs
import com.chg.progeresseye.util.isPro
import com.chg.progeresseye.util.toNormalizedPlan
import timber.log.Timber
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update

/**
 * 설정 화면의 UI 상태 데이터를 보관하는 데이터 클래스
 *
 * @property completionAlerts 작업 완료 알림 수신 여부
 * @property stallWarnings 작업 지연 경고 수신 여부
 * @property currentPlan 현재 사용자의 구독 플랜
 * @property isAdFreeMode 글로벌 광고 제거 모드 활성화 여부
 * @property subscriptionPrice 구독 상품 가격 문자열
 * @property isBillingReady 결제 클라이언트 준비 상태
 * @constructor Create empty [SettingsUiState]
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
 *
 * 알림 설정, Pro 구독 결제(BillingClient) 및 정책 상태를 관리합니다.
 *
 * @param application 전체 앱 라이프사이클에 접근하기 위한 Application 컨텍스트
 * @param userPlanRepository 사용자 결제 플랜 상태를 관찰하는 저장소
 * @param policyRepository 전역 정책을 관찰하는 저장소
 * @constructor Create empty [SettingsViewModel]
 */
class SettingsViewModel @Inject constructor(
    application: Application,
    private val userPlanRepository: UserPlanRepository,
    private val policyRepository: PolicyRepository,
) : AndroidViewModel(application) {

    private val prefs = application.getSharedPreferences(NotificationPrefs.PREFS_NAME, Context.MODE_PRIVATE)
    private val auth = FirebaseAuth.getInstance()
    private val firestore = FirebaseFirestore.getInstance(FirebaseConstants.FIRESTORE_DB)
    private val rtdb = FirebaseDatabase.getInstance()
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
        auth.currentUser?.uid?.let { uid ->
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

    /**
     * 작업 완료 알림 수신 설정을 토글
     */
    fun toggleCompletionAlerts() {
        _uiState.update { current ->
            val updated = current.copy(completionAlerts = !current.completionAlerts)
            prefs.edit().putBoolean(NotificationPrefs.KEY_COMPLETION_ALERTS, updated.completionAlerts).apply()
            updated
        }
    }

    /**
     * 작업 지연/중단 경고 알림 수신 설정을 토글
     */
    fun toggleStallWarnings() {
        _uiState.update { current ->
            val updated = current.copy(stallWarnings = !current.stallWarnings)
            prefs.edit().putBoolean(NotificationPrefs.KEY_STALL_WARNINGS, updated.stallWarnings).apply()
            updated
        }
    }

    /**
     * Pro 구독 상품 결제 흐름을 시작
     *
     * @param activity Google Play 결제 팝업을 표시할 Activity 컨텍스트
     */
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

    // 앱 시작/포그라운드 복귀 시 MainScreen에서 호출 — 구독 만료/취소 자동 반영
    fun refreshSubscriptionStatus() {
        if (billingClient?.isReady == true) {
            queryActiveSubscriptions()
        } else {
            setupBillingClient() // 연결 성공 시 내부에서 queryActiveSubscriptions() 호출
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
            if (billingResult.responseCode != BillingClient.BillingResponseCode.OK) return@queryPurchasesAsync

            if (purchases.isNullOrEmpty()) {
                // 활성 구독 없음 → RTDB plan을 free로 갱신 (취소/만료 시 자동 반영)
                val uid = auth.currentUser?.uid ?: return@queryPurchasesAsync
                FirebaseRefs.planRef(uid).setValue("free")
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

        // Google Play 확인 후 RTDB에 plan: "pro" 기록 (PC 앱에서도 읽을 수 있도록)
        FirebaseRefs.planRef(uid).setValue("pro")
            .addOnSuccessListener {
                // Firestore에 purchaseToken + 결제일 백업 (서버 검증 도입 시 활용)
                firestore.collection("users")
                    .document(uid)
                    .set(
                        mapOf(
                            "purchaseToken" to purchase.purchaseToken,
                            "purchaseTime" to purchase.purchaseTime,
                            "planUpdatedAt" to System.currentTimeMillis(),
                        ),
                        SetOptions.merge(),
                    )
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
        billingClient?.endConnection()
        billingClient = null
    }

    companion object {
        private const val PRO_SUBSCRIPTION_PRODUCT_ID = "pro_monthly_3000"
    }
}
