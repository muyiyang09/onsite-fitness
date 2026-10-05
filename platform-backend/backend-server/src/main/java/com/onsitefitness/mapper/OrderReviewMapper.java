package com.onsitefitness.mapper;

import com.github.pagehelper.Page;
import com.onsitefitness.dto.OrderReviewPageQueryDTO;
import com.onsitefitness.entity.OrderReview;
import com.onsitefitness.vo.OrderReviewVO;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface OrderReviewMapper {

    /**
     * 新增评价
     * @param orderReview
     */
    void insert(OrderReview orderReview);

    /**
     * 根据订单id查询评价(含课程名/教练名)
     * @param orderId
     * @return
     */
    OrderReviewVO getByOrderId(Long orderId);

    /**
     * 按教练分页查询评价
     * @param orderReviewPageQueryDTO
     * @return
     */
    Page<OrderReviewVO> pageQueryByCoach(OrderReviewPageQueryDTO orderReviewPageQueryDTO);

    /**
     * 回填教练综合评分: rating = 该教练所有评价的教练评分均值(四舍五入保留1位)
     * @param coachId
     */
    void updateCoachRating(Long coachId);

}
