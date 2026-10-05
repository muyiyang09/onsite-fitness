package com.onsitefitness.service.impl;

import com.alibaba.fastjson2.JSON;
import com.github.pagehelper.Page;
import com.github.pagehelper.PageHelper;
import com.github.xiaoymin.knife4j.core.util.CollectionUtils;
import com.onsitefitness.annotation.AuditLog;
import com.onsitefitness.constant.MessageConstant;
import com.onsitefitness.context.BaseContext;
import com.onsitefitness.dto.*;
import com.onsitefitness.entity.*;
import com.onsitefitness.exception.AddressBookBusinessException;
import com.onsitefitness.exception.OrderBusinessException;
import com.onsitefitness.mapper.*;
import com.onsitefitness.result.PageResult;
import com.onsitefitness.service.OrderService;
import com.onsitefitness.utils.WeChatPayUtil;
import com.onsitefitness.vo.OrderPaymentVO;
import com.onsitefitness.vo.OrderStatisticsVO;
import com.onsitefitness.vo.OrderSubmitVO;
import com.onsitefitness.vo.OrderVO;
import com.onsitefitness.websocket.WebSocketServer;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.BeanUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.script.DefaultRedisScript;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.TimeUnit;
import java.util.stream.Collectors;

@Slf4j
@Service
public class OrderServiceImpl implements OrderService {

    @Autowired
    private AddressBookMapper addressBookMapper;
    @Autowired
    private OrderMapper orderMapper;
    @Autowired
    private OrderDetailMapper orderDetailMapper;
    @Autowired
    private UserMapper userMapper;
    @Autowired
    private WeChatPayUtil weChatPayUtil;
    @Autowired
    private WebSocketServer webSocketServer;
    @Autowired
    private DispatchPoolMapper dispatchPoolMapper;
    @Autowired
    private CoachScheduleMapper coachScheduleMapper;
    @Autowired
    private StringRedisTemplate stringRedisTemplate;
    @Autowired
    private CourseMapper courseMapper;
    @Autowired
    private CoursePackageMapper coursePackageMapper;

    /**
     * 分布式锁 CAS 释放脚本（§6.21）：get==value 才 del，原子操作杜绝
     * 「读-比较-删」三步之间的 TOCTOU（锁已过期被他人接管后误删）。
     */
    private static final DefaultRedisScript<Long> RELEASE_LOCK_SCRIPT = new DefaultRedisScript<>(
            "if redis.call('get',KEYS[1]) == ARGV[1] then return redis.call('del',KEYS[1]) else return 0 end",
            Long.class);

    /**
     * 用户下单:构造订单(status=PENDING_PAYMENT, payStatus=UN_PAID),不锁排期,保存 orders + order_detail
     */
    @Override
    @Transactional
    @AuditLog(type = "order.submit", detail = "用户下单")
    public OrderSubmitVO submit(OrdersSubmitDTO ordersSubmitDTO) {
        // 1.校验收货地址
        AddressBook addressBook = addressBookMapper.getById(ordersSubmitDTO.getAddressBookId());
        if (addressBook == null) {
            throw new AddressBookBusinessException(MessageConstant.ADDRESS_BOOK_IS_NULL);
        }

        Long userId = BaseContext.getCurrentId();

        // 2.构造订单
        Orders order = new Orders();
        BeanUtils.copyProperties(ordersSubmitDTO, order);
        order.setStatus(Orders.PENDING_PAYMENT);
        order.setPayStatus(Orders.UN_PAID);
        order.setOrderNumber(generateOrderNumber());
        order.setUserId(userId);
        order.setSubmitTime(LocalDateTime.now());
        order.setConsignee(addressBook.getConsignee());
        order.setPhone(addressBook.getPhone());
        order.setSex(addressBook.getSex());
        order.setAddress(addressBook.getProvinceName() + addressBook.getCityName()
                + addressBook.getDistrictName() + addressBook.getDetail());

        // 3.服务端校验金额：校验明细价格 + 重新计算总金额
        List<OrderDetail> orderDetails = ordersSubmitDTO.getOrderDetails();
        if (!CollectionUtils.isEmpty(orderDetails)) {
            BigDecimal calculatedAmount = BigDecimal.ZERO;
            for (OrderDetail detail : orderDetails) {
                if (detail.getCourseId() != null) {
                    Course course = courseMapper.getById(detail.getCourseId());
                    if (course == null) {
                        throw new OrderBusinessException("课程不存在");
                    }
                    detail.setAmount(course.getPrice());
                } else if (detail.getCoursePackageId() != null) {
                    CoursePackage coursePackage = coursePackageMapper.getById(detail.getCoursePackageId());
                    if (coursePackage == null) {
                        throw new OrderBusinessException("套餐不存在");
                    }
                    detail.setAmount(coursePackage.getPrice());
                }

                BigDecimal detailAmount = detail.getAmount() != null
                    ? detail.getAmount().multiply(new BigDecimal(detail.getNumber() != null ? detail.getNumber() : 1))
                    : BigDecimal.ZERO;
                calculatedAmount = calculatedAmount.add(detailAmount);
            }

            if (ordersSubmitDTO.getAmount() == null ||
                calculatedAmount.subtract(ordersSubmitDTO.getAmount()).abs().compareTo(new BigDecimal("0.01")) > 0) {
                log.warn("订单金额不匹配：客户端={}, 服务端计算={}", ordersSubmitDTO.getAmount(), calculatedAmount);
                throw new OrderBusinessException("订单金额异常，请重新下单");
            }

            order.setAmount(calculatedAmount);
        }

        orderMapper.insert(order);

        // 4.保存订单明细
        if (!CollectionUtils.isEmpty(orderDetails)) {
            for (OrderDetail detail : orderDetails) {
                detail.setOrderId(order.getId());
            }
            orderDetailMapper.insertBatch(orderDetails);
        }

        // 4.返回订单信息
        return OrderSubmitVO.builder()
                .id(order.getId())
                .orderNumber(order.getOrderNumber())
                .orderAmount(order.getAmount())
                .orderTime(order.getSubmitTime())
                .build();
    }

