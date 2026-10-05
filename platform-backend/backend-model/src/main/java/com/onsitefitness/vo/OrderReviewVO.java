package com.onsitefitness.vo;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;
import java.time.LocalDateTime;

/**
 * 订单评价 VO(含课程名/教练名)
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class OrderReviewVO implements Serializable {

    private Long id;

    private Long orderId;

    private Long userId;

    private Long coachId;

    private Long courseId;

    //教练评分 1-5
    private Integer coachRating;

    //课程评分 1-5
    private Integer courseRating;

    private String content;

    private String images;

    private LocalDateTime createTime;

    //课程名称
    private String courseName;

    //教练姓名
    private String coachName;

}
