package com.onsitefitness.service;

import com.onsitefitness.dto.*;
import com.onsitefitness.entity.Orders;
import com.onsitefitness.result.PageResult;
import com.onsitefitness.vo.OrderPaymentVO;
import com.onsitefitness.vo.OrderStatisticsVO;
import com.onsitefitness.vo.OrderSubmitVO;
import com.onsitefitness.vo.OrderVO;

public interface OrderService {

    /**
     * 用户下单
     */
    OrderSubmitVO submit(OrdersSubmitDTO ordersSubmitDTO);

    /**
     * 订单支付
     */
    OrderPaymentVO payment(OrdersPaymentDTO ordersPaymentDTO) throws Exception;

    /**
     * 支付成功,修改订单状态(待付款 -> 待接单),锁排期,派单池订单入池
     */
    void paySuccess(String outTradeNo);

    /**
     * 用户历史订单分页查询
     */
    PageResult pageQuery4User(int page, int pageSize, Integer status);

    /**
     * 教练接单列表分页查询
     */
    PageResult pageQuery4Coach(int page, int pageSize, Integer status, Long coachId);

    /**
     * 订单详情(含订单明细,派单池订单含派单池信息)
     */
    OrderVO details(Long id);

    /**
     * 用户取消订单
     */
    void userCancelById(Long id) throws Exception;

    /**
     * 管理端订单条件查询
     */
    PageResult conditionSearch(OrdersPageQueryDTO ordersPageQueryDTO);

    /**
     * 订单状态统计
     */
    OrderStatisticsVO statistics();

    /**
     * 管理端接单(保留)
     */
    void confirm(OrdersConfirmDTO ordersConfirmDTO);

    /**
     * 管理端拒单(保留)
     */
    void rejection(OrdersRejectionDTO ordersRejectionDTO) throws Exception;

    /**
     * 管理端取消订单(保留)
     */
    void cancel(OrdersCancelDTO ordersCancelDTO) throws Exception;

    /**
     * 管理端派送(保留,上门体育无派送,仅改状态)
     */
    void delivery(Long id);

    /**
     * 管理端完成订单(保留)
     */
    void complete(Long id);

    /**
     * 订单催单
     */
    void reminder(Long id);

    /**
     * 教练确认接单(指定单): 校验 orderMode=1,status=TO_BE_ACCEPTED,coach_id=coachId
     */
    void confirmOrder(Long orderId, Long coachId);

    /**
     * 教练拒单(指定单): 校验同上,改状态 REJECTED,释放排期
     */
    void rejectOrder(Long orderId, Long coachId, String reason);

    /**
     * 派单池抢单: Redis 分布式锁 + 乐观锁更新 dispatch_pool + 回填 orders
     */
    void seize(Long poolId, Long coachId);

    /**
     * 开始服务: 校验 status=TO_BE_SERVED,coach_id=coachId
     */
    void startService(Long orderId, Long coachId);

    /**
     * 完成服务: 校验 status=IN_SERVICE,coach_id=coachId,记录 trainRecord/bodyData
     */
    void completeService(ServiceCompleteDTO serviceCompleteDTO);

    /**
     * 用户申请退款(状态 2待接单/3待服务 -> 8退款中)
     */
    void applyRefund(Long orderId);

    /**
     * 管理端处理退款(8退款中 -> 9已退款 或 退回原状态)
     */
    void handleRefund(Long orderId, boolean agree);

    /**
     * 根据id获取订单
     */
    Orders getById(Long id);
}
