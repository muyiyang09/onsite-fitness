package com.onsitefitness.entity;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;
import java.time.LocalDateTime;

/**
 * 评价（教练 + 课程双维度）
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class OrderReview implements Serializable {

    private static final long serialVersionUID = 1L;

    private Long id;

    //订单id
    private Long orderId;

    //用户id
    private Long userId;

    //教练id
    private Long coachId;

    //课程id
    private Long courseId;

    //教练评分 1-5
    private Integer coachRating;

    //课程评分 1-5
    private Integer courseRating;

    //评价内容
    private String content;

    //图片(逗号分隔)
    private String images;

    //评价时间
    private LocalDateTime createTime;
}
