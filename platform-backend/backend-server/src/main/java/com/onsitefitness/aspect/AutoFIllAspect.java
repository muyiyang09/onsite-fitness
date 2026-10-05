package com.onsitefitness.aspect;

import com.onsitefitness.annotation.AutoFill;
import com.onsitefitness.constant.AutoFillConstant;
import com.onsitefitness.context.BaseContext;
import com.onsitefitness.enumeration.OperationType;
import lombok.extern.slf4j.Slf4j;
import org.aspectj.lang.JoinPoint;
import org.aspectj.lang.annotation.Aspect;
import org.aspectj.lang.annotation.Before;
import org.aspectj.lang.annotation.Pointcut;
import org.aspectj.lang.reflect.MethodSignature;
import org.springframework.stereotype.Component;

import java.lang.reflect.Method;
import java.time.LocalDateTime;

import static org.apache.ibatis.ognl.OgnlRuntime.setFieldValue;

/**
 * 自定义前面，实现公共字段自动填充处理逻辑
 */
@Slf4j
@Component
@Aspect
public class AutoFIllAspect {
    /**
     * 切入点,insert和update方法
     */
    @Pointcut("execution(* com.onsitefitness.mapper.*.*(..)) && @annotation(com.onsitefitness.annotation.AutoFill)")
    public void autoFillPointCut() {
    }

    /**
     * 前置通知，实现公共字段自动填充
     * @param joinPoint
     */
    @Before("autoFillPointCut()")
    public void autoFill(JoinPoint joinPoint) throws NoSuchMethodException {
        log.info("开始进行公共字段自动填充");
        //1.获取被注解的方法参数
        MethodSignature signature = (MethodSignature) joinPoint.getSignature();
        AutoFill autoFill = signature.getMethod().getAnnotation(AutoFill.class);
        OperationType operationType = autoFill.value();
        //2.获取被注解的方法参数
        Object[] args = joinPoint.getArgs();
        if (args == null || args.length == 0) {
            return;
        }
        //3.遍历参数，判断是否有需要自动填充的字段
        Object entity = args[0];
        // 准备赋值的参数
        LocalDateTime now = LocalDateTime.now();
        Long currentUserId = BaseContext.getCurrentId();
        //4.遍历参数，判断是否有需要自动填充的字段
        if (operationType == OperationType.INSERT){
            try { // 反射调用方法
                Method setCreateTime= entity.getClass().getDeclaredMethod(AutoFillConstant.SET_CREATE_TIME, LocalDateTime.class);
                Method setCreateUser = entity.getClass().getDeclaredMethod(AutoFillConstant.SET_CREATE_USER, Long.class);
                Method setUpdateTime = entity.getClass().getDeclaredMethod(AutoFillConstant.SET_UPDATE_TIME, LocalDateTime.class);
                Method setUpdateUser = entity.getClass().getDeclaredMethod(AutoFillConstant.SET_UPDATE_USER, Long.class);
                setCreateTime.invoke(entity, now);
                setCreateUser.invoke(entity, currentUserId);
                setUpdateTime.invoke(entity, now);
                setUpdateUser.invoke(entity, currentUserId);
            } catch (Exception e) {
                throw new RuntimeException(e);
            }
        }else if (operationType == OperationType.UPDATE){
            try {
                Method setUpdateTime = entity.getClass().getDeclaredMethod(AutoFillConstant.SET_UPDATE_TIME, LocalDateTime.class);
                Method setUpdateUser = entity.getClass().getDeclaredMethod(AutoFillConstant.SET_UPDATE_USER, Long.class);
                setUpdateTime.invoke(entity, now);
                setUpdateUser.invoke(entity, currentUserId);
            }catch (Exception e){
                throw new RuntimeException(e);
            }
        }
    }
}

