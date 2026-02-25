package com.chg.progeresseye.ui.screen.login

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.RemoveRedEye
import androidx.compose.material.icons.outlined.Memory
import androidx.compose.material.icons.outlined.ViewInAr
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.blur
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.draw.scale
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Fill
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.chg.progeresseye.ui.theme.BackgroundDark
import com.chg.progeresseye.ui.theme.Indigo400
import com.chg.progeresseye.ui.theme.Indigo500
import com.chg.progeresseye.ui.theme.OnSurfaceVariantDark
import com.chg.progeresseye.ui.theme.Primary
import com.chg.progeresseye.ui.theme.ProgressEyeTheme
import com.chg.progeresseye.ui.theme.ProgressTrack
import com.chg.progeresseye.ui.theme.SurfaceDark

@Composable
fun LoginScreen(
    onSignInClick: () -> Unit = {},
    modifier: Modifier = Modifier,
) {
    Box(
        modifier = modifier
            .fillMaxSize()
            .background(
                Brush.radialGradient(
                    colors = listOf(Color(0xFF1C2738), BackgroundDark),
                    center = Offset(0.5f, 0f),
                    radius = 1200f,
                ),
            ),
    ) {
        // Decorative background blurred circles
        Box(
            modifier = Modifier
                .size(320.dp)
                .align(Alignment.TopEnd)
                .offset(x = 80.dp, y = (-80).dp)
                .blur(120.dp)
                .background(Primary.copy(alpha = 0.05f), CircleShape),
        )
        Box(
            modifier = Modifier
                .size(256.dp)
                .align(Alignment.BottomStart)
                .offset(x = (-80).dp, y = 80.dp)
                .blur(120.dp)
                .background(Indigo500.copy(alpha = 0.05f), CircleShape),
        )

        // Main content
        Column(
            modifier = Modifier.fillMaxSize(),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            // Center content area (takes remaining space above buttons)
            Column(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth()
                    .padding(horizontal = 24.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center,
            ) {
                // Logo
                LogoSection()

                Spacer(modifier = Modifier.height(24.dp))

                // Title + Subtitle
                Text(
                    text = "ProgressEye",
                    style = MaterialTheme.typography.headlineLarge,
                    color = Color.White,
                    fontWeight = FontWeight.Bold,
                    letterSpacing = (-0.5).sp,
                )

                Spacer(modifier = Modifier.height(12.dp))

                Text(
                    text = "Monitor your progress\nanywhere, safely.",
                    style = MaterialTheme.typography.bodyLarge,
                    color = OnSurfaceVariantDark,
                    textAlign = TextAlign.Center,
                    lineHeight = 26.sp,
                    modifier = Modifier.widthIn(max = 320.dp),
                )

                Spacer(modifier = Modifier.height(32.dp))

                // Preview card
                PreviewCard()
            }

            // Bottom action area
            BottomActions(onSignInClick = onSignInClick)
        }
    }
}

// ── Logo Section ──

@Composable
private fun LogoSection() {
    Box(
        modifier = Modifier.size(160.dp),
        contentAlignment = Alignment.Center,
    ) {
        // Glow behind circle
        Box(
            modifier = Modifier
                .size(160.dp)
                .blur(48.dp)
                .background(Primary.copy(alpha = 0.20f), CircleShape),
        )

        // Circle container
        Box(
            modifier = Modifier
                .size(128.dp)
                .clip(CircleShape)
                .background(SurfaceDark)
                .border(1.dp, Primary.copy(alpha = 0.20f), CircleShape),
            contentAlignment = Alignment.Center,
        ) {
            // Eye icon
            Icon(
                imageVector = Icons.Outlined.RemoveRedEye,
                contentDescription = "ProgressEye logo",
                tint = Primary,
                modifier = Modifier.size(64.dp),
            )

            // Small progress bar at bottom of circle
            Box(
                modifier = Modifier
                    .align(Alignment.BottomCenter)
                    .padding(bottom = 24.dp),
            ) {
                // Track
                Box(
                    modifier = Modifier
                        .width(64.dp)
                        .height(6.dp)
                        .clip(RoundedCornerShape(3.dp))
                        .background(ProgressTrack),
                )
                // Fill (66%)
                Box(
                    modifier = Modifier
                        .width(42.dp)
                        .height(6.dp)
                        .clip(RoundedCornerShape(3.dp))
                        .background(Primary),
                )
            }
        }
    }
}

// ── Preview Card ──

@Composable
private fun PreviewCard() {
    Column(
        modifier = Modifier
            .widthIn(max = 320.dp)
            .fillMaxWidth()
            .clip(RoundedCornerShape(16.dp))
            .background(SurfaceDark.copy(alpha = 0.5f))
            .border(1.dp, Color.White.copy(alpha = 0.05f), RoundedCornerShape(16.dp))
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        // Row 1: Rendering progress
        ProgressRow(
            icon = { ProgressIcon(Primary) { Icon(Icons.Outlined.ViewInAr, null, tint = Primary, modifier = Modifier.size(20.dp)) } },
            label = "Rendering Scene 04",
            percentage = "78%",
            percentageColor = Primary,
            progress = 0.78f,
            progressColor = Primary,
            alpha = 1f,
        )

        // Row 2: Training progress (dimmed)
        ProgressRow(
            icon = { ProgressIcon(Indigo500) { Icon(Icons.Outlined.Memory, null, tint = Indigo400, modifier = Modifier.size(20.dp)) } },
            label = "Training Epoch 12",
            percentage = "42%",
            percentageColor = Indigo400,
            progress = 0.42f,
            progressColor = Indigo500,
            alpha = 0.6f,
        )
    }
}

@Composable
private fun ProgressIcon(
    accentColor: Color,
    content: @Composable () -> Unit,
) {
    Box(
        modifier = Modifier
            .size(40.dp)
            .clip(RoundedCornerShape(8.dp))
            .background(accentColor.copy(alpha = 0.20f)),
        contentAlignment = Alignment.Center,
    ) {
        content()
    }
}

@Composable
private fun ProgressRow(
    icon: @Composable () -> Unit,
    label: String,
    percentage: String,
    percentageColor: Color,
    progress: Float,
    progressColor: Color,
    alpha: Float,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .alpha(alpha),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        icon()

        Column(
            modifier = Modifier.weight(1f),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                Text(
                    text = label,
                    style = MaterialTheme.typography.labelSmall,
                    color = OnSurfaceVariantDark,
                    fontWeight = FontWeight.Medium,
                )
                Text(
                    text = percentage,
                    style = MaterialTheme.typography.labelSmall,
                    color = percentageColor,
                    fontWeight = FontWeight.Medium,
                )
            }

            // Progress bar
            ProgressBar(progress = progress, color = progressColor)
        }
    }
}

