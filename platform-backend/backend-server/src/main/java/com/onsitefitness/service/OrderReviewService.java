package com.onsitefitness.service;

import com.onsitefitness.dto.OrderReviewDTO;
import com.onsitefitness.result.PageResult;
import com.onsitefitness.vo.OrderReviewVO;

public interface OrderReviewService {

    /**
     * 提交评价(校验订单已完成+未评价,回填教练评分)
     * @param orderReviewDTO
     */
    void submit(OrderReviewDTO orderReviewDTO);

    /**
     * 根据订单id查询评价
     * @param orderId
     * @return
     */
    OrderReviewVO getByOrderId(Long orderId);

    /**
     * 按教练分页查询评价
     * @param coachId
     * @param page
     * @param pageSize
     * @return
     */
    PageResult pageQueryByCoach(Long coachId, int page, int pageSize);

}
