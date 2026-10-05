package com.onsitefitness.annotation;

import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

/**
 * 业务审计标记（§6.28）：标注敏感业务方法，由 AuditLogAspect 切面写入 sys_audit_log。
 */
@Target(ElementType.METHOD)
@Retention(RetentionPolicy.RUNTIME)
public @interface AuditLog {

    /** 动作类型，如 order.submit / order.seize / order.refund / order.handle / coachAudit */
    String type();

    /** 操作描述 */
    String detail() default "";
}
