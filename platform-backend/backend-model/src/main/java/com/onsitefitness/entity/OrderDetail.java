package com.onsitefitness.entity;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;

/**
 * 订单明细
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class OrderDetail implements Serializable {

    private static final long serialVersionUID = 1L;

    private Long id;

    //订单id
    private Long orderId;

    //课程id
    private Long courseId;

    //套餐id（套餐订单时填）
    private Long coursePackageId;

    //名称(课程名/套餐名)
    private String name;

    //图片
    private String image;

    //教练id
    private Long coachId;

    //排期id
    private Long scheduleId;

    //上门日期
    private LocalDate scheduleDate;

    //上门时段
    private String timeSlot;

    //节数
    private Integer number;

    //金额
    private BigDecimal amount;

    //创建时间
    private LocalDateTime createTime;

    //更新时间
    private LocalDateTime updateTime;
}