    /**
     * 订单支付(模拟微信支付,生成预支付交易单)
     */
    @Override
    public OrderPaymentVO payment(OrdersPaymentDTO ordersPaymentDTO) throws Exception {
        log.info("订单支付:{}", ordersPaymentDTO);
        // 模拟微信支付,直接返回空支付凭证(实际由 paySuccess 改状态)
        OrderPaymentVO vo = new OrderPaymentVO();
        vo.setNonceStr(UUID.randomUUID().toString().replace("-", ""));
        vo.setTimeStamp(String.valueOf(System.currentTimeMillis() / 1000));
        vo.setPackageStr("prepay_id=" + UUID.randomUUID().toString());
        vo.setSignType("MD5");
        vo.setPaySign(UUID.randomUUID().toString().replace("-", ""));
        return vo;
    }

    /**
     * 支付成功:状态 待付款->待接单,锁排期(乐观锁),派单池订单入池
     */
    @Override
    @Transactional
    public void paySuccess(String outTradeNo) {
        Orders ordersDB = orderMapper.getByNumber(outTradeNo);
        if (ordersDB == null) {
            throw new OrderBusinessException(MessageConstant.ORDER_NOT_FOUND);
        }

        if (!Orders.PENDING_PAYMENT.equals(ordersDB.getStatus())) {
            log.info("订单 {} 状态已为 {}，跳过支付处理", outTradeNo, ordersDB.getStatus());
            return;
        }

        // 1.更新订单状态:待付款 -> 待接单
        Orders orders = Orders.builder()
                .id(ordersDB.getId())
                .status(Orders.TO_BE_ACCEPTED)
                .payStatus(Orders.PAID)
                .checkoutTime(LocalDateTime.now())
                .updateTime(LocalDateTime.now())
                .build();
        orderMapper.update(orders);

        // 2.锁排期(乐观锁: AVAILABLE -> OCCUPIED,绑定订单id),影响行数=0 抛异常
        if (ordersDB.getScheduleId() != null) {
            int rows = coachScheduleMapper.lockSchedule(
                    ordersDB.getScheduleId(), ordersDB.getId(),
                    CoachSchedule.STATUS_AVAILABLE, CoachSchedule.STATUS_OCCUPIED);
            if (rows == 0) {
                throw new OrderBusinessException("排期已被占用,支付失败");
            }
        }

        // 3.派单池订单(orderMode=2)入派单池
        if (ordersDB.getOrderMode() != null && ordersDB.getOrderMode().equals(Orders.MODE_DISPATCH)) {
            DispatchPool pool = DispatchPool.builder()
                    .orderId(ordersDB.getId())
                    .dispatchType(DispatchPool.DISPATCH_PENDING)
                    .status(DispatchPool.STATUS_PENDING)
                    .expireTime(LocalDateTime.now().plusMinutes(30))
                    .createTime(LocalDateTime.now())
                    .build();
            dispatchPoolMapper.insert(pool);
        }

        // 4.WebSocket 来单提醒
        Map map = new HashMap();
        map.put("type", 1);
        map.put("orderId", ordersDB.getId());
        map.put("content", "订单号:" + outTradeNo);
        webSocketServer.sendToAllClient(JSON.toJSONString(map));
        log.info("来单提醒:{}", JSON.toJSONString(map));
    }

