package com.sky.service.impl;

import com.github.pagehelper.Page;
import com.github.pagehelper.PageHelper;
import com.sky.constant.MessageConstant;
import com.sky.context.BaseContext;
import com.sky.dto.OrderReviewDTO;
import com.sky.dto.OrderReviewPageQueryDTO;
import com.sky.entity.OrderDetail;
import com.sky.entity.OrderReview;
import com.sky.entity.Orders;
import com.sky.exception.OrderBusinessException;
import com.sky.mapper.OrderDetailMapper;
import com.sky.mapper.OrderMapper;
import com.sky.mapper.OrderReviewMapper;
import com.sky.result.PageResult;
import com.sky.service.OrderReviewService;
import com.sky.utils.AiServiceClient;
import com.sky.vo.OrderReviewVO;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;

@Slf4j
@Service
public class OrderReviewServiceImpl implements OrderReviewService {

    @Autowired
    private OrderReviewMapper orderReviewMapper;
    @Autowired
    private OrderMapper orderMapper;
    @Autowired
    private OrderDetailMapper orderDetailMapper;
    @Autowired(required = false)
    private AiServiceClient aiServiceClient;

    /**
     * 提交评价：校验 → 写评价表 → 订单 COMPLETED→REVIEWED → 回填教练评分 → 异步触发 AI 摘要（失败降级）
     */
    @Override
    @Transactional
    public void submit(OrderReviewDTO orderReviewDTO) {
        Long orderId = orderReviewDTO.getOrderId();

        //1.校验订单存在且状态=已完成(已评价状态也允许兼容老数据的重复提交校验由第 2 步处理)
        Orders order = orderMapper.getById(orderId);
        if (order == null) {
            throw new OrderBusinessException(MessageConstant.ORDER_NOT_FOUND);
        }
        if (!Orders.COMPLETED.equals(order.getStatus())) {
            throw new OrderBusinessException(MessageConstant.ORDER_STATUS_ERROR);
        }

        //2.校验未评价（唯一业务约束：一单只能评一次）
        OrderReviewVO exist = orderReviewMapper.getByOrderId(orderId);
        if (exist != null) {
            throw new OrderBusinessException("该订单已评价");
        }

        //3.从订单明细取 coachId/courseId(订单本身 coachId 优先)
        Long coachId = order.getCoachId();
        Long courseId = null;
        List<OrderDetail> details = orderDetailMapper.getByOrderId(orderId);
        if (details != null && !details.isEmpty()) {
            OrderDetail first = details.get(0);
            if (coachId == null) {
                coachId = first.getCoachId();
            }
            courseId = first.getCourseId();
        }

        //4.插入评价
        OrderReview review = OrderReview.builder()
                .orderId(orderId)
                .userId(BaseContext.getCurrentId())
                .coachId(coachId)
                .courseId(courseId)
                .coachRating(orderReviewDTO.getCoachRating())
                .courseRating(orderReviewDTO.getCourseRating())
                .content(orderReviewDTO.getContent())
                .images(orderReviewDTO.getImages())
                .createTime(LocalDateTime.now())
                .build();
        orderReviewMapper.insert(review);

        //5.订单状态迁移：COMPLETED(5) -> REVIEWED(10)，关闭"待评价"业务窗口
        Orders orderUpdate = Orders.builder()
                .id(orderId)
                .status(Orders.REVIEWED)
                .updateTime(LocalDateTime.now())
                .build();
        orderMapper.update(orderUpdate);

        //6.回填教练综合评分(该教练所有评价 coach_rating 均值，SQL 四舍五入保留 1 位)
        if (coachId != null) {
            orderReviewMapper.updateCoachRating(coachId);
        }

        //7.异步触发 AI 评价摘要：失败降级（ai-service 不可用/未配置均不影响评价提交）
        if (coachId != null) {
            asyncRefreshReviewSummary(coachId);
        }
    }

    /**
     * 异步刷新教练评价摘要（AiServiceClient 未启用时静默跳过，走手动查询兜底）。
     * 加 @Async 需主类开启 @EnableAsync；如未开启则按同步调用 + try/catch 降级兜底。
     */
    @Async
    public void asyncRefreshReviewSummary(Long coachId) {
        if (aiServiceClient == null) {
            log.info("[评价摘要] AiServiceClient 未注入，跳过异步刷新 coach={}", coachId);
            return;
        }
        try {
            aiServiceClient.reviewSummary(coachId.intValue(), 30);
        } catch (Exception e) {
            // 摘要失败不影响主链路；后续用户访问教练详情时会通过 /v1/ai/review-summary 懒生成
            log.warn("[评价摘要] 异步刷新失败 coach={}：{}", coachId, e.getMessage());
        }
    }

    /**
     * 根据订单id查询评价
     */
    @Override
    public OrderReviewVO getByOrderId(Long orderId) {
        return orderReviewMapper.getByOrderId(orderId);
    }

    /**
     * 按教练分页查询评价
     */
    @Override
    public PageResult pageQueryByCoach(Long coachId, int page, int pageSize) {
        PageHelper.startPage(page, pageSize);
        OrderReviewPageQueryDTO dto = new OrderReviewPageQueryDTO();
        dto.setCoachId(coachId);
        Page<OrderReviewVO> p = orderReviewMapper.pageQueryByCoach(dto);
        return new PageResult(p.getTotal(), p.getResult());
    }
}
