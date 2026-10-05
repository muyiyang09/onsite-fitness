package com.onsitefitness.context;

public class BaseContext {

    public static ThreadLocal<Long> threadLocal = new ThreadLocal<>();

    /** 当前登录员工/用户的角色（§6.27 RBAC），如 admin / dev / null */
    private static final ThreadLocal<String> roleThreadLocal = new ThreadLocal<>();

    public static void setCurrentId(Long id) {
        threadLocal.set(id);
    }

    public static Long getCurrentId() {
        return threadLocal.get();
    }

    public static void removeCurrentId() {
        threadLocal.remove();
    }

    public static void setCurrentRole(String role) {
        roleThreadLocal.set(role);
    }

    public static String getCurrentRole() {
        return roleThreadLocal.get();
    }

    public static void removeCurrentRole() {
        roleThreadLocal.remove();
    }

}
