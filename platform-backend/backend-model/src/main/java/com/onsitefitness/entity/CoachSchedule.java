package com.onsitefitness.entity;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;
import java.time.LocalDate;
import java.time.LocalDateTime;

/**
 * 教练排期
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class CoachSchedule implements Serializable {

    /**
     * 状态 1可约 2已占 3休息
     */
    public static final Integer STATUS_AVAILABLE = 1;
    public static final Integer STATUS_OCCUPIED = 2;
    public static final Integer STATUS_REST = 3;

    private static final long serialVersionUID = 1L;

    private Long id;

    //教练id
    private Long coachId;

    //排期日期
    private LocalDate scheduleDate;

    //时段(如 09:00-10:00)
    private String timeSlot;

    //状态 1可约 2已占 3休息
    private Integer status;

    //占用订单id
    private Long orderId;

    //创建时间
    private LocalDateTime createTime;

    //更新时间
    private LocalDateTime updateTime;
}
