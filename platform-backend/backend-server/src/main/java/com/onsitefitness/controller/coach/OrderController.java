package com.onsitefitness.controller.coach;

import com.onsitefitness.context.BaseContext;
import com.onsitefitness.dto.ServiceCompleteDTO;
import com.onsitefitness.entity.Orders;
import com.onsitefitness.exception.OrderBusinessException;
import com.onsitefitness.result.PageResult;
import com.onsitefitness.result.Result;
import com.onsitefitness.service.DispatchPoolService;
import com.onsitefitness.service.OrderService;
import com.onsitefitness.vo.DispatchPoolVO;
import com.onsitefitness.vo.OrderVO;
import io.swagger.v3.oas.annotations.tags.Tag;
import io.swagger.v3.oas.annotations.Operation;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 教练端订单接口:接单/拒单/开始服务/完成服务/抢单/接单列表/派单池可抢列表
 */
@RestController("coachOrderController")
@RequestMapping("/coach/order")
@Tag(name = "教练端订单相关接口")
@Slf4j
public class OrderController {

    @Autowired
    private OrderService orderService;
    @Autowired
    private DispatchPoolService dispatchPoolService;

    /**
     * 教练接单列表分页查询
     */
    @GetMapping("/list")
    @Operation(summary = "教练接单列表分页查询")
    public Result<PageResult> list(int page, int pageSize, Integer status) {
        Long coachId = BaseContext.getCurrentId();
        PageResult pageResult = orderService.pageQuery4Coach(page, pageSize, status, coachId);
        return Result.success(pageResult);
    }

    /**
     * 教练确认接单(指定单)
     */
    @PutMapping("/confirm")
    @Operation(summary = "教练确认接单(指定单)")
    public Result confirm(Long id) {
        Long coachId = BaseContext.getCurrentId();
        orderService.confirmOrder(id, coachId);
        return Result.success();
    }

    /**
     * 教练拒单(指定单)
     */
    @PutMapping("/reject")
    @Operation(summary = "教练拒单(指定单)")
    public Result reject(Long id, String reason) {
        Long coachId = BaseContext.getCurrentId();
        orderService.rejectOrder(id, coachId, reason);
        return Result.success();
    }

    /**
     * 派单池抢单
     */
    @PostMapping("/seize")
    @Operation(summary = "派单池抢单")
    public Result seize(Long poolId) {
        Long coachId = BaseContext.getCurrentId();
        orderService.seize(poolId, coachId);
        return Result.success();
    }

    /**
     * 开始服务
     */
    @PutMapping("/startService")
    @Operation(summary = "开始服务")
    public Result startService(Long id) {
        Long coachId = BaseContext.getCurrentId();
        orderService.startService(id, coachId);
        return Result.success();
    }

    /**
     * 完成服务(提交训练记录/体测数据)
     */
    @PutMapping("/completeService")
    @Operation(summary = "完成服务")
    public Result completeService(@RequestBody ServiceCompleteDTO serviceCompleteDTO) {
        orderService.completeService(serviceCompleteDTO);
        return Result.success();
    }

    /**
     * 派单池可抢列表(按教练服务城市)
     */
    @GetMapping("/dispatchPool")
    @Operation(summary = "派单池可抢列表")
    public Result<List<DispatchPoolVO>> dispatchPool(String cityCode) {
        List<DispatchPoolVO> list = dispatchPoolService.listSeizable(cityCode);
        return Result.success(list);
    }

    /**
     * 查询订单详情
     */
    @GetMapping("/details/{id}")
    @Operation(summary = "查询订单详情")
    public Result<OrderVO> details(@PathVariable("id") Long id) {
        Orders order = orderService.getById(id);
        if (order == null || !order.getCoachId().equals(BaseContext.getCurrentId())) {
            throw new OrderBusinessException("无权查看该订单");
        }
        OrderVO orderVO = orderService.details(id);
        return Result.success(orderVO);
    }
}
