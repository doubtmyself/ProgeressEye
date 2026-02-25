package com.chg.progeresseye

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.chg.progeresseye.ui.screen.login.LoginScreen
import com.chg.progeresseye.ui.screen.main.MainScreen
import com.chg.progeresseye.ui.theme.ProgressEyeTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            ProgressEyeTheme {
                val navController = rememberNavController()
                NavHost(
                    navController = navController,
                    startDestination = "login",
                ) {
                    composable("login") {
                        LoginScreen(
                            onSignInClick = {
                                // TODO: Google Sign-In 실제 인증 구현 (추후 작업)
                                navController.navigate("main") {
                                    popUpTo("login") { inclusive = true }
                                }
                            },
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