package com.onsitefitness.properties;

import jakarta.annotation.PostConstruct;
import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

@Component
@ConfigurationProperties(prefix = "onsite.jwt")
@Data
public class JwtProperties {

    /**
     * 管理端员工生成jwt令牌相关配置
     */
    private String adminSecretKey;
    private long adminTtl;
    private String adminTokenName;

    /**
     * 用户端微信用户生成jwt令牌相关配置
     */
    private String userSecretKey;
    private long userTtl;
    private String userTokenName;

    /**
     * 教练端生成jwt令牌相关配置
     */
    private String coachSecretKey;
    private long coachTtl;
    private String coachTokenName;

    /**
     * 启动即校验密钥长度（§6.14）：三个 key 必须 ≥32 字符，防 6 字节短密钥回归。
     * 缺失（空字符串）同样在此拦截，实现「缺失即启动失败」的快速失败。
     */
    @PostConstruct
    public void validate() {
        requireLength("admin-secret-key", adminSecretKey);
        requireLength("user-secret-key", userSecretKey);
        requireLength("coach-secret-key", coachSecretKey);
    }

    private void requireLength(String name, String key) {
        if (key == null || key.length() < 32) {
            throw new IllegalStateException(
                    "[onsite.jwt] " + name + " 长度不足 32 字符（当前 " +
                    (key == null ? 0 : key.length()) + "），请通过 ONSITE_JWT_* 环境变量注入强密钥");
        }
    }

}
