package com.onsitefitness.aspect;

import com.onsitefitness.context.BaseContext;
import com.onsitefitness.exception.BaseException;
import lombok.extern.slf4j.Slf4j;
import org.aspectj.lang.annotation.Aspect;
import org.aspectj.lang.annotation.Before;
import org.aspectj.lang.annotation.Pointcut;
import org.springframework.stereotype.Component;

/**
 * RBAC 权限切面（§6.27）：拦截 {@link com.onsitefitness.annotation.AdminOnly} 标注的方法，
 * 校验当前登录员工角色是否为 admin，否则拒绝执行（抛业务异常 → 全局异常处理器统一返回）。
 */
@Slf4j
@Component
@Aspect
public class AdminRoleAspect {

    @Pointcut("@annotation(com.onsitefitness.annotation.AdminOnly)")
    public void adminOnlyPointcut() {
    }

    @Before("adminOnlyPointcut()")
    public void checkAdminRole() {
        String role = BaseContext.getCurrentRole();
        if (!"admin".equals(role)) {
            log.warn("越权访问敏感管理端点，当前角色={}, userId={}", role, BaseContext.getCurrentId());
            throw new BaseException("无权限操作，仅管理员可执行");
        }
    }
}
