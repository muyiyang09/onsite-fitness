package com.onsitefitness.annotation;

import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

/**
 * 敏感管理操作标记（§6.27 RBAC）：仅 admin 角色可执行。
 * 由 AdminRoleAspect 切面在方法执行前校验 BaseContext 中的角色。
 */
@Target(ElementType.METHOD)
@Retention(RetentionPolicy.RUNTIME)
public @interface AdminOnly {
}
