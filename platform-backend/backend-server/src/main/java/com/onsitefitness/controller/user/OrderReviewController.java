package com.onsitefitness.controller.user;

import com.onsitefitness.dto.OrderReviewDTO;
import com.onsitefitness.result.Result;
import com.onsitefitness.service.OrderReviewService;
import com.onsitefitness.vo.OrderReviewVO;
import io.swagger.v3.oas.annotations.tags.Tag;
import io.swagger.v3.oas.annotations.Operation;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

/**
 * 用户端订单评价
 */
@RestController("userOrderReviewController")
@RequestMapping("/user/order/review")
@Tag(name = "C端-订单评价接口")
@Slf4j
public class OrderReviewController {

    @Autowired
    private OrderReviewService orderReviewService;

    /**
     * 提交评价
     */
    @PostMapping
    @Operation(summary = "提交评价")
    public Result submit(@RequestBody OrderReviewDTO orderReviewDTO) {
        log.info("提交评价：{}", orderReviewDTO);
        orderReviewService.submit(orderReviewDTO);
        return Result.success();
    }

    /**
     * 根据订单id查询评价
     */
    @GetMapping("/{orderId}")
    @Operation(summary = "根据订单id查询评价")
    public Result<OrderReviewVO> getByOrderId(@PathVariable Long orderId) {
        log.info("根据订单id查询评价：{}", orderId);
        OrderReviewVO orderReviewVO = orderReviewService.getByOrderId(orderId);
        return Result.success(orderReviewVO);
    }
}
