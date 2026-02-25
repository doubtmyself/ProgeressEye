package com.chg.progeresseye

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import com.chg.progeresseye.ui.screen.login.LoginScreen
import com.chg.progeresseye.ui.theme.ProgressEyeTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            ProgressEyeTheme {
                LoginScreen(
                    onSignInClick = { /* TODO: Google Sign-In */ },
                )
            }
        }
    }
}