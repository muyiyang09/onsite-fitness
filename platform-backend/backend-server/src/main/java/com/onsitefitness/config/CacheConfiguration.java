package com.onsitefitness.config;

import com.fasterxml.jackson.annotation.JsonAutoDetect;
import com.fasterxml.jackson.annotation.PropertyAccessor;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.jsontype.impl.LaissezFaireSubTypeValidator;
import com.onsitefitness.json.JacksonObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.cache.Cache;
import org.springframework.cache.CacheManager;
import org.springframework.cache.annotation.CachingConfigurer;
import org.springframework.cache.interceptor.CacheErrorHandler;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.redis.cache.RedisCacheConfiguration;
import org.springframework.data.redis.cache.RedisCacheManager;
import org.springframework.data.redis.connection.RedisConnectionFactory;
import org.springframework.data.redis.serializer.GenericJackson2JsonRedisSerializer;
import org.springframework.data.redis.serializer.RedisSerializationContext;
import org.springframework.data.redis.serializer.StringRedisSerializer;

import java.time.Duration;

/**
 * 缓存三防配置（§6.23）：
 *  - 击穿：@Cacheable(sync=true) 单线程回源（见 CoursePackageController）；
 *  - 穿透：coursePackageCache 允许缓存 null 值（NullValue 哨兵），空结果 5min 内不反复打 DB；
 *  - 降级：CacheErrorHandler 吞掉 Redis 异常，缓存挂了直接走 DB，不阻断主链路。
 */
@Configuration
@Slf4j
public class CacheConfiguration implements CachingConfigurer {

    private final RedisConnectionFactory connectionFactory;

    public CacheConfiguration(RedisConnectionFactory connectionFactory) {
        this.connectionFactory = connectionFactory;
    }

    /**
     * Redis 缓存管理器：值用 JSON（含 @class 类型元信息），保证 Result&lt;List&lt;CoursePackage&gt;&gt;
     * 这类泛型容器反序列化回正确类型；与 RedisConfiguration 的 redisTemplate 序列化保持一致。
     */
    @Override
    public CacheManager cacheManager() {
        ObjectMapper om = new JacksonObjectMapper();
        om.setVisibility(PropertyAccessor.ALL, JsonAutoDetect.Visibility.ANY);
        om.activateDefaultTyping(LaissezFaireSubTypeValidator.instance, ObjectMapper.DefaultTyping.NON_FINAL);
        GenericJackson2JsonRedisSerializer valueSerializer = new GenericJackson2JsonRedisSerializer(om);

        RedisCacheConfiguration defaults = RedisCacheConfiguration.defaultCacheConfig()
                .entryTtl(Duration.ofMinutes(30))
                .serializeKeysWith(RedisSerializationContext.SerializationPair.fromSerializer(new StringRedisSerializer()))
                .serializeValuesWith(RedisSerializationContext.SerializationPair.fromSerializer(valueSerializer));

        // coursePackageCache：TTL 5min；默认配置已启用 null 值缓存（NullValue 哨兵），
        // 故此处不调用 disableCachingNullValues()，以达成穿透防护。
        RedisCacheConfiguration coursePackage = defaults.entryTtl(Duration.ofMinutes(5));

        return RedisCacheManager.builder(connectionFactory)
                .cacheDefaults(defaults)
                .withCacheConfiguration("coursePackageCache", coursePackage)
                .build();
    }

    @Override
    public CacheErrorHandler errorHandler() {
        return new CacheErrorHandler() {
            @Override
            public void handleCacheGetError(RuntimeException exception, Cache cache, Object key) {
                log.warn("缓存读异常，降级直查 DB：cache={}, key={}, err={}", cache.getName(), key, exception.getMessage());
            }

            @Override
            public void handleCachePutError(RuntimeException exception, Cache cache, Object key, Object value) {
                log.warn("缓存写异常，忽略：cache={}, key={}, err={}", cache.getName(), key, exception.getMessage());
            }

            @Override
            public void handleCacheEvictError(RuntimeException exception, Cache cache, Object key) {
                log.warn("缓存清除异常，忽略：cache={}, key={}, err={}", cache.getName(), key, exception.getMessage());
            }

            @Override
            public void handleCacheClearError(RuntimeException exception, Cache cache) {
                log.warn("缓存清空异常，忽略：cache={}, err={}", cache.getName(), exception.getMessage());
            }
        };
    }
}
