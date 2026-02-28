package com.chg.progeresseye

import android.os.Bundle
import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import timber.log.Timber
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.chg.progeresseye.auth.AuthViewModel
import com.chg.progeresseye.auth.MobileSessionManager
import com.chg.progeresseye.service.FCMService
import com.chg.progeresseye.ui.screen.login.LoginScreen
import com.chg.progeresseye.ui.screen.main.MainScreen
import com.chg.progeresseye.ui.theme.ProgressEyeTheme
import com.google.android.gms.ads.MobileAds
import com.google.firebase.database.DatabaseReference
import com.google.firebase.database.FirebaseDatabase
import com.google.firebase.database.ValueEventListener
import com.google.firebase.database.DatabaseError
import com.google.firebase.database.DataSnapshot
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {
    private var mobileSessionRef: DatabaseReference? = null
    private var mobileSessionListener: ValueEventListener? = null
    private var isHandlingSessionConflict: Boolean = false

    private val notificationPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { /* granted or denied — no action needed */ }

    override fun onCreate(savedInstanceState: Bundle?) {
        // installSplashScreen() MUST be called BEFORE super.onCreate()
        val splashScreen = installSplashScreen()
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

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

                // Start destination is driven by AuthUiState, not raw FirebaseAuth state.
                // This prevents auto-navigation to main while takeover confirmation is pending.
                val startDestination = if (
                    authState.user != null && !authState.requiresSessionTakeover
                ) {
                    "main"
                } else {
                    "login"
                }

                LaunchedEffect(authState.user, authState.requiresSessionTakeover) {
                    val currentRoute = navController.currentDestination?.route
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
                    startDestination = startDestination,
                ) {
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

        CoroutineScope(Dispatchers.IO).launch {
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
}
