package com.chg.progeresseye.ui.screen.login

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Memory
import androidx.compose.material.icons.outlined.RemoveRedEye
import androidx.compose.material.icons.outlined.ViewInAr
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CheckboxDefaults
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.key
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.layout.positionInRoot
import androidx.compose.ui.draw.scale
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.foundation.text.ClickableText
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.chg.progeresseye.R
import com.chg.progeresseye.ui.theme.BackgroundDark
import com.chg.progeresseye.ui.theme.Indigo400
import com.chg.progeresseye.ui.theme.Indigo500
import com.chg.progeresseye.ui.theme.OnSurfaceDark
import com.chg.progeresseye.ui.theme.OnSurfaceVariantDark
import com.chg.progeresseye.ui.theme.Primary
import com.chg.progeresseye.ui.theme.ProgressEyeTheme
import com.chg.progeresseye.ui.theme.ProgressTrack
import com.chg.progeresseye.ui.theme.SurfaceContainerDark
import com.chg.progeresseye.ui.theme.SurfaceDark
import kotlinx.coroutines.delay
import kotlin.random.Random

// ── Local palette (not in theme) ──
private val Slate400 = Color(0xFF94A3B8)
private val Slate500 = Color(0xFF64748B)
private val Slate900 = Color(0xFF0F172A)
private val WhiteAlpha5 = Color(0x0DFFFFFF)
private val GoogleBlue = Color(0xFF4285F4)
private val GoogleRed = Color(0xFFEA4335)
private val GoogleYellow = Color(0xFFFBBC05)
private val GoogleGreen = Color(0xFF34A853)

private data class TaskTemplate(
    val labelRes: Int,
    val icon: ImageVector,
    val iconTint: Color,
    val iconBackground: Color,
    val barColor: Color,
)

private data class AnimatedTaskRow(
    val id: Int,
    val template: TaskTemplate,
    val rowAlpha: Float,
    val targetFraction: Float,
    val exiting: Boolean,
    val progressStep: Float,
)

private fun randomProgressStep(): Float = Random.nextFloat() * (0.024f - 0.010f) + 0.010f

private val TaskTemplates = listOf(
    TaskTemplate(
        labelRes = R.string.login_task_sample_01,
        icon = Icons.Outlined.ViewInAr,
        iconTint = Primary,
        iconBackground = Primary.copy(alpha = 0.20f),
        barColor = Primary,
    ),
    TaskTemplate(
        labelRes = R.string.login_task_sample_02,
        icon = Icons.Outlined.Memory,
        iconTint = Indigo400,
        iconBackground = Indigo500.copy(alpha = 0.20f),
        barColor = Indigo500,
    ),
    TaskTemplate(
        labelRes = R.string.login_task_sample_03,
        icon = Icons.Outlined.RemoveRedEye,
        iconTint = Primary,
        iconBackground = Primary.copy(alpha = 0.18f),
        barColor = Primary,
    ),
    TaskTemplate(
        labelRes = R.string.login_task_sample_04,
        icon = Icons.Outlined.ViewInAr,
        iconTint = Indigo400,
        iconBackground = Indigo500.copy(alpha = 0.20f),
        barColor = Indigo500,
    ),
    TaskTemplate(
        labelRes = R.string.login_task_sample_05,
        icon = Icons.Outlined.Memory,
        iconTint = Primary,
        iconBackground = Primary.copy(alpha = 0.16f),
        barColor = Primary,
    ),
    TaskTemplate(
        labelRes = R.string.login_task_sample_06,
        icon = Icons.Outlined.RemoveRedEye,
        iconTint = Indigo400,
        iconBackground = Indigo500.copy(alpha = 0.18f),
        barColor = Indigo500,
    ),
    TaskTemplate(
        labelRes = R.string.login_task_sample_07,
        icon = Icons.Outlined.ViewInAr,
        iconTint = Primary,
        iconBackground = Primary.copy(alpha = 0.20f),
        barColor = Primary,
    ),
    TaskTemplate(
        labelRes = R.string.login_task_sample_08,
        icon = Icons.Outlined.Memory,
        iconTint = Indigo400,
        iconBackground = Indigo500.copy(alpha = 0.20f),
        barColor = Indigo500,
    ),
    TaskTemplate(
        labelRes = R.string.login_task_sample_09,
        icon = Icons.Outlined.RemoveRedEye,
        iconTint = Primary,
        iconBackground = Primary.copy(alpha = 0.18f),
        barColor = Primary,
    ),
    TaskTemplate(
        labelRes = R.string.login_task_sample_10,
        icon = Icons.Outlined.ViewInAr,
        iconTint = Indigo400,
        iconBackground = Indigo500.copy(alpha = 0.20f),
        barColor = Indigo500,
    ),
)

