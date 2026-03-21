package com.chg.progeresseye

import com.chg.progeresseye.util.isPro
import com.chg.progeresseye.util.toNormalizedPlan
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class PlanExtTest {

    // ── isPro ──────────────────────────────────────────

    @Test
    fun `isPro returns true for pro`() {
        assertTrue("pro".isPro())
    }

    @Test
    fun `isPro returns false for free`() {
        assertFalse("free".isPro())
    }

    @Test
    fun `isPro returns false for empty string`() {
        assertFalse("".isPro())
    }

    @Test
    fun `isPro returns false for null`() {
        val plan: String? = null
        assertFalse(plan.isPro())
    }

    @Test
    fun `isPro is case sensitive`() {
        assertFalse("Pro".isPro())
        assertFalse("PRO".isPro())
    }

    // ── toNormalizedPlan ───────────────────────────────

    @Test
    fun `toNormalizedPlan returns pro for pro`() {
        assertEquals("pro", "pro".toNormalizedPlan())
    }

    @Test
    fun `toNormalizedPlan returns free for free`() {
        assertEquals("free", "free".toNormalizedPlan())
    }

    @Test
    fun `toNormalizedPlan returns free for empty string`() {
        assertEquals("free", "".toNormalizedPlan())
    }

    @Test
    fun `toNormalizedPlan returns free for null`() {
        val plan: String? = null
        assertEquals("free", plan.toNormalizedPlan())
    }

    @Test
    fun `toNormalizedPlan returns free for unknown plan`() {
        assertEquals("free", "enterprise".toNormalizedPlan())
        assertEquals("free", "premium".toNormalizedPlan())
    }

    @Test
    fun `toNormalizedPlan is case sensitive`() {
        assertEquals("free", "Pro".toNormalizedPlan())
        assertEquals("free", "PRO".toNormalizedPlan())
    }
}
