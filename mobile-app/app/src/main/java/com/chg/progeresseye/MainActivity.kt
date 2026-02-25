package com.chg.progeresseye

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.chg.progeresseye.auth.AuthViewModel
import com.chg.progeresseye.ui.screen.login.LoginScreen
import com.chg.progeresseye.ui.screen.main.MainScreen
import com.chg.progeresseye.ui.theme.ProgressEyeTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            ProgressEyeTheme {
                val authViewModel: AuthViewModel = viewModel()
                val authState by authViewModel.uiState.collectAsStateWithLifecycle()
                val navController = rememberNavController()

                // Skip login if user already has a valid Firebase session
                val startDestination = if (authViewModel.isSignedIn) "main" else "login"

                NavHost(
                    navController = navController,
                    startDestination = startDestination,
                ) {
                    composable("login") {
                        val webClientId = getString(R.string.default_web_client_id)

                        // Navigate to main when sign-in succeeds
                        LaunchedEffect(authState.user) {
                            if (authState.user != null) {
                                navController.navigate("main") {
                                    popUpTo("login") { inclusive = true }
                                }
                            }
                        }

                        LoginScreen(
                            onSignInClick = {
                                authViewModel.signInWithGoogle(
                                    context = this@MainActivity,
                                    webClientId = webClientId,
                                )
                            },
                            isLoading = authState.isLoading,
                            error = authState.error,
                        )
                    }
                    composable("main") {
                        MainScreen()
                    }
                }
            }
        }
    }
}
