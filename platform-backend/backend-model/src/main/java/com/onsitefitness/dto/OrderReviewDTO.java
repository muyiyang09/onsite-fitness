package com.onsitefitness.dto;

import lombok.Data;

import java.io.Serializable;

/**
 * 订单评价提交 DTO
 */
@Data
public class OrderReviewDTO implements Serializable {

    private Long orderId;

    //教练评分 1-5
    private Integer coachRating;

    //课程评分 1-5
    private Integer courseRating;

    //评价内容
    private String content;

    //评价图片(逗号分隔URL)
    private String images;

}
