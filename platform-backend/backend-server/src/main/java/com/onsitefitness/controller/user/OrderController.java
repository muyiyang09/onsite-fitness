package com.onsitefitness.controller.user;

import com.onsitefitness.context.BaseContext;
import com.onsitefitness.dto.OrdersPaymentDTO;
import com.onsitefitness.dto.OrdersSubmitDTO;
import com.onsitefitness.entity.Orders;
import com.onsitefitness.exception.OrderBusinessException;
import com.onsitefitness.result.PageResult;
import com.onsitefitness.result.Result;
import com.onsitefitness.service.OrderService;
import com.onsitefitness.vo.OrderPaymentVO;
import com.onsitefitness.vo.OrderSubmitVO;
import com.onsitefitness.vo.OrderVO;
import io.swagger.v3.oas.annotations.tags.Tag;
import io.swagger.v3.oas.annotations.Operation;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

@RestController("userOrderController")
@RequestMapping("/user/order")
@Tag(name = "用户d端订单相关接口")
@Slf4j
public class OrderController {
    @Autowired
    private OrderService orderService;
    /**
     * 用户下单
     * @param orderSubmitDTO
     * @return
     */
    @PostMapping("/submit")
    @Operation(summary = "用户下单")
    public Result<OrderSubmitVO> submit(@RequestBody OrdersSubmitDTO orderSubmitDTO) {
        log.info("订单提交参数：{}", orderSubmitDTO);
        // 订单提交业务逻辑
        OrderSubmitVO orderSubmitVO = orderService.submit(orderSubmitDTO);
        // 返回订单信息
        return Result.success(orderSubmitVO);
    }
    /**
     * 订单支付
     *
     * @param ordersPaymentDTO
     * @return
     */
    @PutMapping("/payment")
    @Operation(summary = "订单支付")
    public Result<OrderPaymentVO> payment(@RequestBody OrdersPaymentDTO ordersPaymentDTO) throws Exception {
        log.info("订单支付：{}", ordersPaymentDTO);
        OrderPaymentVO orderPaymentVO = orderService.payment(ordersPaymentDTO);
        log.info("生成预支付交易单：{}", orderPaymentVO);

        // 业务处理，修改订单转态、来单状态 模拟微信支付接口
        orderService.paySuccess(ordersPaymentDTO.getOrderNumber());
        log.info("订单支付成功：{}", ordersPaymentDTO.getOrderNumber());
        return Result.success(orderPaymentVO);
    }
    /**
     * 历史订单查询
     *
     * @param page
     * @param pageSize
     * @param status   订单状态 1待付款 2待接单 3已接单 4派送中 5已完成 6已取消
     * @return
     */
    @GetMapping("/historyOrders")
    @Operation(summary = "历史订单查询")
    public Result<PageResult> page(int page, int pageSize, Integer status) {
        PageResult pageResult = orderService.pageQuery4User(page, pageSize, status);
        return Result.success(pageResult);
    }
    /**
     * 查询订单详情
     *
     * @param id
     * @return
     */
    @GetMapping("/orderDetail/{id}")
    @Operation(summary = "查询订单详情")
    public Result<OrderVO> details(@PathVariable("id") Long id) {
        Orders order = orderService.getById(id);
        if (order == null || !order.getUserId().equals(BaseContext.getCurrentId())) {
            throw new OrderBusinessException("无权查看该订单");
        }
        OrderVO orderVO = orderService.details(id);
        return Result.success(orderVO);
    }

    /**
     * 用户取消订单
     *
     * @return
     */
    @PutMapping("/cancel/{id}")
    @Operation(summary = "取消订单")
    public Result cancel(@PathVariable("id") Long id) throws Exception {
        orderService.userCancelById(id);
        return Result.success();
    }
    /**
     * 用户申请退款
     * @param id
     * @return
     */
    @PutMapping("/refund/{id}")
    @Operation(summary = "申请退款")
    public Result refund(@PathVariable("id") Long id) {
        orderService.applyRefund(id);
        return Result.success();
    }
    /**
     * 客户催单
     * @param id
     * @return
     */
    @GetMapping("/reminder/{id}")
    @Operation(summary = "客户催单")
    public Result reminder(@PathVariable("id") Long id){
        Orders order = orderService.getById(id);
        if (order == null || !order.getUserId().equals(BaseContext.getCurrentId())) {
            throw new OrderBusinessException("无权操作该订单");
        }
        orderService.reminder(id);
        return Result.success();
    }

}