    /**
     * 用户历史订单分页查询
     */
    @Override
    public PageResult pageQuery4User(int page, int pageSize, Integer status) {
        PageHelper.startPage(page, pageSize);
        OrdersPageQueryDTO dto = new OrdersPageQueryDTO();
        dto.setUserId(BaseContext.getCurrentId());
        dto.setStatus(status);

        Page<Orders> pageResult = orderMapper.pageQuery(dto);
        List<OrderVO> list = buildOrderVOList(pageResult);
        return new PageResult(pageResult.getTotal(), list);
    }

    /**
     * 教练接单列表分页查询
     */
    @Override
    public PageResult pageQuery4Coach(int page, int pageSize, Integer status, Long coachId) {
        PageHelper.startPage(page, pageSize);
        OrdersPageQueryDTO dto = new OrdersPageQueryDTO();
        dto.setCoachId(coachId);
        dto.setStatus(status);

        Page<Orders> pageResult = orderMapper.pageQuery(dto);
        List<OrderVO> list = buildOrderVOList(pageResult);
        return new PageResult(pageResult.getTotal(), list);
    }

    /**
     * 订单详情(含订单明细,派单池订单含派单池信息)
     */
    @Override
    public OrderVO details(Long id) {
        Orders orders = orderMapper.getById(id);
        if (orders == null) {
            throw new OrderBusinessException(MessageConstant.ORDER_NOT_FOUND);
        }

        List<OrderDetail> orderDetailList = orderDetailMapper.getByOrderId(orders.getId());

        OrderVO orderVO = new OrderVO();
        BeanUtils.copyProperties(orders, orderVO);
        orderVO.setOrderDetailList(orderDetailList);

        // 派单池订单时附带派单池信息
        if (orders.getOrderMode() != null && orders.getOrderMode().equals(Orders.MODE_DISPATCH)) {
            DispatchPool pool = dispatchPoolMapper.getByOrderId(orders.getId());
            orderVO.setDispatchPool(pool);
        }
        return orderVO;
    }

    /**
     * 用户取消订单:校验 status in (PENDING_PAYMENT, TO_BE_ACCEPTED),释放排期,派单池订单取消池记录
     */
    @Override
    @Transactional
    public void userCancelById(Long id) throws Exception {
        Orders ordersDB = orderMapper.getById(id);
        if (ordersDB == null) {
            throw new OrderBusinessException(MessageConstant.ORDER_NOT_FOUND);
        }

        Long userId = BaseContext.getCurrentId();
        if (ordersDB.getUserId() == null || !ordersDB.getUserId().equals(userId)) {
            throw new OrderBusinessException(MessageConstant.ORDER_STATUS_ERROR);
        }

        Integer status = ordersDB.getStatus();
        if (!status.equals(Orders.PENDING_PAYMENT) && !status.equals(Orders.TO_BE_ACCEPTED)) {
            throw new OrderBusinessException(MessageConstant.ORDER_STATUS_ERROR);
        }

        // §11.1：已付款订单不允许直接取消（钱收了单没了），必须走申请退款流程
        if (status.equals(Orders.TO_BE_ACCEPTED)
                && ordersDB.getPayStatus() != null
                && ordersDB.getPayStatus().equals(Orders.PAID)) {
            throw new OrderBusinessException("已支付订单请走申请退款流程");
        }

        // 更新订单状态为已取消（仅待付款订单允许无损取消）
        Orders orders = Orders.builder()
                .id(ordersDB.getId())
                .status(Orders.CANCELLED)
                .cancelReason("用户取消")
                .cancelTime(LocalDateTime.now())
                .updateTime(LocalDateTime.now())
                .build();
        orderMapper.update(orders);

        // 释放排期
        releaseSchedule(ordersDB.getScheduleId());

        // 派单池订单取消池记录
        cancelDispatchPool(ordersDB.getId());
    }

