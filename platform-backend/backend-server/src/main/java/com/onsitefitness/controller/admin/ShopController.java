package com.onsitefitness.controller.admin;

import com.onsitefitness.result.Result;
import io.swagger.v3.oas.annotations.tags.Tag;
import io.swagger.v3.oas.annotations.Operation;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.web.bind.annotation.*;

@RestController("adminShopController")
@RequestMapping("/admin/shop")
@Tag(name = "店铺相关接口")
@Slf4j
public class ShopController {
    public static final String KEY = "SHOP_STATUS";
    public static final Integer DEFAULT_STATUS = 1;

    @Autowired
    private RedisTemplate<Object, Object> redisTemplate;

    /**
     * 设置店铺营业状态。Redis 不可用时仍记录日志（实际业务需后续补管理端告警）
     */
    @PutMapping("/{status}")
    @Operation(summary = "设置营业状态")
    public Result setStatus(@PathVariable Integer status) {
        log.info("设置店铺状态：{}", status == 1 ? "营业中" : "打烊中");
        try {
            redisTemplate.opsForValue().set(KEY, status);
        } catch (Exception e) {
            log.warn("写入店铺营业状态失败(Redis不可用) msg={}", e.getMessage());
        }
        return Result.success();
    }

    @GetMapping("/status")
    @Operation(summary = "获取店铺的营业状态")
    public Result<Integer> getStatus() {
        Integer status;
        try {
            Object val = redisTemplate.opsForValue().get(KEY);
            status = (val instanceof Integer) ? (Integer) val : null;
        } catch (Exception e) {
            log.warn("读取店铺营业状态失败(降级:默认营业中) msg={}", e.getMessage());
            status = null;
        }
        if (status == null) status = DEFAULT_STATUS;
        log.info("获取的店铺营业状态：{}", status == 1 ? "营业中" : "打烊中");
        return Result.success(status);
    }
}
