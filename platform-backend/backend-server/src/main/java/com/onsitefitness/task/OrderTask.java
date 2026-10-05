package com.onsitefitness.task;

import com.onsitefitness.entity.DispatchPool;
import com.onsitefitness.entity.Orders;
import com.onsitefitness.mapper.CoachScheduleMapper;
import com.onsitefitness.mapper.DispatchPoolMapper;
import com.onsitefitness.mapper.OrderMapper;
import lombok.extern.slf4j.Slf4j;
import net.javacrumbs.shedlock.spring.annotation.SchedulerLock;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;
import java.util.List;

@Component
@Slf4j
public class OrderTask {

    /** 待付款订单超时时长（分钟）：下单后超过该时长仍未支付则自动取消（§6.25） */
    private static final int PENDING_PAYMENT_TIMEOUT_MINUTES = 15;

    @Autowired
    private OrderMapper orderMapper;
    @Autowired
    private DispatchPoolMapper dispatchPoolMapper;
    @Autowired
    private CoachScheduleMapper coachScheduleMapper;

    /**
     * 派单池超时定时任务:每分钟扫描超时未派的派单池记录,取消订单并释放排期
     *
     * §6.24：ShedLock 保证多副本部署时同一时刻只有一个实例执行本任务。
     */
    @Scheduled(fixedRate = 60000)
    @SchedulerLock(name = "order-task-dispatch")
    public void processDispatchTimeout() {
        log.info("定时处理派单池超时订单:{}", LocalDateTime.now());

        List<DispatchPool> expiredList = dispatchPoolMapper.listExpired(DispatchPool.STATUS_PENDING);
        if (expiredList == null || expiredList.isEmpty()) {
            return;
        }
        for (DispatchPool pool : expiredList) {
            try {
                // 1.取消派单池记录
                DispatchPool update = DispatchPool.builder()
                        .id(pool.getId())
                        .status(DispatchPool.STATUS_CANCELLED)
                        .build();
                dispatchPoolMapper.update(update);

                // 2.取消订单
                Orders orders = Orders.builder()
                        .id(pool.getOrderId())
                        .status(Orders.CANCELLED)
                        .cancelReason("派单超时")
                        .cancelTime(LocalDateTime.now())
                        .updateTime(LocalDateTime.now())
                        .build();
                orderMapper.update(orders);

                // 3.释放排期
                Orders ordersDB = orderMapper.getById(pool.getOrderId());
                if (ordersDB != null && ordersDB.getScheduleId() != null) {
                    coachScheduleMapper.releaseSchedule(ordersDB.getScheduleId(),
                            com.onsitefitness.entity.CoachSchedule.STATUS_AVAILABLE);
                }
            } catch (Exception e) {
                log.error("处理派单池超时失败,poolId={}", pool.getId(), e);
            }
        }
    }

    /**
     * 待付款超时取消（§6.25）：扫描 PENDING_PAYMENT 且 submitTime 超过 15 分钟的订单，自动取消。
     * 此时排期尚未锁定（支付成功才锁）、也未入派单池，故只需改订单状态，无需释放排期/取消池记录。
     */
    @Scheduled(fixedRate = 60000)
    @SchedulerLock(name = "order-task-pending")
    public void processPendingPaymentTimeout() {
        LocalDateTime deadline = LocalDateTime.now().minusMinutes(PENDING_PAYMENT_TIMEOUT_MINUTES);
        List<Orders> expiredList = orderMapper.getByStatusAndSubmitTime(Orders.PENDING_PAYMENT, deadline);
        if (expiredList == null || expiredList.isEmpty()) {
            return;
        }
        for (Orders order : expiredList) {
            try {
                Orders update = Orders.builder()
                        .id(order.getId())
                        .status(Orders.CANCELLED)
                        .cancelReason("超时未支付")
                        .cancelTime(LocalDateTime.now())
                        .updateTime(LocalDateTime.now())
                        .build();
                orderMapper.update(update);
                log.info("待付款订单超时取消：orderId={}, orderNumber={}", order.getId(), order.getOrderNumber());
            } catch (Exception e) {
                log.error("待付款订单超时取消失败,orderId={}", order.getId(), e);
            }
        }
    }
}