    /**
     * 管理端订单条件查询
     */
    @Override
    public PageResult conditionSearch(OrdersPageQueryDTO ordersPageQueryDTO) {
        PageHelper.startPage(ordersPageQueryDTO.getPage(), ordersPageQueryDTO.getPageSize());
        Page<Orders> page = orderMapper.pageQuery(ordersPageQueryDTO);
        List<OrderVO> list = buildOrderVOList(page);
        return new PageResult(page.getTotal(), list);
    }

    /**
     * 订单状态统计(待接单/待服务/服务中)
     */
    @Override
    public OrderStatisticsVO statistics() {
        Integer toBeAccepted = orderMapper.countStatus(Orders.TO_BE_ACCEPTED);
        Integer toBeServed = orderMapper.countStatus(Orders.TO_BE_SERVED);
        Integer inService = orderMapper.countStatus(Orders.IN_SERVICE);

        OrderStatisticsVO vo = new OrderStatisticsVO();
        vo.setToBeConfirmed(toBeAccepted);
        vo.setConfirmed(toBeServed);
        vo.setDeliveryInProgress(inService);
        return vo;
    }

    /**
     * 管理端接单(保留):状态 -> 待服务
     */
    @Override
    public void confirm(OrdersConfirmDTO ordersConfirmDTO) {
        Orders orders = Orders.builder()
                .id(ordersConfirmDTO.getId())
                .status(Orders.TO_BE_SERVED)
                .acceptTime(LocalDateTime.now())
                .updateTime(LocalDateTime.now())
                .build();
        orderMapper.update(orders);
    }

    /**
     * 管理端拒单(保留):状态 -> 已取消
     */
    @Override
    @Transactional
    public void rejection(OrdersRejectionDTO ordersRejectionDTO) throws Exception {
        Orders ordersDB = orderMapper.getById(ordersRejectionDTO.getId());
        if (ordersDB == null || !ordersDB.getStatus().equals(Orders.TO_BE_ACCEPTED)) {
            throw new OrderBusinessException(MessageConstant.ORDER_STATUS_ERROR);
        }

        Orders orders = Orders.builder()
                .id(ordersDB.getId())
                .status(Orders.REJECTED)
                .rejectionReason(ordersRejectionDTO.getRejectionReason())
                .cancelTime(LocalDateTime.now())
                .updateTime(LocalDateTime.now())
                .build();
        orderMapper.update(orders);

        releaseSchedule(ordersDB.getScheduleId());
        cancelDispatchPool(ordersDB.getId());
    }

    /**
     * 管理端取消订单(保留)
     */
    @Override
    @Transactional
    public void cancel(OrdersCancelDTO ordersCancelDTO) throws Exception {
        Orders ordersDB = orderMapper.getById(ordersCancelDTO.getId());
        if (ordersDB == null) {
            throw new OrderBusinessException(MessageConstant.ORDER_NOT_FOUND);
        }

        Orders orders = Orders.builder()
                .id(ordersDB.getId())
                .status(Orders.CANCELLED)
                .cancelReason(ordersCancelDTO.getCancelReason())
                .cancelTime(LocalDateTime.now())
                .updateTime(LocalDateTime.now())
                .build();
        orderMapper.update(orders);

        releaseSchedule(ordersDB.getScheduleId());
        cancelDispatchPool(ordersDB.getId());
    }

    /**
     * 管理端派送(保留,上门体育无派送,仅状态流转:待服务 -> 服务中)
     */
    @Override
    public void delivery(Long id) {
        Orders ordersDB = orderMapper.getById(id);
        if (ordersDB == null || !ordersDB.getStatus().equals(Orders.TO_BE_SERVED)) {
            throw new OrderBusinessException(MessageConstant.ORDER_STATUS_ERROR);
        }
        Orders orders = Orders.builder()
                .id(ordersDB.getId())
                .status(Orders.IN_SERVICE)
                .serviceStartTime(LocalDateTime.now())
                .updateTime(LocalDateTime.now())
                .build();
        orderMapper.update(orders);
    }

