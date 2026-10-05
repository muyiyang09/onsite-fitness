package com.onsitefitness.config;

import org.springframework.context.annotation.Configuration;

@Configuration
public class RateLimitConfig {
    // 限流配置常量
    public static final int GLOBAL_WINDOW_SECONDS = 60;      // 全局窗口：60秒
    public static final int GLOBAL_MAX_REQUESTS = 300;        // 全局限制：300次/分钟（每IP）
    public static final int USER_WINDOW_SECONDS = 60;        // 用户窗口：60秒
    public static final int USER_MAX_REQUESTS = 100;         // 用户限制：100次/分钟（每用户）
    public static final int LOGIN_WINDOW_SECONDS = 300;      // 登录窗口：5分钟
    public static final int LOGIN_MAX_REQUESTS = 5;          // 登录限制：5次/5分钟
}
