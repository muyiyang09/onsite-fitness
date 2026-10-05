package com.onsitefitness.controller.user;

import com.onsitefitness.result.Result;
import io.swagger.v3.oas.annotations.tags.Tag;
import io.swagger.v3.oas.annotations.Operation;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController("userShopController")
@RequestMapping("/user/shop")
@Tag(name = "店铺相关接口")
@Slf4j
public class ShopController {
    public static final String KEY = "SHOP_STATUS";
    /** 无 Redis 时的降级默认值：营业中（小程序前端用它判断是否允许下单/浏览） */
    public static final Integer DEFAULT_STATUS = 1;

    @Autowired
    private RedisTemplate<Object, Object> redisTemplate;

    /**
     * 获取店铺营业状态
     * Redis 不可用则默认"营业中"
     */
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
        log.info("获取的店铺营业状态：{}", status == 1 ? "开启" : "关闭");
        return Result.success(status);
    }
}
