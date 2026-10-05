package com.onsitefitness.interceptor;

import com.onsitefitness.constant.JwtClaimsConstant;
import com.onsitefitness.context.BaseContext;
import com.onsitefitness.properties.JwtProperties;
import com.onsitefitness.service.TokenBlacklistService;
import com.onsitefitness.utils.JwtUtil;
import io.jsonwebtoken.Claims;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;
import org.springframework.web.method.HandlerMethod;
import org.springframework.web.servlet.HandlerInterceptor;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

/**
 * jwt令牌校验的拦截器
 */
@Component
@Slf4j
public class JwtTokenUserInterceptor implements HandlerInterceptor {

    @Autowired
    private JwtProperties jwtProperties;

    @Autowired
    private TokenBlacklistService tokenBlacklistService;

    /**
     * 校验jwt
     *
     * @param request
     * @param response
     * @param handler
     * @return
     * @throws Exception
     */
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) throws Exception {
        //判断当前拦截到的是Controller的方法还是其他资源
        if (!(handler instanceof HandlerMethod)) {
            //当前拦截到的不是动态方法，直接放行
            return true;
        }

        //1、从请求头中获取令牌
        String token = request.getHeader(jwtProperties.getUserTokenName());

        //2、校验令牌
        try {
            log.info("jwt校验:{}", token == null ? null : token.substring(0, Math.min(6, token.length())) + "***");
            Claims claims = JwtUtil.parseJWT(jwtProperties.getUserSecretKey(), token);
            Long userId = Long.valueOf(claims.get(JwtClaimsConstant.USER_ID).toString());
            log.info("当前用户id：{}", userId);

            String jti = claims.get(JwtClaimsConstant.JTI) != null
                    ? claims.get(JwtClaimsConstant.JTI).toString()
                    : null;
            if (jti != null && tokenBlacklistService.isBlacklisted(jti)) {
                log.warn("token已被吊销, userId={}, jti={}", userId, jti);
                response.setStatus(401);
                return false;
            }

            if (jti != null) {
                tokenBlacklistService.registerUserToken(
                        String.valueOf(userId), jti, jwtProperties.getUserTtl());
            }

            BaseContext.setCurrentId(userId);
            return true;
        } catch (Exception ex) {
            response.setStatus(401);
            return false;
        }
    }
}