@Composable
private fun ProgressBar(
    progress: Float,
    color: Color,
    modifier: Modifier = Modifier,
) {
    val trackColor = ProgressTrack
    Canvas(
        modifier = modifier
            .fillMaxWidth()
            .height(6.dp)
            .clip(RoundedCornerShape(3.dp)),
    ) {
        // Track
        drawRoundRect(
            color = trackColor,
            cornerRadius = CornerRadius(3.dp.toPx()),
        )
        // Fill
        drawRoundRect(
            color = color,
            size = Size(size.width * progress, size.height),
            cornerRadius = CornerRadius(3.dp.toPx()),
        )
    }
}

// ── Bottom Actions ──

@Composable
private fun BottomActions(onSignInClick: () -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(
                Brush.verticalGradient(
                    colors = listOf(Color.Transparent, BackgroundDark),
                    startY = 0f,
                    endY = 100f,
                ),
            )
            .padding(horizontal = 24.dp)
            .padding(bottom = 48.dp, top = 16.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        // Google Sign-In Button
        GoogleSignInButton(onClick = onSignInClick)

        // Terms text
        Row(
            horizontalArrangement = Arrangement.spacedBy(4.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                text = "By continuing you agree to our",
                style = MaterialTheme.typography.bodySmall,
                color = Color(0xFF64748B), // slate-500
            )
            Text(
                text = "Terms",
                style = MaterialTheme.typography.bodySmall,
                color = OnSurfaceVariantDark,
                textDecoration = TextDecoration.Underline,
                modifier = Modifier.clickable { /* TODO */ },
            )
        }
    }
}

