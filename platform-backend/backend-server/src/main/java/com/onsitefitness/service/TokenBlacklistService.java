package com.onsitefitness.service;

import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

import org.springframework.beans.factory.annotation.Autowired;
import java.util.Set;
import java.util.concurrent.TimeUnit;

@Service
public class TokenBlacklistService {

    @Autowired
    private StringRedisTemplate stringRedisTemplate;

    private static final String BLACKLIST_PREFIX = "token:blacklist:";
    private static final String USER_TOKENS_PREFIX = "user:tokens:";

    public void blacklist(String jti, long ttlMillis) {
        String key = BLACKLIST_PREFIX + jti;
        stringRedisTemplate.opsForValue().set(key, "1", ttlMillis, TimeUnit.MILLISECONDS);
    }

    public boolean isBlacklisted(String jti) {
        String key = BLACKLIST_PREFIX + jti;
        return Boolean.TRUE.equals(stringRedisTemplate.hasKey(key));
    }

    public void registerUserToken(String userId, String jti, long ttlMillis) {
        String key = USER_TOKENS_PREFIX + userId;
        stringRedisTemplate.opsForSet().add(key, jti);
        stringRedisTemplate.expire(key, ttlMillis, TimeUnit.MILLISECONDS);
    }

    public void invalidateAllUserTokens(String userId) {
        String key = USER_TOKENS_PREFIX + userId;
        Set<String> tokens = stringRedisTemplate.opsForSet().members(key);
        if (tokens != null) {
            for (String jti : tokens) {
                blacklist(jti, TimeUnit.HOURS.toMillis(1));
            }
        }
        stringRedisTemplate.delete(key);
    }
}