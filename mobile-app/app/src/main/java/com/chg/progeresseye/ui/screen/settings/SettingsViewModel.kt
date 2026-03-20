package com.chg.progeresseye.ui.screen.settings

import android.app.Activity
import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.chg.progeresseye.domain.repository.NotificationPrefsRepository
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
 *
 * @property completionAlerts 완료 알림 활성화 여부
 * @property stallWarnings 정체 경고 알림 활성화 여부
 * @property currentPlan 현재 사용자의 구독 플랜 ("free", "pro" 등)
 * @property isAdFreeMode 전역 광고 제거 모드 활성화 여부 (정책에 의해 강제될 수 있음)
 * @property isPolicyLoaded 정책 로드 완료 여부
 * @property subscriptionPrice 구독 상품의 포맷팅된 가격 문자열
 * @property isBillingReady 결제 클라이언트 준비 완료 여부
 * @property isPurchaseLoading 결제 처리 중인지 여부
 * @property billingMessage 사용자에게 표시할 결제 관련 알림 메시지
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
 * 설정 화면의 비즈니스 로직과 UI 상태를 관리하는 ViewModel입니다.
 * 인앱 결제(구독) 처리 및 알림 설정을 담당합니다.
 *
 * @property userPlanRepository 사용자 플랜 정보 저장소
 * @property policyRepository 앱 정책 정보 저장소
 * @property notificationPrefsRepository 알림 설정 저장소
 * @property getCurrentUserUidUseCase 현재 사용자 UID 획득 UseCase
 * @property updateUserPlanUseCase 사용자 플랜 업데이트 UseCase
 * @property recordSubscriptionPurchaseUseCase 구독 구매 기록 저장 UseCase
 */
