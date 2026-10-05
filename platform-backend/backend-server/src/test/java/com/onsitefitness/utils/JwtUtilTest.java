package com.onsitefitness.utils;

import io.jsonwebtoken.Claims;
import org.junit.jupiter.api.Test;

import java.util.HashMap;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;

/**
 * JwtUtil 单元测试（纯逻辑，无 DB/Redis 依赖）。
 * 覆盖：签发-解析 round-trip、短密钥防御性补零、错误密钥解析失败、jti 自动生成。
 */
class JwtUtilTest {

    /** 32 字节密钥（HS256 最低长度） */
    private static final String SECRET = "0123456789abcdef0123456789abcdef";

    @Test
    void createAndParseRoundTrip() {
        Map<String, Object> claims = new HashMap<>();
        claims.put("empId", 1L);

        JwtUtil.JwtTokenResult result = JwtUtil.createJWT(SECRET, 3_600_000L, claims);
        String token = result.getToken();
        Claims parsed = JwtUtil.parseJWT(SECRET, token);

        assertEquals(1L, ((Number) parsed.get("empId")).longValue());
        assertNotNull(result.getJti());
        assertEquals(result.getJti(), parsed.get("jti"));
    }

    @Test
    void shortSecretIsPaddedDefensively() {
        Map<String, Object> claims = new HashMap<>();
        claims.put("uid", 42L);

        JwtUtil.JwtTokenResult result = JwtUtil.createJWT("short", 3_600_000L, claims);
        String token = result.getToken();
        Claims parsed = JwtUtil.parseJWT("short", token);

        assertEquals(42L, ((Number) parsed.get("uid")).longValue());
    }

    @Test
    void parseWithWrongSecretThrows() {
        JwtUtil.JwtTokenResult result = JwtUtil.createJWT(SECRET, 3_600_000L, Map.of("k", "v"));
        String token = result.getToken();

        assertThrows(Exception.class,
                () -> JwtUtil.parseJWT("11111111111111111111111111111111", token));
    }
}
