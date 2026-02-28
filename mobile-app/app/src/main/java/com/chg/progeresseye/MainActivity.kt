package com.chg.progeresseye

import android.os.Bundle
import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import timber.log.Timber
import android.app.AlertDialog
import android.content.Intent
import android.net.Uri
import androidx.activity.result.IntentSenderRequest
import com.google.android.play.core.appupdate.AppUpdateManagerFactory
import com.google.android.play.core.appupdate.AppUpdateOptions
import com.google.android.play.core.install.model.AppUpdateType
import com.google.android.play.core.install.model.UpdateAvailability
import com.google.firebase.firestore.FirebaseFirestore
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.lifecycleScope
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.chg.progeresseye.auth.AuthViewModel
import com.chg.progeresseye.auth.MobileSessionManager
import com.chg.progeresseye.service.FCMService
import com.chg.progeresseye.ui.screen.login.LoginScreen
import com.chg.progeresseye.ui.screen.main.MainScreen
import com.chg.progeresseye.ui.screen.splash.SplashScreen
import com.chg.progeresseye.ui.theme.ProgressEyeTheme
import com.google.android.gms.ads.MobileAds
import com.google.firebase.database.DatabaseReference
import com.google.firebase.database.FirebaseDatabase
import com.google.firebase.database.ValueEventListener
import com.google.firebase.database.DatabaseError
import com.google.firebase.database.DataSnapshot
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {
    private var mobileSessionRef: DatabaseReference? = null
    private var mobileSessionListener: ValueEventListener? = null
    private var isHandlingSessionConflict: Boolean = false

    private val notificationPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { /* granted or denied — no action needed */ }

    /** 인앱 업데이트가 필요한 상태인지 (onResume 재트리거용) */
    private var updateRequired = false

    private val updateLauncher = registerForActivityResult(
        ActivityResultContracts.StartIntentSenderForResult()
    ) { result ->
        if (result.resultCode != RESULT_OK) {
            // 사용자가 업데이트를 취소/실패 → 앱 종료 (강제 업데이트이므로)
            Timber.w("In-app update cancelled or failed (code=%d)", result.resultCode)
            finish()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        // installSplashScreen() MUST be called BEFORE super.onCreate()
        val splashScreen = installSplashScreen()
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        // 강제 버전 체크 (Firestore progress DB — 인증 불필요)
        checkMinVersion()

        setContent {
            ProgressEyeTheme {
                val authViewModel: AuthViewModel = viewModel()
                val authState by authViewModel.uiState.collectAsStateWithLifecycle()
                val navController = rememberNavController()

                // Keep splash visible until auth state is determined
                // Firebase AuthStateListener fires synchronously, so this resolves fast
                splashScreen.setKeepOnScreenCondition {
                    // Show splash while initial auth check hasn't completed
                    // Once authViewModel is initialized, isSignedIn is available immediately
                    false // Firebase currentUser is synchronous — no async wait needed
                }

                // Target destination after splash, driven by AuthUiState.
                // This prevents auto-navigation to main while takeover confirmation is pending.
                val authTarget = if (
                    authState.user != null && !authState.requiresSessionTakeover
                ) {
                    "main"
                } else {
                    "login"
                }

                LaunchedEffect(authState.user, authState.requiresSessionTakeover) {
                    val currentRoute = navController.currentDestination?.route
                    // Don't auto-navigate while splash animation is running
                    if (currentRoute == "splash") return@LaunchedEffect
                    if (authState.user != null && !authState.requiresSessionTakeover && currentRoute != "main") {
                        navController.navigate("main") {
                            popUpTo("login") { inclusive = true }
                        }
                    } else if (authState.user == null && currentRoute == "main") {
                        navController.navigate("login") {
                            popUpTo("main") { inclusive = true }
                        }
                    }
                }

                LaunchedEffect(authState.user?.uid) {
                    val uid = authState.user?.uid
                    if (uid != null) {
                        startSessionConflictListener(uid, authViewModel)
                    } else {
                        stopSessionConflictListener()
                    }
                }

                NavHost(
                    navController = navController,
                    startDestination = "splash",
                ) {
                    composable("splash") {
                        SplashScreen(
                            onFinished = {
                                navController.navigate(authTarget) {
                                    popUpTo("splash") { inclusive = true }
                                }
                            },
                        )
                    }
                    composable("login") {
                        val webClientId = getString(R.string.default_web_client_id)

                        LoginScreen(
                            onSignInClick = {
                                authViewModel.signInWithGoogle(
                                    context = this@MainActivity,
                                    webClientId = webClientId,
                                )
                            },
                            onConfirmSessionTakeover = {
                                authViewModel.confirmSessionTakeover(this@MainActivity)
                            },
                            onCancelSessionTakeover = {
                                authViewModel.cancelSessionTakeover(this@MainActivity)
                            },
                            isLoading = authState.isLoading,
                            error = authState.error,
                            requiresSessionTakeover = authState.requiresSessionTakeover,
                            existingDeviceName = authState.existingDeviceName,
                        )
                    }
                    composable("main") {
                        LaunchedEffect(Unit) {
                            requestNotificationPermission()
                            FCMService.registerToken()
                        }
                        MainScreen(
                            onSignOut = {
                                authViewModel.signOut(this@MainActivity)
                            },
                            onDeleteAccount = {
                                authViewModel.deleteAccount(this@MainActivity)
                            },
                        )
                    }
                }
            }
        }

        lifecycleScope.launch(Dispatchers.IO) {
            MobileAds.initialize(this@MainActivity) {}
        }
    }

    override fun onDestroy() {
        stopSessionConflictListener()
        super.onDestroy()
    }

    private fun startSessionConflictListener(uid: String, authViewModel: AuthViewModel) {
        stopSessionConflictListener()
        isHandlingSessionConflict = false

        val localSessionId = MobileSessionManager.getSessionId(this) ?: return
        val ref = FirebaseDatabase.getInstance()
            .getReference("users")
            .child(uid)
            .child("mobileSession")
            .child("sessionId")

        val listener = object : ValueEventListener {
            override fun onDataChange(snapshot: DataSnapshot) {
                val remoteSessionId = snapshot.getValue(String::class.java) ?: return
                if (!isHandlingSessionConflict && remoteSessionId != localSessionId) {
                    isHandlingSessionConflict = true
                    authViewModel.forceSignOutBySessionConflict(this@MainActivity)
                }
            }

            override fun onCancelled(error: DatabaseError) {
                Timber.w(error.toException(), "mobileSession listener cancelled")
            }
        }

        ref.addValueEventListener(listener)
        mobileSessionRef = ref
        mobileSessionListener = listener
    }

    private fun stopSessionConflictListener() {
        mobileSessionListener?.let { listener ->
            mobileSessionRef?.removeEventListener(listener)
        }
        mobileSessionListener = null
        mobileSessionRef = null
        isHandlingSessionConflict = false
    }

    private fun requestNotificationPermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (ContextCompat.checkSelfPermission(
                    this, Manifest.permission.POST_NOTIFICATIONS
                ) != PackageManager.PERMISSION_GRANTED
            ) {
                notificationPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
            }
        }
    }

    private fun checkMinVersion() {
        FirebaseFirestore.getInstance("progress")
            .collection("appConfig").document("android").get()
            .addOnSuccessListener { document ->
                val minVersion = document.getString("minVersion") ?: return@addOnSuccessListener
                val currentVersion = packageManager.getPackageInfo(packageName, 0).versionName
                    ?: return@addOnSuccessListener
                if (isOutdated(currentVersion, minVersion)) {
                    updateRequired = true
                    startImmediateUpdate(currentVersion, minVersion)
                }
            }
            .addOnFailureListener { error ->
                Timber.d(error, "Version check failed")
            }
    }

    private fun isOutdated(current: String, minimum: String): Boolean {
        fun parse(v: String): List<Int> = v.split(".").mapNotNull { it.toIntOrNull() }
        val c = parse(current)
        val m = parse(minimum)
        for (i in 0 until maxOf(c.size, m.size)) {
            val cv = c.getOrElse(i) { 0 }
            val mv = m.getOrElse(i) { 0 }
            if (cv < mv) return true
            if (cv > mv) return false
        }
        return false
    }

    private fun startImmediateUpdate(currentVersion: String, minVersion: String) {
        val appUpdateManager = AppUpdateManagerFactory.create(this)
        appUpdateManager.appUpdateInfo.addOnSuccessListener { info ->
            if (info.updateAvailability() == UpdateAvailability.UPDATE_AVAILABLE
                && info.isUpdateTypeAllowed(AppUpdateType.IMMEDIATE)
            ) {
                appUpdateManager.startUpdateFlowForResult(
                    info,
                    updateLauncher,
                    AppUpdateOptions.newBuilder(AppUpdateType.IMMEDIATE).build(),
                )
            } else {
                // Play Store에 업데이트가 아직 없거나 사이드로드 → 폴백
                showFallbackUpdateDialog(currentVersion, minVersion)
            }
        }.addOnFailureListener {
            Timber.w(it, "AppUpdateManager check failed")
            showFallbackUpdateDialog(currentVersion, minVersion)
        }
    }

    /** 인앱 업데이트 불가 시 Play Store 링크로 안내 */
    private fun showFallbackUpdateDialog(currentVersion: String, minVersion: String) {
        AlertDialog.Builder(this)
            .setTitle(getString(R.string.update_required_title))
            .setMessage(
                getString(R.string.update_required_message) + "\n\n" +
                getString(R.string.update_required_current, currentVersion) + "\n" +
                getString(R.string.update_required_minimum, minVersion)
            )
            .setCancelable(false)
            .setPositiveButton(getString(R.string.update_required_button)) { _, _ ->
                startActivity(Intent(
                    Intent.ACTION_VIEW,
                    Uri.parse("https://play.google.com/store/apps/details?id=$packageName"),
                ))
                finish()
            }
            .show()
    }

    override fun onResume() {
        super.onResume()
        // IMMEDIATE 업데이트 중 앱으로 돌아왔을 때 완료되지 않았으면 재트리거
        if (!updateRequired) return
        val appUpdateManager = AppUpdateManagerFactory.create(this)
        appUpdateManager.appUpdateInfo.addOnSuccessListener { info ->
            if (info.updateAvailability() == UpdateAvailability.DEVELOPER_TRIGGERED_UPDATE_IN_PROGRESS) {
                appUpdateManager.startUpdateFlowForResult(
                    info,
                    updateLauncher,
                    AppUpdateOptions.newBuilder(AppUpdateType.IMMEDIATE).build(),
                )
            }
        }
    }
}
