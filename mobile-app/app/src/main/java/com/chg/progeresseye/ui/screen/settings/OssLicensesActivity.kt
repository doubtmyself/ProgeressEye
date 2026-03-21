package com.chg.progeresseye.ui.screen.settings

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.chg.progeresseye.R
import com.chg.progeresseye.ui.theme.BackgroundDark
import com.chg.progeresseye.ui.theme.OnSurfaceDark
import com.chg.progeresseye.ui.theme.OnSurfaceVariantDark
import com.chg.progeresseye.ui.theme.OutlineVariantDark
import com.chg.progeresseye.ui.theme.ProgressEyeTheme
import com.chg.progeresseye.ui.theme.SurfaceContainerDark

class OssLicensesActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            ProgressEyeTheme {
                OssLicensesContent(onBack = ::finish)
            }
        }
    }
}

private data class OssLibrary(
    val name: String,
    val license: String,
    val url: String,
)

private val ossLibraries = listOf(
    OssLibrary("Kotlin", "Apache-2.0", "https://github.com/JetBrains/kotlin/blob/master/license/LICENSE.txt"),
    OssLibrary("Kotlinx Coroutines", "Apache-2.0", "https://github.com/Kotlin/kotlinx.coroutines/blob/master/LICENSE.txt"),
    OssLibrary("AndroidX", "Apache-2.0", "https://android.googlesource.com/platform/frameworks/support/+/androidx-main/LICENSE.txt"),
    OssLibrary("Jetpack Compose", "Apache-2.0", "https://android.googlesource.com/platform/frameworks/support/+/androidx-main/LICENSE.txt"),
    OssLibrary("Firebase Android SDK", "Apache-2.0", "https://github.com/firebase/firebase-android-sdk/blob/master/LICENSE"),
    OssLibrary("Hilt (Dagger)", "Apache-2.0", "https://github.com/google/dagger/blob/master/LICENSE.txt"),
    OssLibrary("Coil", "Apache-2.0", "https://github.com/coil-kt/coil/blob/main/LICENSE.txt"),
    OssLibrary("OkHttp", "Apache-2.0", "https://github.com/square/okhttp/blob/master/LICENSE.txt"),
    OssLibrary("Timber", "Apache-2.0", "https://github.com/JakeWharton/timber/blob/trunk/LICENSE.txt"),
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun OssLicensesContent(onBack: () -> Unit) {
    val uriHandler = LocalUriHandler.current

    Scaffold(
        containerColor = BackgroundDark,
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        text = stringResource(R.string.settings_oss_licenses),
                        style = MaterialTheme.typography.titleLarge,
                        color = OnSurfaceDark,
                    )
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(
                            imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                            contentDescription = stringResource(R.string.cd_close),
                            tint = OnSurfaceDark,
                        )
                    }
                },
            )
        },
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
            contentPadding = PaddingValues(horizontal = 16.dp, vertical = 16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            item {
                Text(
                    text = stringResource(R.string.settings_oss_licenses_description),
                    style = MaterialTheme.typography.bodySmall,
                    color = OnSurfaceVariantDark,
                )
            }

            items(ossLibraries) { item ->
                Card(
                    colors = CardDefaults.cardColors(containerColor = SurfaceContainerDark),
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable { uriHandler.openUri(item.url) },
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 14.dp, vertical = 12.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Column(modifier = Modifier.weight(1f)) {
                            Text(
                                text = item.name,
                                style = MaterialTheme.typography.bodyLarge,
                                color = OnSurfaceDark,
                                fontWeight = FontWeight.SemiBold,
                            )
                            Spacer(Modifier.height(2.dp))
                            Text(
                                text = item.license,
                                style = MaterialTheme.typography.bodySmall,
                                color = OnSurfaceVariantDark,
                            )
                        }
                        Icon(
                            imageVector = Icons.AutoMirrored.Filled.KeyboardArrowRight,
                            contentDescription = null,
                            tint = OnSurfaceVariantDark,
                            modifier = Modifier.size(20.dp),
                        )
                    }
                    HorizontalDivider(color = OutlineVariantDark)
                }
            }
        }
    }
}