// ═════════════════════════════════════════════════════════
// LoginScreen
// ═════════════════════════════════════════════════════════

@Composable
fun LoginScreen(
    onSignInClick: () -> Unit = {},
    onConfirmSessionTakeover: () -> Unit = {},
    onCancelSessionTakeover: () -> Unit = {},
    onConfirmWithdrawalCancel: () -> Unit = {},
    onKeepWithdrawal: () -> Unit = {},
    isLoading: Boolean = false,
    error: String? = null,
    requiresSessionTakeover: Boolean = false,
    existingDeviceName: String? = null,
    requiresWithdrawalCancel: Boolean = false,
    withdrawalGraceEndDate: String? = null,
    modifier: Modifier = Modifier,
) {
    // Track the logo circle's center in root coordinates
    var logoCenterInRoot by remember { mutableStateOf(Offset.Unspecified) }

    Box(
        modifier = modifier
            .fillMaxSize()
            .background(BackgroundDark)
            .drawBehind {
                val center = if (logoCenterInRoot != Offset.Unspecified) {
                    logoCenterInRoot
                } else {
                    Offset(size.width / 2f, size.height * 0.30f)
                }
                val glowRadius = size.height * 0.35f
                drawCircle(
                    brush = Brush.radialGradient(
                        colors = listOf(
                            Primary.copy(alpha = 0.08f),
                            Color(0xFF1A2540),
                            BackgroundDark,
                        ),
                        center = center,
                        radius = glowRadius,
                    ),
                    radius = glowRadius,
                    center = center,
                )
            },
    ) {
        if (requiresWithdrawalCancel) {
            AlertDialog(
                onDismissRequest = onKeepWithdrawal,
                title = { Text(text = stringResource(R.string.withdrawal_pending_title)) },
                text = {
                    Text(
                        text = stringResource(
                            R.string.withdrawal_pending_message,
                            withdrawalGraceEndDate ?: "-",
                        ),
                    )
                },
                confirmButton = {
                    TextButton(onClick = onConfirmWithdrawalCancel) {
                        Text(text = stringResource(R.string.withdrawal_cancel_yes))
                    }
                },
                dismissButton = {
                    TextButton(onClick = onKeepWithdrawal) {
                        Text(text = stringResource(R.string.withdrawal_cancel_no))
                    }
                },
            )
        } else if (requiresSessionTakeover) {
            AlertDialog(
                onDismissRequest = onCancelSessionTakeover,
                title = { Text(text = stringResource(R.string.session_takeover_title)) },
                text = {
                    Text(
                        text = stringResource(
                            R.string.session_takeover_message,
                            existingDeviceName ?: stringResource(R.string.session_takeover_unknown_device),
                        ),
                    )
                },
                confirmButton = {
                    TextButton(onClick = onConfirmSessionTakeover) {
                        Text(text = stringResource(R.string.session_takeover_confirm))
                    }
                },
                dismissButton = {
                    TextButton(onClick = onCancelSessionTakeover) {
                        Text(text = stringResource(R.string.session_takeover_cancel))
                    }
                },
            )
        }

        // ── Main vertical layout ──
        Column(
            modifier = Modifier.fillMaxSize(),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            // Center content (weight pushes bottom actions down)
            Column(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth()
                    .padding(horizontal = 24.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center,
            ) {
                LogoSection(
                    onCirclePositioned = { logoCenterInRoot = it },
                )
                Spacer(modifier = Modifier.height(24.dp))
                TextSection()
                Spacer(modifier = Modifier.height(32.dp))
                PreviewCard()
            }

            // Bottom pinned area
            BottomActions(onSignInClick = onSignInClick, isLoading = isLoading, error = error)
        }
    }
}

// ═════════════════════════════════════════════════════════
// 1. Logo — 160dp area, 128dp circle, eye icon, mini bar
// ═════════════════════════════════════════════════════════

@Composable
private fun LogoSection(
    onCirclePositioned: (Offset) -> Unit = {},
) {
    Box(
        modifier = Modifier.size(160.dp),
        contentAlignment = Alignment.Center,
    ) {
        // Primary glow — large soft spread behind the circle
        Box(
            modifier = Modifier
                .size(200.dp)
                .drawBehind {
                    drawCircle(
                        brush = Brush.radialGradient(
                            colors = listOf(
                                Primary.copy(alpha = 0.18f),
                                Primary.copy(alpha = 0.06f),
                                Color.Transparent,
                            ),
                        ),
                        radius = size.minDimension / 2f,
                    )
                },
        )

        // Circle + icon, then progress bar below
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Box(
                modifier = Modifier
                    .size(128.dp)
                    .onGloballyPositioned { coords ->
                        val pos = coords.positionInRoot()
                        onCirclePositioned(
                            Offset(
                                pos.x + coords.size.width / 2f,
                                pos.y + coords.size.height / 2f,
                            ),
                        )
                    }
                    .drawBehind {
                        drawCircle(
                            color = Primary.copy(alpha = 0.20f),
                            radius = size.minDimension / 2f,
                        )
                        drawCircle(
                            color = SurfaceDark,
                            radius = size.minDimension / 2f - 1.dp.toPx(),
                        )
                    },
                contentAlignment = Alignment.Center,
            ) {
                Icon(
                    imageVector = Icons.Outlined.RemoveRedEye,
                    contentDescription = stringResource(R.string.cd_app_logo),
                    tint = Primary,
                    modifier = Modifier.size(64.dp),
                )
            }

            Spacer(modifier = Modifier.height(8.dp))

            // Mini progress bar (64×6, 66% fill)
            MiniProgressBar(
                fraction = 0.66f,
                fillColor = Primary,
                modifier = Modifier
                    .width(64.dp)
                    .height(6.dp),
            )
        }
    }
}

