package com.chg.progeresseye.ui.screen.splash

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.draw.scale
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.chg.progeresseye.R
import com.chg.progeresseye.ui.theme.OnSurfaceDark
import com.chg.progeresseye.ui.theme.OnSurfaceVariantDark
import com.chg.progeresseye.ui.theme.Primary
import com.chg.progeresseye.ui.theme.ProgressEyeTheme
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

// ── Splash-local palette ──
private val SplashBg = Color(0xFF0F0F1A)
private val TrackColor = Color(0xFF1A1A2E)
private val GradientBlueStart = Color(0xFF3B82F6)
private val GradientBlueEnd = Color(0xFF60A5FA)

// ═════════════════════════════════════════════════════════
// SplashScreen — branded loading with animated progress bar
// ═════════════════════════════════════════════════════════

@Composable
fun SplashScreen(
    onFinished: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val currentOnFinished by rememberUpdatedState(onFinished)
    val progress = remember { Animatable(0f) }
    val contentAlpha = remember { Animatable(0f) }
    val iconScale = remember { Animatable(0.85f) }

    LaunchedEffect(Unit) {
        // Staggered reveal: fade-in + scale icon, then fill progress bar
        launch { contentAlpha.animateTo(1f, tween(500, easing = FastOutSlowInEasing)) }
        launch { iconScale.animateTo(1f, tween(600, easing = FastOutSlowInEasing)) }
        progress.animateTo(1f, tween(durationMillis = 2000, easing = FastOutSlowInEasing))
        delay(200)
        currentOnFinished()
    }

    Box(
        modifier = modifier
            .fillMaxSize()
            .background(SplashBg)
            .drawBehind {
                // Soft radial glow behind the icon area
                val center = Offset(size.width / 2f, size.height * 0.40f)
                val glowRadius = size.height * 0.28f
                drawCircle(
                    brush = Brush.radialGradient(
                        colors = listOf(
                            Primary.copy(alpha = 0.08f),
                            Color(0xFF12122A),
                            SplashBg,
                        ),
                        center = center,
                        radius = glowRadius,
                    ),
                    radius = glowRadius,
                    center = center,
                )
            },
        contentAlignment = Alignment.Center,
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            modifier = Modifier
                .offset(y = (-32).dp)
                .alpha(contentAlpha.value),
        ) {
            // App icon
            Image(
                painter = painterResource(id = R.mipmap.ic_launcher),
                contentDescription = "ProgressEye",
                modifier = Modifier
                    .size(96.dp)
                    .scale(iconScale.value),
            )

            Spacer(modifier = Modifier.height(20.dp))

            // App name
            Text(
                text = "ProgressEye",
                style = MaterialTheme.typography.headlineMedium,
                fontWeight = FontWeight.Bold,
                color = OnSurfaceDark,
                letterSpacing = (-0.5).sp,
            )

            Spacer(modifier = Modifier.height(8.dp))

            // Tagline
            Text(
                text = "Monitor your progress",
                style = MaterialTheme.typography.bodyMedium,
                color = OnSurfaceVariantDark,
            )

            Spacer(modifier = Modifier.height(36.dp))

            // Animated gradient progress bar
            SplashProgressBar(
                progress = progress.value,
                modifier = Modifier
                    .width(200.dp)
                    .height(6.dp),
            )
        }
    }
}

// ═════════════════════════════════════════════════════════
// Progress bar — gradient fill over dark track
// ═════════════════════════════════════════════════════════

@Composable
private fun SplashProgressBar(
    progress: Float,
    modifier: Modifier = Modifier,
) {
    Canvas(modifier = modifier) {
        val cr = CornerRadius(size.height / 2f)

        // Track
        drawRoundRect(color = TrackColor, cornerRadius = cr)

        // Gradient fill
        if (progress > 0f) {
            val fillWidth = size.width * progress.coerceIn(0f, 1f)
            drawRoundRect(
                brush = Brush.horizontalGradient(
                    colors = listOf(GradientBlueStart, GradientBlueEnd),
                    startX = 0f,
                    endX = size.width,
                ),
                size = Size(fillWidth, size.height),
                cornerRadius = cr,
            )
        }
    }
}

// ═════════════════════════════════════════════════════════
// Preview
// ═════════════════════════════════════════════════════════

@Preview(showBackground = true, showSystemUi = true)
@Composable
private fun SplashScreenPreview() {
    ProgressEyeTheme {
        SplashScreen(onFinished = {})
    }
}
