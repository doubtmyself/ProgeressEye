package com.chg.progeresseye.ui.component

import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.foundation.layout.height
import androidx.compose.ui.unit.dp

import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.compose.LifecycleResumeEffect
import com.chg.progeresseye.BuildConfig
import com.google.android.gms.ads.AdRequest
import com.google.android.gms.ads.AdSize
import com.google.android.gms.ads.AdView

@Composable
fun BannerAd(modifier: Modifier = Modifier) {
    val context = LocalContext.current

    val adView = remember {
        AdView(context).apply {
            adUnitId = if (BuildConfig.DEBUG) BANNER_AD_UNIT_ID_TEST else BANNER_AD_UNIT_ID
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
        modifier = modifier.height(50.dp),
    )
}

private const val BANNER_AD_UNIT_ID = "ca-app-pub-6572076936506117/1388628199"
private const val BANNER_AD_UNIT_ID_TEST = "ca-app-pub-3940256099942544/9214589741"