// ═════════════════════════════════════════════════════════
// 2. Text — title + subtitle
// ═════════════════════════════════════════════════════════

@Composable
private fun TextSection() {
    Text(
        text = "ProgressEye",
        style = MaterialTheme.typography.headlineLarge,
        fontWeight = FontWeight.Bold,
        color = OnSurfaceDark,
        letterSpacing = (-0.5).sp,
    )
    Spacer(modifier = Modifier.height(8.dp))
    Text(
        text = stringResource(R.string.login_subtitle),
        style = MaterialTheme.typography.bodyLarge,
        color = Slate400,
        textAlign = TextAlign.Center,
        modifier = Modifier.widthIn(max = 320.dp),
    )
}

// ═════════════════════════════════════════════════════════
// 3. Preview card — glass surface
// ═════════════════════════════════════════════════════════

@Composable
private fun PreviewCard() {
    val rows = remember {
        mutableStateListOf(
            AnimatedTaskRow(
                id = 1,
                template = TaskTemplates[0],
                rowAlpha = 1f,
                targetFraction = 0.10f,
                exiting = false,
                progressStep = randomProgressStep(),
            ),
            AnimatedTaskRow(
                id = 2,
                template = TaskTemplates[1],
                rowAlpha = 0.6f,
                targetFraction = 0.06f,
                exiting = false,
                progressStep = randomProgressStep(),
            ),
        )
    }
    var nextId by remember { mutableIntStateOf(3) }
    var nextTemplateIndex by remember { mutableIntStateOf(2) }
    val removalDeadlines = remember { mutableStateMapOf<Int, Long>() }

    LaunchedEffect(Unit) {
        while (true) {
            while (rows.size < 2) {
                rows += AnimatedTaskRow(
                    id = nextId,
                    template = TaskTemplates[nextTemplateIndex % TaskTemplates.size],
                    rowAlpha = if (rows.isEmpty()) 1f else 0.6f,
                    targetFraction = 0f,
                    exiting = false,
                    progressStep = randomProgressStep(),
                )
                nextId += 1
                nextTemplateIndex += 1
            }

            val now = System.currentTimeMillis()
            val dueIds = removalDeadlines
                .filterValues { deadline -> deadline <= now }
                .keys
                .toList()
            dueIds.forEach { rowId ->
                removalDeadlines.remove(rowId)
                rows.removeAll { it.id == rowId }
                rows += AnimatedTaskRow(
                    id = nextId,
                    template = TaskTemplates[nextTemplateIndex % TaskTemplates.size],
                    rowAlpha = 0.6f,
                    targetFraction = 0f,
                    exiting = false,
                    progressStep = randomProgressStep(),
                )
                nextId += 1
                nextTemplateIndex += 1
            }

            for (index in rows.indices) {
                val current = rows[index]
                if (current.exiting) {
                    continue
                }
                val nextFraction = (current.targetFraction + current.progressStep).coerceAtMost(1f)
                if (nextFraction >= 1f) {
                    rows[index] = current.copy(targetFraction = 1f, exiting = true)
                    removalDeadlines[current.id] = now + 520L
                } else {
                    rows[index] = current.copy(targetFraction = nextFraction)
                }
            }

            if (rows.isNotEmpty()) {
                rows[0] = rows[0].copy(rowAlpha = 1f)
            }
            if (rows.size >= 2) {
                rows[1] = rows[1].copy(rowAlpha = 0.6f)
            }

            delay(140)
        }
    }

    Surface(
        shape = RoundedCornerShape(16.dp),
        color = SurfaceDark.copy(alpha = 0.50f),
        border = BorderStroke(1.dp, WhiteAlpha5),
        modifier = Modifier.widthIn(max = 320.dp),
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            rows.forEach { row ->
                key(row.id) {
                    AnimatedVisibility(
                        visible = !row.exiting,
                        enter = fadeIn(animationSpec = tween(260)) +
                            slideInVertically(
                                initialOffsetY = { it / 3 },
                                animationSpec = tween(260),
                            ),
                        exit = fadeOut(animationSpec = tween(420)) +
                            slideOutVertically(
                                targetOffsetY = { it / 2 },
                                animationSpec = tween(420),
                            ),
                    ) {
                        TaskProgressRow(
                            icon = row.template.icon,
                            iconTint = row.template.iconTint,
                            iconBackground = row.template.iconBackground,
                            label = stringResource(row.template.labelRes),
                            percentColor = row.template.barColor,
                            fraction = row.targetFraction,
                            barColor = row.template.barColor,
                            rowAlpha = row.rowAlpha,
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun TaskIcon(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    tint: Color,
    background: Color,
) {
    Box(
        modifier = Modifier
            .size(40.dp)
            .clip(RoundedCornerShape(8.dp))
            .background(background),
        contentAlignment = Alignment.Center,
    ) {
        Icon(
            imageVector = icon,
            contentDescription = null,
            tint = tint,
            modifier = Modifier.size(20.dp),
        )
    }
}

@Composable
private fun TaskProgressRow(
    icon: ImageVector,
    iconTint: Color,
    iconBackground: Color,
    label: String,
    percentColor: Color,
    fraction: Float,
    barColor: Color,
    rowAlpha: Float,
) {
    val animatedFraction by animateFloatAsState(
        targetValue = fraction.coerceIn(0f, 1f),
        animationSpec = tween(durationMillis = 420),
        label = "task_row_progress",
    )
    val percent = "${(animatedFraction * 100f).toInt()}%"

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .alpha(rowAlpha),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        TaskIcon(icon = icon, tint = iconTint, background = iconBackground)

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
                    color = Slate400,
                )
                Text(
                    text = percent,
                    style = MaterialTheme.typography.labelSmall,
                    color = percentColor,
                )
            }
            MiniProgressBar(
                fraction = animatedFraction,
                fillColor = barColor,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(6.dp),
            )
        }
    }
}

// ═════════════════════════════════════════════════════════
// Mini progress bar (Canvas, reusable)
// ═════════════════════════════════════════════════════════

@Composable
private fun MiniProgressBar(
    fraction: Float,
    fillColor: Color,
    modifier: Modifier = Modifier,
) {
    Canvas(modifier = modifier) {
        val cr = CornerRadius(size.height / 2f)
        drawRoundRect(color = ProgressTrack, cornerRadius = cr)
        if (fraction > 0f) {
            drawRoundRect(
                color = fillColor,
                size = Size(size.width * fraction.coerceIn(0f, 1f), size.height),
                cornerRadius = cr,
            )
        }
    }
}

// ═════════════════════════════════════════════════════════
// Bottom actions — gradient fade + Google button + terms
// ═════════════════════════════════════════════════════════

@Composable
private fun BottomActions(
    onSignInClick: () -> Unit,
    isLoading: Boolean = false,
    error: String? = null,
) {
    var termsAccepted by remember { mutableStateOf(false) }

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
            .padding(bottom = 48.dp, top = 24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        error?.let {
            Text(
                text = it,
                style = MaterialTheme.typography.bodySmall,
                color = Color(0xFFEF4444),
                textAlign = TextAlign.Center,
            )
        }
        TermsRow(checked = termsAccepted, onCheckedChange = { termsAccepted = it })
        GoogleSignInButton(
            onClick = onSignInClick,
            isLoading = isLoading,
            enabled = termsAccepted,
        )
    }
}

// ═════════════════════════════════════════════════════════
// Google Sign-In button — white bg, scale press effect
// ═════════════════════════════════════════════════════════

@Composable
private fun GoogleSignInButton(
    onClick: () -> Unit,
    isLoading: Boolean = false,
    enabled: Boolean = true,
) {
    val interactionSource = remember { MutableInteractionSource() }
    val isPressed by interactionSource.collectIsPressedAsState()
    val scale by animateFloatAsState(
        targetValue = if (isPressed) 0.98f else 1f,
        animationSpec = tween(100),
        label = "btn_scale",
    )

    val isEnabled = enabled && !isLoading

    Surface(
        onClick = onClick,
        shape = RoundedCornerShape(12.dp),
        color = if (isEnabled) Color.White else Color.White.copy(alpha = 0.4f),
        enabled = isEnabled,
        interactionSource = interactionSource,
        modifier = Modifier
            .fillMaxWidth()
            .scale(scale),
    ) {
        Row(
            modifier = Modifier.padding(vertical = 16.dp),
            horizontalArrangement = Arrangement.Center,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            if (isLoading) {
                androidx.compose.material3.CircularProgressIndicator(
                    modifier = Modifier.size(20.dp),
                    strokeWidth = 2.dp,
                    color = Slate900,
                )
            } else {
                GoogleColorIcon(modifier = Modifier.size(20.dp))
            }
            Spacer(modifier = Modifier.width(12.dp))
            Text(
                text = if (isLoading) stringResource(R.string.login_signing_in) else stringResource(R.string.login_sign_in_google),
                style = MaterialTheme.typography.labelLarge.copy(
                    fontWeight = FontWeight.Bold,
                    fontSize = 16.sp,
                ),
                color = if (isEnabled) Slate900 else Slate900.copy(alpha = 0.5f),
            )
        }
    }
}

// ═════════════════════════════════════════════════════════
// Google 4-color "G" icon (stroke arcs + bar)
// ═════════════════════════════════════════════════════════

@Composable
private fun GoogleColorIcon(modifier: Modifier = Modifier) {
    Canvas(modifier = modifier) {
        val s = size.minDimension
        val sw = s * 0.22f
        val r = s / 2f - sw / 2f
        val c = Offset(s / 2f, s / 2f)
        val arcSize = Size(r * 2, r * 2)
        val arcTopLeft = Offset(c.x - r, c.y - r)
        val stroke = Stroke(width = sw)

        // Blue — right (-45° → 45°)
        drawArc(GoogleBlue, -45f, 90f, false, arcTopLeft, arcSize, style = stroke)
        // Green — bottom-right (45° → 135°)
        drawArc(GoogleGreen, 45f, 90f, false, arcTopLeft, arcSize, style = stroke)
        // Yellow — bottom-left (135° → 195°)
        drawArc(GoogleYellow, 135f, 60f, false, arcTopLeft, arcSize, style = stroke)
        // Red — top-left (195° → 315°)
        drawArc(GoogleRed, 195f, 120f, false, arcTopLeft, arcSize, style = stroke)
        // Horizontal bar of "G"
        drawLine(
            color = GoogleBlue,
            start = Offset(c.x - sw * 0.1f, c.y),
            end = Offset(c.x + r + sw / 2f, c.y),
            strokeWidth = sw,
        )
    }
}

// ═════════════════════════════════════════════════════════
// Terms — "By continuing you agree to our Terms"
// ═════════════════════════════════════════════════════════

@Composable
private fun TermsRow(
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit,
) {
    val uriHandler = LocalUriHandler.current

    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier = Modifier.fillMaxWidth(),
    ) {
        Checkbox(
            checked = checked,
            onCheckedChange = onCheckedChange,
            colors = CheckboxDefaults.colors(
                checkedColor = Primary,
                uncheckedColor = Slate500,
                checkmarkColor = Color.White,
            ),
        )
        val prefix = stringResource(R.string.login_terms_prefix)
        val tosLink = stringResource(R.string.login_terms_link)
        val mid = stringResource(R.string.login_terms_mid)
        val ppLink = stringResource(R.string.login_terms_privacy_link)
        val suffix = stringResource(R.string.login_terms_suffix)
        val privacyUrl = "https://progresseye-49244.web.app"

        val annotated = buildAnnotatedString {
            if (prefix.isNotEmpty()) withStyle(SpanStyle(color = Slate500)) { append(prefix) }
            pushStringAnnotation(tag = "TOS", annotation = privacyUrl)
            withStyle(SpanStyle(color = Primary, textDecoration = TextDecoration.Underline)) {
                append(tosLink)
            }
            pop()
            withStyle(SpanStyle(color = Slate500)) { append(mid) }
            pushStringAnnotation(tag = "PP", annotation = privacyUrl)
            withStyle(SpanStyle(color = Primary, textDecoration = TextDecoration.Underline)) {
                append(ppLink)
            }
            pop()
            if (suffix.isNotEmpty()) withStyle(SpanStyle(color = Slate500)) { append(suffix) }
        }

        ClickableText(
            text = annotated,
            style = MaterialTheme.typography.bodySmall,
            onClick = { offset ->
                annotated.getStringAnnotations("TOS", offset, offset)
                    .firstOrNull()?.let { uriHandler.openUri(it.item) }
                annotated.getStringAnnotations("PP", offset, offset)
                    .firstOrNull()?.let { uriHandler.openUri(it.item) }
            },
        )
    }
}

// ═════════════════════════════════════════════════════════
// Preview
// ═════════════════════════════════════════════════════════

@Preview(showBackground = true, showSystemUi = true)
@Composable
private fun LoginScreenPreview() {
    ProgressEyeTheme {
        LoginScreen()
    }
}