class SettingsViewModel @Inject constructor(
    application: Application,
    private val userPlanRepository: UserPlanRepository,
    private val policyRepository: PolicyRepository,
    private val notificationPrefsRepository: NotificationPrefsRepository,
    private val getCurrentUserUidUseCase: GetCurrentUserUidUseCase,
    private val updateUserPlanUseCase: UpdateUserPlanUseCase,
    private val recordSubscriptionPurchaseUseCase: RecordSubscriptionPurchaseUseCase
) : AndroidViewModel(application) {

    private var billingClient: BillingClient? = null
    private var subscriptionProductDetails: ProductDetails? = null

    private val _uiState = MutableStateFlow(SettingsUiState())
    val uiState: StateFlow<SettingsUiState> = _uiState.asStateFlow()

    /**
     * Google Play 결제 업데이트 리스너입니다. 구매 성공, 취소, 에러 등 결과에 따라 UI 상태를 업데이트합니다.
     */
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
                Timber.w("purchasesUpdatedListener error: code=%d msg=%s", billingResult.responseCode, billingResult.debugMessage)
                _uiState.update {
                    it.copy(
                        isPurchaseLoading = false,
                        billingMessage = getApplication<Application>().getString(R.string.settings_subscription_purchase_failed),
                    )
                }
            }
        }
    }

    init {
        viewModelScope.launch {
            notificationPrefsRepository.observeCompletionAlerts().collect { enabled ->
                _uiState.update { it.copy(completionAlerts = enabled) }
            }
        }
        viewModelScope.launch {
            notificationPrefsRepository.observeStallWarnings().collect { enabled ->
                _uiState.update { it.copy(stallWarnings = enabled) }
            }
        }
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

    /**
     * 완료 알림 설정 값을 반전시키고 영구 저장소에 저장합니다.
     */
    fun toggleCompletionAlerts() {
        val newValue = !_uiState.value.completionAlerts
        _uiState.update { it.copy(completionAlerts = newValue) }
        viewModelScope.launch { notificationPrefsRepository.setCompletionAlerts(newValue) }
    }

    /**
     * 정체 경고 알림 설정 값을 반전시키고 영구 저장소에 저장합니다.
     */
    fun toggleStallWarnings() {
        val newValue = !_uiState.value.stallWarnings
        _uiState.update { it.copy(stallWarnings = newValue) }
        viewModelScope.launch { notificationPrefsRepository.setStallWarnings(newValue) }
    }

    /**
     * Pro 구독 구매 흐름을 시작합니다.
     *
     * @param activity 결제 화면을 띄우기 위해 필요한 Activity
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
            Timber.w("launchBillingFlow error: code=%d msg=%s", result.responseCode, result.debugMessage)
            _uiState.update {
                it.copy(
                    isPurchaseLoading = false,
                    billingMessage = getApplication<Application>().getString(R.string.settings_subscription_purchase_failed),
                )
            }
        }
    }

    /**
     * UI에 표시된 결제 관련 에러/안내 메시지를 초기화합니다.
     */
    fun clearBillingMessage() {
        _uiState.update { it.copy(billingMessage = null) }
    }

    /**
     * 현재 구독 상태를 강제로 새로고침합니다.
     */
    fun refreshSubscriptionStatus() {
        if (billingClient?.isReady == true) {
            queryActiveSubscriptions()
        } else {
            setupBillingClient()
        }
    }

    /**
     * BillingClient를 초기화하고 연결을 시도합니다.
     */
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

    /**
     * 구독 상품 정보를 비동기적으로 조회하여 가격 정보를 업데이트합니다.
     */
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
                        billingMessage = getApplication<Application>().getString(R.string.settings_subscription_not_ready),
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

    /**
     * 사용자가 현재 보유한 활성 구독 내역을 조회합니다.
     */
    private fun queryActiveSubscriptions() {
        val client = billingClient ?: return
        if (!client.isReady) return

        client.queryPurchasesAsync(
            QueryPurchasesParams.newBuilder()
                .setProductType(BillingClient.ProductType.SUBS)
                .build(),
        ) { billingResult, purchases ->
            if (billingResult.responseCode != BillingClient.BillingResponseCode.OK) return@queryPurchasesAsync

            if (purchases.isEmpty()) {
                val uid = getCurrentUserUidUseCase() ?: return@queryPurchasesAsync
                viewModelScope.launch {
                    try { updateUserPlanUseCase(uid, "free") } catch (e: Exception) { Timber.w(e) }
                }
                return@queryPurchasesAsync
            }
            processPurchases(purchases, showSuccessMessage = false)
        }
    }

    /**
     * 조회된 구매 목록을 분석하여 적절한 처리(승인 또는 권한 부여)를 수행합니다.
     *
     * @param purchases 구매 정보 목록
     * @param showSuccessMessage 성공 메시지를 화면에 표시할지 여부
     */
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

    /**
     * Google Play 서버에 구매 승인(Acknowledge) 요청을 보냅니다.
     *
     * @param purchase 승인할 구매 정보
     * @param showSuccessMessage 승인 완료 후 성공 메시지 표시 여부
     */
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
                        billingMessage = getApplication<Application>().getString(R.string.settings_subscription_purchase_failed),
                    )
                }
            }
        }
    }

    /**
     * 사용자에게 Pro 구독 권한을 부여하고 서버에 구매 내역을 기록합니다.
     *
     * @param purchase 구매 성공한 정보
     * @param showSuccessMessage 성공 메시지 표시 여부
     */
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

    /**
     * ProductDetails 객체로부터 현재 유효한 구독 가격 문자열을 추출합니다.
     *
     * @return 포맷팅된 가격 문자열 (예: "₩3,000"), 없으면 null
     */
    private fun ProductDetails.formattedSubscriptionPrice(): String? {
        return subscriptionOfferDetails
            ?.firstOrNull()
            ?.pricingPhases
            ?.pricingPhaseList
            ?.firstOrNull()
            ?.formattedPrice
    }

    /**
     * ViewModel이 소멸될 때 결제 클라이언트 연결을 해제합니다.
     */
    override fun onCleared() {
        super.onCleared()
        billingClient?.endConnection()
        billingClient = null
    }

    companion object {
        private const val PRO_SUBSCRIPTION_PRODUCT_ID = "pro_monthly_3000"
    }
}