    /**
     * 管理端完成订单(保留):状态 -> 已完成
     */
    @Override
    public void complete(Long id) {
        Orders ordersDB = orderMapper.getById(id);
        if (ordersDB == null || !ordersDB.getStatus().equals(Orders.IN_SERVICE)) {
            throw new OrderBusinessException(MessageConstant.ORDER_STATUS_ERROR);
        }
        Orders orders = Orders.builder()
                .id(ordersDB.getId())
                .status(Orders.COMPLETED)
                .serviceEndTime(LocalDateTime.now())
                .updateTime(LocalDateTime.now())
                .build();
        orderMapper.update(orders);
    }

    /**
     * 订单催单
     */
    @Override
    public void reminder(Long id) {
        Orders ordersDB = orderMapper.getById(id);
        if (ordersDB == null) {
            throw new OrderBusinessException(MessageConstant.ORDER_NOT_FOUND);
        }
        Map map = new HashMap();
        map.put("orderId", id);
        map.put("type", 2);
        map.put("content", "订单号:" + ordersDB.getOrderNumber() + ",请及时服务");
        webSocketServer.sendToAllClient(JSON.toJSONString(map));
        log.info("订单状态提醒:{}", JSON.toJSONString(map));
    }

    /**
     * 教练确认接单(指定单):校验 orderMode=1,status=TO_BE_ACCEPTED,coach_id=coachId
     */
    @Override
    @Transactional
    public void confirmOrder(Long orderId, Long coachId) {
        Orders ordersDB = orderMapper.getById(orderId);
        if (ordersDB == null) {
            throw new OrderBusinessException(MessageConstant.ORDER_NOT_FOUND);
        }
        if (!Orders.MODE_APPOINT.equals(ordersDB.getOrderMode())) {
            throw new OrderBusinessException("非指定单,无法直接确认");
        }
        if (!Orders.TO_BE_ACCEPTED.equals(ordersDB.getStatus())) {
            throw new OrderBusinessException(MessageConstant.ORDER_STATUS_ERROR);
        }
        if (ordersDB.getCoachId() == null || !ordersDB.getCoachId().equals(coachId)) {
            throw new OrderBusinessException("该订单不属于当前教练");
        }

        Orders orders = Orders.builder()
                .id(orderId)
                .status(Orders.TO_BE_SERVED)
                .acceptTime(LocalDateTime.now())
                .updateTime(LocalDateTime.now())
                .build();
        orderMapper.update(orders);
    }

    /**
     * 教练拒单(指定单):改状态 REJECTED,释放排期
     */
    @Override
    @Transactional
    public void rejectOrder(Long orderId, Long coachId, String reason) {
        Orders ordersDB = orderMapper.getById(orderId);
        if (ordersDB == null) {
            throw new OrderBusinessException(MessageConstant.ORDER_NOT_FOUND);
        }
        if (!Orders.MODE_APPOINT.equals(ordersDB.getOrderMode())) {
            throw new OrderBusinessException("非指定单,无法拒单");
        }
        if (!Orders.TO_BE_ACCEPTED.equals(ordersDB.getStatus())) {
            throw new OrderBusinessException(MessageConstant.ORDER_STATUS_ERROR);
        }
        if (ordersDB.getCoachId() == null || !ordersDB.getCoachId().equals(coachId)) {
            throw new OrderBusinessException("该订单不属于当前教练");
        }

        Orders orders = Orders.builder()
                .id(orderId)
                .status(Orders.REJECTED)
                .rejectionReason(reason)
                .cancelTime(LocalDateTime.now())
                .updateTime(LocalDateTime.now())
                .build();
        orderMapper.update(orders);

        releaseSchedule(ordersDB.getScheduleId());
    }

