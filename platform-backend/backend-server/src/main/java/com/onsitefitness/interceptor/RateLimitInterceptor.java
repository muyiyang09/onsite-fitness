package com.onsitefitness.interceptor;

import com.onsitefitness.config.RateLimitConfig;
import com.onsitefitness.context.BaseContext;
import com.onsitefitness.properties.JwtProperties;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.HandlerInterceptor;

import java.util.concurrent.TimeUnit;

@Component
@Slf4j
public class RateLimitInterceptor implements HandlerInterceptor {

    @Autowired
    private StringRedisTemplate stringRedisTemplate;

    @Autowired
    private JwtProperties jwtProperties;

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) throws Exception {
        String requestURI = request.getRequestURI();
        String clientIp = getClientIp(request);

        // 1. 登录接口更严格的限流
        if (requestURI.contains("/login")) {
            String loginKey = "ratelimit:login:" + clientIp;
            if (!checkRateLimit(loginKey, RateLimitConfig.LOGIN_MAX_REQUESTS,
                                RateLimitConfig.LOGIN_WINDOW_SECONDS)) {
                log.warn("登录限流触发，IP: {}", clientIp);
                response.setStatus(429);
                response.setHeader("Retry-After", String.valueOf(RateLimitConfig.LOGIN_WINDOW_SECONDS));
                return false;
            }
        }

        // 2. 全局 IP 限流
        String ipKey = "ratelimit:ip:" + clientIp;
        if (!checkRateLimit(ipKey, RateLimitConfig.GLOBAL_MAX_REQUESTS,
                            RateLimitConfig.GLOBAL_WINDOW_SECONDS)) {
            log.warn("全局IP限流触发，IP: {}", clientIp);
            response.setStatus(429);
            response.setHeader("Retry-After", String.valueOf(RateLimitConfig.GLOBAL_WINDOW_SECONDS));
            return false;
        }

        // 3. 用户级限流（如果已登录）
        Long userId = BaseContext.getCurrentId();
        if (userId != null) {
            String userKey = "ratelimit:user:" + userId;
            if (!checkRateLimit(userKey, RateLimitConfig.USER_MAX_REQUESTS,
                                RateLimitConfig.USER_WINDOW_SECONDS)) {
                log.warn("用户限流触发，userId: {}", userId);
                response.setStatus(429);
                response.setHeader("Retry-After", String.valueOf(RateLimitConfig.USER_WINDOW_SECONDS));
                return false;
            }
        }

        return true;
    }

    // 基于 Redis 计数器的简单限流
    private boolean checkRateLimit(String key, int maxRequests, int windowSeconds) {
        try {
            String countStr = stringRedisTemplate.opsForValue().get(key);
            int count = 0;
            if (countStr != null) {
                count = Integer.parseInt(countStr);
            }

            if (count >= maxRequests) {
                return false;
            }

            // 原子递增
            Long newCount = stringRedisTemplate.opsForValue().increment(key);
            if (newCount != null && newCount == 1) {
                // 第一次设置过期时间
                stringRedisTemplate.expire(key, windowSeconds, TimeUnit.SECONDS);
            }

            return true;
        } catch (Exception e) {
            log.error("限流检查异常，放行请求", e);
            return true; // Redis 异常时放行，不阻塞业务
        }
    }

    // 获取客户端真实 IP
    private String getClientIp(HttpServletRequest request) {
        String ip = request.getHeader("X-Forwarded-For");
        if (ip == null || ip.isEmpty() || "unknown".equalsIgnoreCase(ip)) {
            ip = request.getHeader("X-Real-IP");
        }
        if (ip == null || ip.isEmpty() || "unknown".equalsIgnoreCase(ip)) {
            ip = request.getRemoteAddr();
        }
        // 处理多个代理的情况，取第一个 IP
        if (ip != null && ip.contains(",")) {
            ip = ip.split(",")[0].trim();
        }
        return ip;
    }
}
