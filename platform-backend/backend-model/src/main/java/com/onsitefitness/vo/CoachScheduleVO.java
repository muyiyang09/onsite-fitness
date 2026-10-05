package com.onsitefitness.vo;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;
import java.time.LocalDate;
import java.time.LocalDateTime;

/**
 * 教练排期 VO
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class CoachScheduleVO implements Serializable {

    private Long id;

    private Long coachId;

    private LocalDate scheduleDate;

    private String timeSlot;

    //状态 1可约 2已占 3休息
    private Integer status;

    private Long orderId;

    private LocalDateTime createTime;

    private LocalDateTime updateTime;

}
