package com.chg.progeresseye.data.util

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

class CommandBuilderTest {

    @Test
    fun `build contains targetDeviceId`() {
        val result = CommandBuilder.build("device-123")
        assertEquals("device-123", result["targetDeviceId"])
    }

    @Test
    fun `build contains ts as Long`() {
        val before = System.currentTimeMillis() / 1000 - 1
        val result = CommandBuilder.build("device-123")
        val after = System.currentTimeMillis() / 1000 + 1
        val ts = result["ts"] as Long
        assertTrue(ts in before..after)
    }

    @Test
    fun `build contains non-blank cmdId`() {
        val result = CommandBuilder.build("device-123")
        val cmdId = result["cmdId"] as String
        assertTrue(cmdId.isNotBlank())
    }

    @Test
    fun `build generates unique cmdId each call`() {
        val first = CommandBuilder.build("device-123")["cmdId"] as String
        val second = CommandBuilder.build("device-123")["cmdId"] as String
        assertTrue(first != second)
    }

    @Test
    fun `build result has exactly three keys`() {
        val result = CommandBuilder.build("device-123")
        assertEquals(3, result.size)
    }

    @Test
    fun `build works with different device ids`() {
        val result1 = CommandBuilder.build("device-aaa")
        val result2 = CommandBuilder.build("device-bbb")
        assertEquals("device-aaa", result1["targetDeviceId"])
        assertEquals("device-bbb", result2["targetDeviceId"])
    }
}
