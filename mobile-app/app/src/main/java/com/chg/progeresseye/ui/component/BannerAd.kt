package com.chg.progeresseye.ui.component

import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier

import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.compose.LifecycleResumeEffect
import com.google.android.gms.ads.AdRequest
import com.google.android.gms.ads.AdSize
import com.google.android.gms.ads.AdView

@Composable
fun BannerAd(modifier: Modifier = Modifier) {
    val context = LocalContext.current

    val adView = remember {
        AdView(context).apply {
            adUnitId = BANNER_TEST_AD_UNIT_ID
        }
    }

    LaunchedEffect(adView) {
        adView.setAdSize(AdSize.BANNER)
        adView.loadAd(AdRequest.Builder().build())
    }

    LifecycleResumeEffect(adView) {
        adView.resume()
        onPauseOrDispose {
            adView.pause()
        }
    }

    DisposableEffect(adView) {
        onDispose {
            adView.destroy()
        }
    }

    AndroidView(
        factory = { adView },
        modifier = modifier,
    )
}

private const val BANNER_TEST_AD_UNIT_ID = "ca-app-pub-3940256099942544/9214589741"
