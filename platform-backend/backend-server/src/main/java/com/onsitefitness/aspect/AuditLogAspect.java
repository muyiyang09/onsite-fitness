package com.onsitefitness.aspect;

import com.onsitefitness.annotation.AuditLog;
import com.onsitefitness.context.BaseContext;
import com.onsitefitness.entity.SysAuditLog;
import com.onsitefitness.mapper.SysAuditLogMapper;
import lombok.extern.slf4j.Slf4j;
import org.aspectj.lang.ProceedingJoinPoint;
import org.aspectj.lang.annotation.Around;
import org.aspectj.lang.annotation.Aspect;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.lang.reflect.Method;
import java.time.LocalDateTime;

/**
 * 业务审计切面（§6.28）：拦截 {@link com.onsitefitness.annotation.AuditLog} 标注的方法，
 * 旁路写入 sys_audit_log（成功/失败都记录；审计写失败只告警、不影响主流程）。
 */
@Slf4j
@Aspect
@Component
public class AuditLogAspect {

    @Autowired
    private SysAuditLogMapper sysAuditLogMapper;

    @Around("@annotation(auditLog)")
    public Object audit(ProceedingJoinPoint pjp, AuditLog auditLog) throws Throwable {
        Long userId = BaseContext.getCurrentId();
        Long bizId = resolveBizId(pjp.getArgs());
        try {
            Object result = pjp.proceed();
            // 主键在返回值里的动作（如下单 submit），事后兜底取一次
            if (bizId == null && result != null) {
                bizId = resolveIdFrom(result);
            }
            writeAudit(userId, auditLog.type(), bizId, auditLog.detail(), null);
            return result;
        } catch (Throwable t) {
            writeAudit(userId, auditLog.type(), bizId, auditLog.detail(), t.getMessage());
            throw t;
        }
    }

    /** 从入参里解析业务主键：优先 Long 类型参数，其次常见 getId/getCoachId/getPoolId/getOrderId。 */
    private Long resolveBizId(Object[] args) {
        if (args != null) {
            for (Object arg : args) {
                if (arg instanceof Long) {
                    return (Long) arg;
                }
                Long id = resolveIdFrom(arg);
                if (id != null) {
                    return id;
                }
            }
        }
        return null;
    }

    private Long resolveIdFrom(Object obj) {
        if (obj == null) {
            return null;
        }
        for (String getter : new String[]{"getId", "getCoachId", "getPoolId", "getOrderId"}) {
            try {
                Method m = obj.getClass().getMethod(getter);
                Object v = m.invoke(obj);
                if (v instanceof Long) {
                    return (Long) v;
                }
            } catch (Exception ignored) {
                // 无此 getter，继续尝试下一个
            }
        }
        return null;
    }

    private void writeAudit(Long userId, String type, Long bizId, String detail, String extra) {
        try {
            SysAuditLog auditLog = SysAuditLog.builder()
                    .userId(userId)
                    .type(type)
                    .bizId(bizId)
                    .detail(detail)
                    .jsonExtra(extra)
                    .createdAt(LocalDateTime.now())
                    .build();
            sysAuditLogMapper.insert(auditLog);
        } catch (Exception e) {
            log.warn("业务审计写入失败（不影响主流程）：type={}, err={}", type, e.getMessage());
        }
    }
}