    /**
     * 派单池抢单:Redis 分布式锁 + 乐观锁更新 dispatch_pool + 回填 orders
     */
    @Override
    @Transactional
    @AuditLog(type = "order.seize", detail = "派单池抢单")
    public void seize(Long poolId, Long coachId) {
        String lockKey = "dispatch:seize:" + poolId;
        String lockValue = UUID.randomUUID().toString().replace("-", "");
        Boolean locked = stringRedisTemplate.opsForValue()
                .setIfAbsent(lockKey, lockValue, 10, TimeUnit.SECONDS);
        if (!Boolean.TRUE.equals(locked)) {
            throw new OrderBusinessException("抢单繁忙,请重试");
        }
        try {
            // 1.乐观锁更新派单池: status=PENDING -> DISPATCHED
            int rows = dispatchPoolMapper.seize(
                    poolId, DispatchPool.STATUS_DISPATCHED, coachId,
                    DispatchPool.DISPATCH_SEIZE, LocalDateTime.now(), DispatchPool.STATUS_PENDING);
            if (rows == 0) {
                throw new OrderBusinessException("抢单失败,订单已被抢或已取消");
            }

            // 2.回填订单: coach_id, status=TO_BE_SERVED, acceptTime
            DispatchPool pool = dispatchPoolMapper.getById(poolId);
            Orders orders = Orders.builder()
                    .id(pool.getOrderId())
                    .coachId(coachId)
                    .status(Orders.TO_BE_SERVED)
                    .acceptTime(LocalDateTime.now())
                    .dispatchType(Orders.DISPATCH_SEIZE)
                    .updateTime(LocalDateTime.now())
                    .build();
            orderMapper.update(orders);
        } finally {
            // 释放锁：Lua CAS 原子 get==value→del，避免 TOCTOU 误删（§6.21）
            stringRedisTemplate.execute(RELEASE_LOCK_SCRIPT, Collections.singletonList(lockKey), lockValue);
        }
    }

    /**
     * 开始服务:校验 status=TO_BE_SERVED,coach_id=coachId
     */
    @Override
    public void startService(Long orderId, Long coachId) {
        Orders ordersDB = orderMapper.getById(orderId);
        if (ordersDB == null) {
            throw new OrderBusinessException(MessageConstant.ORDER_NOT_FOUND);
        }
        if (!Orders.TO_BE_SERVED.equals(ordersDB.getStatus())) {
            throw new OrderBusinessException(MessageConstant.ORDER_STATUS_ERROR);
        }
        if (ordersDB.getCoachId() == null || !ordersDB.getCoachId().equals(coachId)) {
            throw new OrderBusinessException("该订单不属于当前教练");
        }

        Orders orders = Orders.builder()
                .id(orderId)
                .status(Orders.IN_SERVICE)
                .serviceStartTime(LocalDateTime.now())
                .updateTime(LocalDateTime.now())
                .build();
        orderMapper.update(orders);
    }

    /**
     * 完成服务:校验 status=IN_SERVICE,coach_id=coachId,记录 trainRecord/bodyData
     */
    @Override
    public void completeService(ServiceCompleteDTO serviceCompleteDTO) {
        Long orderId = serviceCompleteDTO.getId();
        Long coachId = serviceCompleteDTO.getCoachId();
        Orders ordersDB = orderMapper.getById(orderId);
        if (ordersDB == null) {
            throw new OrderBusinessException(MessageConstant.ORDER_NOT_FOUND);
        }
        if (!Orders.IN_SERVICE.equals(ordersDB.getStatus())) {
            throw new OrderBusinessException(MessageConstant.ORDER_STATUS_ERROR);
        }
        if (ordersDB.getCoachId() == null || !ordersDB.getCoachId().equals(coachId)) {
            throw new OrderBusinessException("该订单不属于当前教练");
        }

        Orders orders = Orders.builder()
                .id(orderId)
                .status(Orders.COMPLETED)
                .serviceEndTime(LocalDateTime.now())
                .trainRecord(serviceCompleteDTO.getTrainRecord())
                .bodyData(serviceCompleteDTO.getBodyData())
                .updateTime(LocalDateTime.now())
                .build();
        orderMapper.update(orders);
        // 评价由用户端触发：服务完成后订单进入 COMPLETED(5)，
        // 用户在小程序提交评价（/user/order/review POST）时：
        //   1. 单评校验 + 写 order_review 表
        //   2. 订单状态 COMPLETED(5) -> REVIEWED(10)
        //   3. 回填 coach.rating（SQL avg 四舍五入 1 位）
        //   4. 异步刷新 AI 评价摘要（失败降级，不阻塞评价提交）
        // 具体实现见 OrderReviewServiceImpl.submit()。
    }

