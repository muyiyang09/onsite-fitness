package com.onsitefitness.utils;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.Date;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

public class JwtUtil {

    public static class JwtTokenResult {
        private final String token;
        private final String jti;

        public JwtTokenResult(String token, String jti) {
            this.token = token;
            this.jti = jti;
        }

        public String getToken() {
            return token;
        }

        public String getJti() {
            return jti;
        }
    }

    /**
     * 生成jwt
     * 使用 HMAC-SHA 算法签名（HS256/HS384/HS512，由密钥长度决定）
     * 自动生成 jti (UUID) 并写入 claims，返回包含 token 和 jti 的结果对象
     *
     * @param secretKey jwt秘钥
     * @param ttlMillis jwt过期时间(毫秒)
     * @param claims    设置的信息
     * @return JwtTokenResult 包含 token 和 jti
     */
    public static JwtTokenResult createJWT(String secretKey, long ttlMillis, Map<String, Object> claims) {
        String jti = UUID.randomUUID().toString();

        // 不直接改写调用方入参（可能是 Map.of 等不可变 Map），复制后再写入 jti
        Map<String, Object> allClaims = new HashMap<>(claims);
        allClaims.put("jti", jti);

        long expMillis = System.currentTimeMillis() + ttlMillis;
        Date exp = new Date(expMillis);

        String token = Jwts.builder()
                .claims(allClaims)
                .signWith(getSigningKey(secretKey))
                .expiration(exp)
                .compact();

        return new JwtTokenResult(token, jti);
    }

    /**
     * Token解密
     *
     * @param secretKey jwt秘钥 此秘钥一定要保留好在服务端, 不能暴露出去, 否则sign就可以被伪造, 如果对接多个客户端建议改造成多个
     * @param token     加密后的token
     * @return
     */
    public static Claims parseJWT(String secretKey, String token) {
        return Jwts.parser()
                // 校验签名使用的密钥
                .verifyWith(getSigningKey(secretKey))
                .build()
                // 解析并校验 token
                .parseSignedClaims(token)
                .getPayload();
    }

    /**
     * 由配置的字符串密钥派生出 HMAC 密钥。
     * jjwt 0.12 起要求 HMAC 密钥长度 >= 256 bit(32 字节)；当前配置密钥已为
     * 64 位随机串，无需处理。这里对 <32 字节的短密钥补零到 32 字节，仅作防御性兜底。
     */
    private static SecretKey getSigningKey(String secretKey) {
        byte[] bytes = secretKey.getBytes(StandardCharsets.UTF_8);
        if (bytes.length < 32) {
            bytes = Arrays.copyOf(bytes, 32);
        }
        return Keys.hmacShaKeyFor(bytes);
    }
}
