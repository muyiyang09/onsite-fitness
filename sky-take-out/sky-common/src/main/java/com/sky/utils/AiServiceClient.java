package com.sky.utils;

import com.alibaba.fastjson2.JSON;
import lombok.extern.slf4j.Slf4j;
import org.apache.http.client.methods.CloseableHttpResponse;
import org.apache.http.client.methods.HttpPost;
import org.apache.http.entity.StringEntity;
import org.apache.http.impl.client.CloseableHttpClient;
import org.apache.http.impl.client.HttpClients;
import org.apache.http.util.EntityUtils;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Map;

/**
 * AI 微服务（ai-service）代理客户端 —— 跨服务机器间互信的唯一出口。
 *
 * <p>职责（§6.13 / §6.15）：
 * <ul>
 *   <li>统一携带 {@code X-Service-Token} 头，与 ai-service 的 ServiceAuthMiddleware 校验握手；</li>
 *   <li>屏蔽 ai-service 地址，后端业务代码只调本类方法，不直接暴露 {@code /v1/ai} 地址。</li>
 * </ul>
 *
 * <p><b>升级路径（重要）</b>：后续所有 C 端 AI 入口都应由后端 {@code /user/ai/**} 先验用户 JWT
 * 再转发到本客户端，<b>绝不</b>把 {@code /v1/ai} 直接反代到网关 / nginx 公网域名。
 * 当前后端尚无调用点，本类为「预备役」骨架，供 controller 后续接入。
 */
@Slf4j
@Component
public class AiServiceClient {

    /** ai-service 基础地址，如 http://ai-service:18000（容器间）或 http://127.0.0.1:18000（本机）。 */
    @Value("${sky.ai.base-url:http://ai-service:18000}")
    private String baseUrl;

    /** 与 ai-service SERVICE_AUTH_TOKEN 一致的共享密钥。 */
    @Value("${sky.ai.service-token:}")
    private String serviceToken;

    /**
     * 教练推荐（自然语言 → Top N 教练）。当前为预留骨架，controller 接入时调用。
     *
     * @param query 用户自然语言 query
     * @return ai-service 返回的 JSON 字符串（后续可按需反序列化为 VO）
     */
    public String recommendCoach(String query) {
        return postJson("/v1/ai/recommend-coach", Map.of(
                "user_query", query,
                "top_n", 3
        ));
    }

    /**
     * 评价摘要（教练最近 N 条评价 → 优缺点 + 标签 + 情感计数）。
     * <p>对齐 ai-service {@code /v1/ai/review-summary} 契约：
     * <pre>{@code
     *   Request:  { coach_id: int, limit: int(1~200) }
     *   Response: { coach_id, summary, positive_tags[], negative_tags[], sentiment{pos/neg/neu}, used_mock }
     * }</pre>
     *
     * @param coachId 教练 ID
     * @param limit   取最近评价条数（1~200，默认 30）
     * @return ai-service 返回的 ReviewSummaryResult JSON 字符串；异常时 ai-service 层已有日志，调用方自行 try/catch
     */
    public String reviewSummary(int coachId, int limit) {
        int safeLimit = Math.min(Math.max(limit, 1), 200);
        // HashMap 支持 null 值，避免 Map.of 对 int 自动装箱的空安全问题
        Map<String, Object> body = new HashMap<>();
        body.put("coach_id", coachId);
        body.put("limit", safeLimit);
        return postJson("/v1/ai/review-summary", body);
    }

    /**
     * 内部统一 POST JSON + X-Service-Token 头。
     */
    private String postJson(String path, Map<String, Object> body) {
        try (CloseableHttpClient httpClient = HttpClients.createDefault()) {
            HttpPost httpPost = new HttpPost(baseUrl + path);
            httpPost.setHeader("Content-Type", "application/json");
            if (serviceToken != null && !serviceToken.isBlank()) {
                httpPost.setHeader("X-Service-Token", serviceToken);
            }
            httpPost.setEntity(new StringEntity(JSON.toJSONString(body), StandardCharsets.UTF_8));

            try (CloseableHttpResponse response = httpClient.execute(httpPost)) {
                String result = EntityUtils.toString(response.getEntity(), StandardCharsets.UTF_8);
                if (response.getStatusLine().getStatusCode() != 200) {
                    log.warn("ai-service 调用失败 status={} body={}", response.getStatusLine().getStatusCode(), result);
                }
                return result;
            }
        } catch (Exception e) {
            log.error("ai-service 调用异常 path={}", path, e);
            throw new RuntimeException("AI 服务调用失败", e);
        }
    }
}