@Composable
private fun GoogleSignInButton(onClick: () -> Unit) {
    val interactionSource = remember { MutableInteractionSource() }
    val isPressed by interactionSource.collectIsPressedAsState()
    val scale by animateFloatAsState(
        targetValue = if (isPressed) 0.98f else 1f,
        animationSpec = tween(100),
        label = "button-scale",
    )

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .scale(scale)
            .clip(RoundedCornerShape(12.dp))
            .background(Color.White)
            .clickable(interactionSource = interactionSource, indication = null, onClick = onClick)
            .padding(vertical = 16.dp),
        horizontalArrangement = Arrangement.Center,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        // Google icon (simplified 4-color "G")
        GoogleIcon(modifier = Modifier.size(20.dp))

        Spacer(modifier = Modifier.width(12.dp))

        Text(
            text = "Sign in with Google",
            style = MaterialTheme.typography.labelLarge,
            color = Color(0xFF0F172A), // slate-900
            fontSize = 16.sp,
        )
    }
}

@Composable
private fun GoogleIcon(modifier: Modifier = Modifier) {
    Canvas(modifier = modifier) {
        val w = size.width
        val h = size.height
        val cx = w / 2f
        val cy = h / 2f

        // Simplified Google "G" using colored arcs
        val blue = Color(0xFF4285F4)
        val green = Color(0xFF34A853)
        val yellow = Color(0xFFFBBC05)
        val red = Color(0xFFEA4335)
        val strokeWidth = w * 0.22f
        val radius = w * 0.38f

        // Blue (right arc, top-right to bottom-right)
        drawArc(
            color = blue,
            startAngle = -45f,
            sweepAngle = 90f,
            useCenter = true,
            topLeft = Offset(cx - radius, cy - radius),
            size = Size(radius * 2, radius * 2),
        )
        // Green (bottom-right arc)
        drawArc(
            color = green,
            startAngle = 45f,
            sweepAngle = 90f,
            useCenter = true,
            topLeft = Offset(cx - radius, cy - radius),
            size = Size(radius * 2, radius * 2),
        )
        // Yellow (bottom-left arc)
        drawArc(
            color = yellow,
            startAngle = 135f,
            sweepAngle = 90f,
            useCenter = true,
            topLeft = Offset(cx - radius, cy - radius),
            size = Size(radius * 2, radius * 2),
        )
        // Red (top-left arc)
        drawArc(
            color = red,
            startAngle = 225f,
            sweepAngle = 90f,
            useCenter = true,
            topLeft = Offset(cx - radius, cy - radius),
            size = Size(radius * 2, radius * 2),
        )

        // Inner white circle to make it look like a "G"
        drawCircle(
            color = Color.White,
            radius = radius * 0.55f,
            center = Offset(cx, cy),
        )

        // Blue bar (right side of G)
        val barWidth = w * 0.28f
        val barHeight = h * 0.18f
        drawRect(
            color = blue,
            topLeft = Offset(cx - barWidth * 0.1f, cy - barHeight / 2f),
            size = Size(radius + barWidth * 0.1f, barHeight),
        )
    }
}

// ── Preview ──

@Preview(showBackground = true, showSystemUi = true)
@Composable
private fun LoginScreenPreview() {
    ProgressEyeTheme {
        LoginScreen()
    }
}
