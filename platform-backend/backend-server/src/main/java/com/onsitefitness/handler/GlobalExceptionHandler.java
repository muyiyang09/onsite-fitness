package com.onsitefitness.handler;

import com.onsitefitness.constant.MessageConstant;
import com.onsitefitness.exception.BaseException;
import com.onsitefitness.result.Result;
import lombok.extern.slf4j.Slf4j;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.sql.SQLIntegrityConstraintViolationException;
import java.util.Objects;
import java.util.stream.Collectors;

/**
 * 全局异常处理器，处理项目中抛出的业务异常
 */
@RestControllerAdvice
@Slf4j
public class GlobalExceptionHandler {

    /**
     * 捕获业务异常
     * @param ex
     * @return
     */
    @ExceptionHandler
    public Result exceptionHandler(BaseException ex){
        log.error("业务异常：{}", ex.getMessage(), ex);
        return Result.error(ex.getMessage());
    }

    /**
     * 捕获SQL异常
     * @param ex
     * @return
     */
    @ExceptionHandler
    public Result exceptionHandler(SQLIntegrityConstraintViolationException ex){
        log.error("SQL完整性约束异常", ex);
        String message = ex.getMessage();
        if(message != null && message.contains("Duplicate entry")){
            String[] split = message.split(" "); //// Duplicate entry 'admin' for key 'idx_username'
            String username = split[2];
            String msg = username  + MessageConstant.ALREADY_EXIST; // Duplicate entry 'admin' for key 'idx_username'
            return Result.error(msg);
        }else{
            return Result.error(MessageConstant.UNKNOWN_ERROR);
        }
    }

    /**
     * 兜底：未预期异常。记完整堆栈，向前端返回统一错误，不泄露内部栈/原始 SQL 细节。
     * @param ex
     * @return
     */
    @ExceptionHandler(Exception.class)
    public Result exceptionHandler(Exception ex){
        log.error("系统异常", ex);
        return Result.error(MessageConstant.UNKNOWN_ERROR);
    }

    /**
     * 参数校验失败（@RequestBody + @Valid）：聚合各字段校验消息返回给前端，避免裸 400 + 无提示。
     * @param ex
     * @return
     */
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public Result exceptionHandler(MethodArgumentNotValidException ex){
        String msg = ex.getBindingResult().getFieldErrors().stream()
                .map(FieldError::getDefaultMessage)
                .filter(Objects::nonNull)
                .collect(Collectors.joining("；"));
        log.warn("参数校验失败：{}", msg);
        return Result.error(msg.isEmpty() ? MessageConstant.UNKNOWN_ERROR : msg);
    }

}