    /**
     * 用户申请退款:状态 2待接单/3待服务 -> 8退款中
     */
    @Override
    @Transactional
    @AuditLog(type = "order.refund", detail = "用户申请退款")
    public void applyRefund(Long orderId) {
        Orders ordersDB = orderMapper.getById(orderId);
        if (ordersDB == null) {
            throw new OrderBusinessException(MessageConstant.ORDER_NOT_FOUND);
        }
        if (!Orders.TO_BE_ACCEPTED.equals(ordersDB.getStatus())
                && !Orders.TO_BE_SERVED.equals(ordersDB.getStatus())) {
            throw new OrderBusinessException("当前状态不可申请退款");
        }
        Orders orders = Orders.builder()
                .id(orderId)
                .status(Orders.REFUNDING)
                .updateTime(LocalDateTime.now())
                .build();
        orderMapper.update(orders);
    }

    /**
     * 管理端处理退款:8退款中 -> 9已退款(释放排期/派单池) 或 退回原状态
     */
    @Override
    @Transactional
    @AuditLog(type = "order.handle", detail = "管理端处理退款")
    public void handleRefund(Long orderId, boolean agree) {
        Orders ordersDB = orderMapper.getById(orderId);
        if (ordersDB == null) {
            throw new OrderBusinessException(MessageConstant.ORDER_NOT_FOUND);
        }
        if (!Orders.REFUNDING.equals(ordersDB.getStatus())) {
            throw new OrderBusinessException("订单不在退款中状态");
        }
        if (agree) {
            // 退款成功:8 -> 9已退款
            Orders orders = Orders.builder()
                    .id(orderId)
                    .status(Orders.REFUNDED)
                    .updateTime(LocalDateTime.now())
                    .build();
            orderMapper.update(orders);
            releaseSchedule(ordersDB.getScheduleId());
            cancelDispatchPool(orderId);
        } else {
            // 拒绝退款:退回原状态(教练已接->待服务,未接->待接单)
            Integer backStatus = ordersDB.getAcceptTime() != null
                    ? Orders.TO_BE_SERVED : Orders.TO_BE_ACCEPTED;
            Orders orders = Orders.builder()
                    .id(orderId)
                    .status(backStatus)
                    .updateTime(LocalDateTime.now())
                    .build();
            orderMapper.update(orders);
        }
    }

    /**
     * 根据id获取订单
     */
    @Override
    public Orders getById(Long id) {
        return orderMapper.getById(id);
    }

    // ==================== 私有辅助方法 ====================

    /**
     * 生成订单号(时间戳 + 随机)
     */
    private String generateOrderNumber() {
        return System.currentTimeMillis() + UUID.randomUUID().toString().replace("-", "").substring(0, 6);
    }

    /**
     * 释放排期(status -> AVAILABLE, order_id = null)
     */
    private void releaseSchedule(Long scheduleId) {
        if (scheduleId != null) {
            coachScheduleMapper.releaseSchedule(scheduleId, CoachSchedule.STATUS_AVAILABLE);
        }
    }

    /**
     * 取消派单池记录(status -> CANCELLED)
     */
    private void cancelDispatchPool(Long orderId) {
        DispatchPool pool = dispatchPoolMapper.getByOrderId(orderId);
        if (pool != null && DispatchPool.STATUS_PENDING.equals(pool.getStatus())) {
            DispatchPool update = DispatchPool.builder()
                    .id(pool.getId())
                    .status(DispatchPool.STATUS_CANCELLED)
                    .build();
            dispatchPoolMapper.update(update);
        }
    }

    /**
     * 构造订单 VO 列表(含订单明细)
     */
    private List<OrderVO> buildOrderVOList(Page<Orders> page) {
        List<OrderVO> list = new ArrayList<>();
        if (page == null || page.getTotal() <= 0) {
            return list;
        }
        for (Orders orders : page.getResult()) {
            List<OrderDetail> orderDetails = orderDetailMapper.getByOrderId(orders.getId());
            OrderVO orderVO = new OrderVO();
            BeanUtils.copyProperties(orders, orderVO);
            orderVO.setOrderDetailList(orderDetails);
            orderVO.setOrderDishes(getOrderDishesStr(orderDetails));
            list.add(orderVO);
        }
        return list;
    }

    /**
     * 拼接订单课程信息字符串
     */
    private String getOrderDishesStr(List<OrderDetail> orderDetailList) {
        if (CollectionUtils.isEmpty(orderDetailList)) {
            return "";
        }
        List<String> dishList = orderDetailList.stream()
                .map(x -> x.getName() + "*" + x.getNumber() + ";")
                .collect(Collectors.toList());
        return String.join("", dishList);
    }
}
